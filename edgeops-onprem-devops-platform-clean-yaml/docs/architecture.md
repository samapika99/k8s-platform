# Architecture and design decisions

## Why MongoDB?

The control plane stores flexible operational objects:
clusters, nodes, devices, incidents, audit events and telemetry.

## Why Kafka?

Telemetry is asynchronous and bursty. Kafka decouples agents from consumers and provides replayability.

## Why Redis?

Redis provides low-latency cache/rate-limit/session state without turning MongoDB into the hot-path cache.

## Why an agent?

The control plane should not require direct privileged access to every Kubernetes API server. The agent acts as the site-side collector.

## Why Argo CD?

Git is the deployment source of truth. Argo CD continuously reconciles Kubernetes state.

## Why Helm?

The same application can be parameterized for dev, staging and production.

## Single-node design

The first version deliberately runs on one MicroK8s node. This is a learning/portfolio environment, not a HA claim.

## Future multi-cluster design

Each remote cluster runs an agent with:

- cluster identity
- registration token
- outbound TLS
- telemetry buffering
- local retry
- least-privilege RBAC

The central API can then maintain thousands of cluster records without requiring inbound access to customer clusters.
