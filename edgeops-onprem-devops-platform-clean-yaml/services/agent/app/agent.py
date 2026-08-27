import os
import socket
import time

import requests

from kubernetes import client, config

from prometheus_client import (
    Gauge,
    start_http_server,
)


# ============================================================
# Configuration
# ============================================================

AGENT_API = os.getenv(
    "EDGEOPS_API",
    "http://api:8000",
)

CLUSTER_NAME = os.getenv(
    "CLUSTER_NAME",
    "edgeops-kubernetes-cluster",
)

INTERVAL = int(
    os.getenv(
        "COLLECT_INTERVAL",
        "30",
    )
)


# ============================================================
# Prometheus Metrics
# ============================================================

node_count = Gauge(
    "edgeops_agent_nodes",
    "Number of Kubernetes nodes discovered",
)

ready_node_count = Gauge(
    "edgeops_agent_ready_nodes",
    "Number of Kubernetes nodes in Ready state",
)

pod_count = Gauge(
    "edgeops_agent_pods",
    "Number of Kubernetes pods discovered",
)

pvc_count = Gauge(
    "edgeops_agent_pvcs",
    "Number of Kubernetes PVCs discovered",
)

deployment_count = Gauge(
    "edgeops_agent_deployments",
    "Number of Kubernetes deployments discovered",
)


# ============================================================
# Kubernetes Configuration
# ============================================================

def load_kube():

    print(
        "Loading Kubernetes configuration...",
        flush=True,
    )

    try:

        config.load_incluster_config()

        print(
            "Using in-cluster Kubernetes configuration",
            flush=True,
        )

        return

    except Exception as exc:

        print(
            f"In-cluster config unavailable: {exc}",
            flush=True,
        )

    try:

        config.load_kube_config()

        print(
            "Using KUBECONFIG configuration",
            flush=True,
        )

    except Exception as exc:

        print(
            f"Failed to load Kubernetes config: {exc}",
            flush=True,
        )

        raise


# ============================================================
# API Helper
# ============================================================

def api_post(
    endpoint,
    payload,
):

    try:

        response = requests.post(
            f"{AGENT_API}{endpoint}",
            json=payload,
            timeout=5,
        )

        return response

    except Exception as exc:

        print(
            f"API request failed "
            f"{endpoint}: {exc}",
            flush=True,
        )

        return None


# ============================================================
# Register / Update Cluster
# ============================================================

def register_cluster(
    kubernetes_version,
    node_total,
):

    payload = {
        "name": CLUSTER_NAME,
        "environment": "production",
        "location": socket.gethostname(),
        "kubernetes_version": kubernetes_version,
    }

    response = api_post(
        "/api/clusters",
        payload,
    )

    if response is None:
        return

    if response.status_code in (
        200,
        201,
    ):

        print(
            f"Cluster registered/updated: "
            f"{CLUSTER_NAME}",
            flush=True,
        )

    else:

        print(
            f"Cluster registration failed: "
            f"{response.status_code} "
            f"{response.text}",
            flush=True,
        )


# ============================================================
# Node Ready Status
# ============================================================

def node_is_ready(node):

    for condition in (
        node.status.conditions or []
    ):

        if condition.type == "Ready":

            return condition.status == "True"

    return False


# ============================================================
# Register / Update Kubernetes Nodes
# ============================================================

def register_nodes(
    nodes,
    pods,
):

    # Count pods running on each node.
    pods_per_node = {}

    for pod in pods:

        node_name = (
            pod.spec.node_name
        )

        if node_name:

            pods_per_node[node_name] = (
                pods_per_node.get(
                    node_name,
                    0,
                )
                + 1
            )

    for node in nodes:

        node_name = node.metadata.name

        ready = node_is_ready(
            node
        )

        status = (
            "ready"
            if ready
            else "not-ready"
        )

        # ----------------------------------------------------
        # Node IP
        # ----------------------------------------------------

        internal_ip = "unknown"

        for address in (
            node.status.addresses or []
        ):

            if address.type == "InternalIP":

                internal_ip = address.address

                break

        # ----------------------------------------------------
        # Node information
        # ----------------------------------------------------

        node_info = (
            node.status.node_info
        )

        kubernetes_version = "unknown"
        architecture = "unknown"
        operating_system = "unknown"
        os_image = "unknown"
        container_runtime = "unknown"

        if node_info:

            kubernetes_version = (
                node_info.kubelet_version
                or "unknown"
            )

            architecture = (
                node_info.architecture
                or "unknown"
            )

            operating_system = (
                node_info.operating_system
                or "unknown"
            )

            os_image = (
                node_info.os_image
                or "unknown"
            )

            container_runtime = (
                node_info.container_runtime_version
                or "unknown"
            )

        # ----------------------------------------------------
        # Node roles
        # ----------------------------------------------------

        labels = (
            node.metadata.labels or {}
        )

        roles = []

        for key in labels:

            if key.startswith(
                "node-role.kubernetes.io/"
            ):

                role = key.split(
                    "/",
                    1,
                )[1]

                roles.append(role)

        # Old Kubernetes label format.
        if not roles:

            legacy_role = labels.get(
                "kubernetes.io/role"
            )

            if legacy_role:

                roles.append(
                    legacy_role
                )

        # ----------------------------------------------------
        # Capacity
        # ----------------------------------------------------

        capacity = (
            node.status.capacity or {}
        )

        cpu_capacity = capacity.get(
            "cpu",
            "0",
        )

        memory_capacity = capacity.get(
            "memory",
            "0",
        )

        pod_capacity = capacity.get(
            "pods",
            "0",
        )

        # ----------------------------------------------------
        # Pod count
        # ----------------------------------------------------

        node_pod_count = pods_per_node.get(
            node_name,
            0,
        )

        # ----------------------------------------------------
        # Device payload
        # ----------------------------------------------------

        payload = {
            "name": node_name,

            "cluster": CLUSTER_NAME,

            "kind": "kubernetes-node",

            "status": status,

            "environment": "production",

            "location": internal_ip,

            "kubernetes_version": (
                kubernetes_version
            ),

            "internal_ip": internal_ip,

            "architecture": architecture,

            "operating_system": (
                operating_system
            ),

            "os_image": os_image,

            "container_runtime": (
                container_runtime
            ),

            "roles": roles,

            "cpu_capacity": (
                cpu_capacity
            ),

            "memory_capacity": (
                memory_capacity
            ),

            "pod_capacity": (
                pod_capacity
            ),

            "pod_count": (
                node_pod_count
            ),

            "ready": ready,
        }

        response = api_post(
            "/api/devices",
            payload,
        )

        if response is None:

            continue

        if response.status_code in (
            200,
            201,
        ):

            print(
                f"Node registered/updated: "
                f"{node_name} "
                f"IP={internal_ip} "
                f"status={status} "
                f"pods={node_pod_count}",
                flush=True,
            )

        else:

            print(
                f"Node registration failed: "
                f"{node_name} "
                f"{response.status_code} "
                f"{response.text}",
                flush=True,
            )


# ============================================================
# Kubernetes Metrics
# ============================================================

def get_node_metrics():

    metrics = {}

    try:

        custom_api = (
            client.CustomObjectsApi()
        )

        result = (
            custom_api.list_cluster_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                plural="nodes",
            )
        )

        for item in result.get(
            "items",
            [],
        ):

            node_name = (
                item
                .get("metadata", {})
                .get("name")
            )

            usage = (
                item
                .get("usage", {})
            )

            cpu = usage.get(
                "cpu",
                "0",
            )

            memory = usage.get(
                "memory",
                "0",
            )

            metrics[node_name] = {
                "cpu": cpu,
                "memory": memory,
            }

        print(
            f"Metrics Server returned "
            f"{len(metrics)} nodes",
            flush=True,
        )

    except Exception as exc:

        print(
            f"Metrics API unavailable: {exc}",
            flush=True,
        )

    return metrics


# ============================================================
# CPU Conversion
# ============================================================

def cpu_to_millicores(
    value,
):

    try:

        value = str(value)

        if value.endswith("n"):

            return (
                float(
                    value[:-1]
                )
                / 1_000_000
            )

        if value.endswith("u"):

            return (
                float(
                    value[:-1]
                )
                / 1_000
            )

        if value.endswith("m"):

            return float(
                value[:-1]
            )

        return float(value) * 1000

    except Exception:

        return 0


# ============================================================
# Memory Conversion
# ============================================================

def memory_to_bytes(
    value,
):

    try:

        value = str(value)

        units = {
            "Ki": 1024,
            "Mi": 1024 ** 2,
            "Gi": 1024 ** 3,
            "Ti": 1024 ** 4,
            "K": 1000,
            "M": 1000 ** 2,
            "G": 1000 ** 3,
            "T": 1000 ** 4,
        }

        for unit, multiplier in (
            units.items()
        ):

            if value.endswith(unit):

                return (
                    float(
                        value[
                            :-len(unit)
                        ]
                    )
                    * multiplier
                )

        return float(value)

    except Exception:

        return 0


# ============================================================
# Calculate CPU / Memory Usage (from Metrics Server)
# ============================================================

def calculate_usage(
    nodes,
    node_metrics,
):
    """
    Calculate cluster-wide CPU and memory usage percentages.
    Returns (cpu_percent, memory_percent, metrics_available).
    metrics_available=True only when the Metrics Server provided
    actual usage data for at least one node.
    """

    total_cpu_used = 0
    total_cpu_capacity = 0
    total_memory_used = 0
    total_memory_capacity = 0
    nodes_with_metrics = 0

    for node in nodes:

        node_name = (
            node.metadata.name
        )

        capacity = (
            node.status.capacity or {}
        )

        cpu_capacity = capacity.get(
            "cpu",
            "0",
        )

        memory_capacity = capacity.get(
            "memory",
            "0",
        )

        total_cpu_capacity += (
            cpu_to_millicores(
                cpu_capacity
            )
        )

        total_memory_capacity += (
            memory_to_bytes(
                memory_capacity
            )
        )

        metrics = node_metrics.get(
            node_name
        )

        if not metrics:
            continue

        nodes_with_metrics += 1

        total_cpu_used += (
            cpu_to_millicores(
                metrics["cpu"]
            )
        )

        total_memory_used += (
            memory_to_bytes(
                metrics["memory"]
            )
        )

    cpu_percent = 0
    memory_percent = 0
    metrics_available = nodes_with_metrics > 0

    if total_cpu_capacity > 0 and metrics_available:

        cpu_percent = (
            total_cpu_used
            / total_cpu_capacity
            * 100
        )

    if total_memory_capacity > 0 and metrics_available:

        memory_percent = (
            total_memory_used
            / total_memory_capacity
            * 100
        )

    return (
        round(cpu_percent, 2),
        round(memory_percent, 2),
        metrics_available,
    )


# ============================================================
# Allocatable-based fallback usage estimate
# ============================================================

def calculate_usage_from_allocatable(
    nodes,
):
    """
    Fallback: estimate usage from (capacity - allocatable) / capacity.
    This reflects how much has been *reserved* by the scheduler, not
    actual runtime usage, but is much better than always showing 0%.
    Returns (cpu_percent, memory_percent).
    """

    total_cpu_capacity = 0
    total_cpu_reserved = 0
    total_memory_capacity = 0
    total_memory_reserved = 0

    for node in nodes:

        capacity = node.status.capacity or {}
        allocatable = node.status.allocatable or {}

        cpu_cap = cpu_to_millicores(
            capacity.get("cpu", "0")
        )
        mem_cap = memory_to_bytes(
            capacity.get("memory", "0")
        )

        cpu_alloc = cpu_to_millicores(
            allocatable.get("cpu", "0")
        )
        mem_alloc = memory_to_bytes(
            allocatable.get("memory", "0")
        )

        total_cpu_capacity += cpu_cap
        total_memory_capacity += mem_cap

        # Reserved = capacity minus what is still freely allocatable
        total_cpu_reserved += max(0, cpu_cap - cpu_alloc)
        total_memory_reserved += max(0, mem_cap - mem_alloc)

    cpu_percent = 0
    memory_percent = 0

    if total_cpu_capacity > 0:
        cpu_percent = (
            total_cpu_reserved / total_cpu_capacity * 100
        )

    if total_memory_capacity > 0:
        memory_percent = (
            total_memory_reserved / total_memory_capacity * 100
        )

    return (
        round(cpu_percent, 2),
        round(memory_percent, 2),
    )


# ============================================================
# Main Collection
# ============================================================

def collect():

    v1 = client.CoreV1Api()

    apps = client.AppsV1Api()

    print(
        "Collecting Kubernetes information...",
        flush=True,
    )

    # --------------------------------------------------------
    # Discover all Kubernetes nodes
    # --------------------------------------------------------

    nodes = (
        v1
        .list_node()
        .items
    )

    # --------------------------------------------------------
    # Discover all pods
    # --------------------------------------------------------

    pods = (
        v1
        .list_pod_for_all_namespaces()
        .items
    )

    # --------------------------------------------------------
    # Discover PVCs
    # --------------------------------------------------------

    pvcs = (
        v1
        .list_persistent_volume_claim_for_all_namespaces()
        .items
    )

    # --------------------------------------------------------
    # Discover deployments
    # --------------------------------------------------------

    deployments = (
        apps
        .list_deployment_for_all_namespaces()
        .items
    )

    node_total = len(nodes)

    pod_total = len(pods)

    pvc_total = len(pvcs)

    deployment_total = len(
        deployments
    )

    # --------------------------------------------------------
    # Ready nodes
    # --------------------------------------------------------

    ready_nodes = 0

    for node in nodes:

        if node_is_ready(node):

            ready_nodes += 1

    # --------------------------------------------------------
    # Cluster status
    # --------------------------------------------------------

    if not nodes:

        cluster_status = "warning"

    elif ready_nodes == node_total:

        cluster_status = "healthy"

    else:

        cluster_status = "warning"

    # --------------------------------------------------------
    # Kubernetes version
    # --------------------------------------------------------

    kubernetes_version = "unknown"

    if nodes:

        node_info = (
            nodes[0]
            .status
            .node_info
        )

        if node_info:

            kubernetes_version = (
                node_info.kubelet_version
                or "unknown"
            )

    # --------------------------------------------------------
    # Register / update cluster
    # --------------------------------------------------------

    register_cluster(
        kubernetes_version,
        node_total,
    )

    # --------------------------------------------------------
    # Register / update ALL nodes
    # --------------------------------------------------------

    register_nodes(
        nodes,
        pods,
    )

    # --------------------------------------------------------
    # CPU / Memory
    # --------------------------------------------------------

    node_metrics = (
        get_node_metrics()
    )

    cpu_percent, memory_percent, metrics_available = (
        calculate_usage(
            nodes,
            node_metrics,
        )
    )

    # Fallback: use allocatable-based estimate when Metrics Server is
    # not available, so the UI never shows a misleading 0%.
    if not metrics_available and nodes:

        print(
            "Metrics Server unavailable — "
            "using allocatable-based estimate for CPU/MEM",
            flush=True,
        )

        cpu_percent, memory_percent = (
            calculate_usage_from_allocatable(nodes)
        )

        print(
            f"  allocatable estimate: "
            f"cpu={cpu_percent}% mem={memory_percent}%",
            flush=True,
        )

    # --------------------------------------------------------
    # Disk
    # --------------------------------------------------------

    # Disk requires node-exporter or a dedicated filesystem
    # metrics source (e.g. Prometheus node_filesystem metrics).
    disk_percent = 0

    # --------------------------------------------------------
    # Prometheus metrics
    # --------------------------------------------------------

    node_count.set(
        node_total
    )

    ready_node_count.set(
        ready_nodes
    )

    pod_count.set(
        pod_total
    )

    pvc_count.set(
        pvc_total
    )

    deployment_count.set(
        deployment_total
    )

    # --------------------------------------------------------
    # Telemetry
    # --------------------------------------------------------

    payload = {
        "cluster": CLUSTER_NAME,

        "cpu": cpu_percent,

        "memory": memory_percent,

        "disk": disk_percent,

        "pods": pod_total,

        "status": cluster_status,

        "node_count": node_total,

        "ready_nodes": ready_nodes,

        "deployment_count": deployment_total,

        "pvc_count": pvc_total,

        "metrics_available": metrics_available,
    }

    response = api_post(
        "/api/telemetry",
        payload,
    )

    if response is not None:

        if response.status_code in (
            200,
            201,
            202,
        ):

            print(
                "Telemetry sent successfully",
                flush=True,
            )

            print(
                f"  cluster={CLUSTER_NAME}",
                flush=True,
            )

            print(
                f"  nodes={node_total}",
                flush=True,
            )

            print(
                f"  ready_nodes={ready_nodes}",
                flush=True,
            )

            print(
                f"  pods={pod_total}",
                flush=True,
            )

            print(
                f"  deployments={deployment_total}",
                flush=True,
            )

            print(
                f"  pvcs={pvc_total}",
                flush=True,
            )

            print(
                f"  cpu={cpu_percent}%",
                flush=True,
            )

            print(
                f"  memory={memory_percent}%",
                flush=True,
            )

            print(
                f"  status={cluster_status}",
                flush=True,
            )

        else:

            print(
                f"Telemetry failed: "
                f"{response.status_code} "
                f"{response.text}",
                flush=True,
            )


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":

    print(
        "========================================",
        flush=True,
    )

    print(
        "EdgeOps Kubernetes Agent",
        flush=True,
    )

    print(
        "========================================",
        flush=True,
    )

    print(
        f"Cluster: {CLUSTER_NAME}",
        flush=True,
    )

    print(
        f"EdgeOps API: {AGENT_API}",
        flush=True,
    )

    print(
        f"Collection interval: {INTERVAL}s",
        flush=True,
    )

    print(
        "========================================",
        flush=True,
    )

    # Prometheus endpoint.
    start_http_server(
        8002
    )

    # Kubernetes authentication.
    load_kube()

    # Continuous collection.
    while True:

        try:

            collect()

        except Exception as exc:

            print(
                f"Collection failed: {exc}",
                flush=True,
            )

        time.sleep(
            INTERVAL
        )