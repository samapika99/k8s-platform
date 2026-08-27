import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from fastapi import FastAPI, HTTPException, Query
from kafka import KafkaProducer
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field
from pymongo import MongoClient
from redis import Redis


# ============================================================
# Configuration
# ============================================================

MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb://mongodb:27017",
)

MONGO_DB = os.getenv(
    "MONGO_DB",
    "edgeops",
)

KAFKA_BOOTSTRAP = os.getenv(
    "KAFKA_BOOTSTRAP",
    "kafka:9092",
)

REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://redis:6379",
)


# ============================================================
# MongoDB
# ============================================================

mongo = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=3000,
)

db = mongo[MONGO_DB]

clusters = db.clusters
devices = db.devices
telemetry = db.telemetry
incidents = db.incidents
audit = db.audit_logs


# ============================================================
# FastAPI
# ============================================================

app = FastAPI(
    title="EdgeOps API",
    version="1.0.0",
)

Instrumentator().instrument(app).expose(app)


# ============================================================
# Redis
# ============================================================

redis_client = Redis.from_url(
    REDIS_URL,
    socket_timeout=2,
)


# ============================================================
# Kafka
# ============================================================

producer = KafkaProducer(
    bootstrap_servers=KAFKA_BOOTSTRAP,
    value_serializer=lambda value: json.dumps(
        value,
        default=str,
    ).encode(),
    request_timeout_ms=3000,
)


# ============================================================
# Models
# ============================================================

class ClusterIn(BaseModel):
    name: str = Field(
        min_length=2,
        max_length=100,
    )

    environment: str = "production"

    location: str = "unknown"

    kubernetes_version: str = "unknown"


class DeviceIn(BaseModel):
    name: str = Field(
        min_length=2,
        max_length=100,
    )

    cluster: str

    kind: str = "kubernetes-node"

    status: str = "unknown"

    environment: str = "production"

    location: str = "unknown"

    kubernetes_version: str = "unknown"

    internal_ip: str = "unknown"

    architecture: str = "unknown"

    operating_system: str = "unknown"

    os_image: str = "unknown"

    container_runtime: str = "unknown"

    roles: list[str] = []

    cpu_capacity: str = "0"

    memory_capacity: str = "0"

    pod_capacity: str = "0"

    pod_count: int = 0

    ready: bool = False

    metrics_available: bool = False

    cpu_percent: float = 0.0

    memory_percent: float = 0.0


class TelemetryIn(BaseModel):
    cluster: str

    cpu: float = Field(
        ge=0,
        le=100,
    )

    memory: float = Field(
        ge=0,
        le=100,
    )

    disk: float = Field(
        ge=0,
        le=100,
    )

    pods: int = Field(
        ge=0,
    )

    status: str = "healthy"

    node_count: int = 0

    ready_nodes: int = 0

    deployment_count: int = 0

    pvc_count: int = 0

    metrics_available: bool = False


# ============================================================
# Helpers
# ============================================================

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def serialize_value(value: Any) -> Any:

    if isinstance(value, ObjectId):
        return str(value)

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, dict):
        return {
            key: serialize_value(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            serialize_value(item)
            for item in value
        ]

    return value


def serialize_document(
    document: dict[str, Any],
) -> dict[str, Any]:
    """Serialize a MongoDB document, renaming _id → id."""
    result = {}
    for key, value in document.items():
        # Rename MongoDB's _id to id for the frontend
        out_key = "id" if key == "_id" else key
        result[out_key] = serialize_value(value)
    return result


def write_audit(
    action: str,
    resource: str,
    detail: Any,
):

    audit.insert_one(
        {
            "action": action,
            "resource": resource,
            "detail": serialize_value(detail),
            "created_at": utcnow(),
        }
    )


# ============================================================
# Database Initialization
# ============================================================

def initialize_database():

    mongo.admin.command("ping")

    required_collections = [
        "clusters",
        "devices",
        "telemetry",
        "incidents",
        "audit_logs",
    ]

    existing_collections = set(
        db.list_collection_names()
    )

    for collection_name in required_collections:

        if collection_name not in existing_collections:

            db.create_collection(
                collection_name
            )

    # One cluster per name.
    clusters.create_index(
        "name",
        unique=True,
    )

    # One device per cluster + node name.
    devices.create_index(
        [
            ("cluster", 1),
            ("name", 1),
        ],
        unique=True,
    )

    incidents.create_index(
        "status"
    )

    incidents.create_index(
        "severity"
    )

    telemetry.create_index(
        "cluster"
    )

    telemetry.create_index(
        "received_at"
    )

    audit.create_index(
        "created_at"
    )

    print(
        f"MongoDB initialized successfully: "
        f"database={MONGO_DB}",
        flush=True,
    )


@app.on_event("startup")
def startup():

    initialize_database()


# ============================================================
# Health
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "ok",
        "service": "api",
    }


@app.get("/ready")
def ready():

    mongo.admin.command("ping")

    redis_client.ping()

    producer.bootstrap_connected()

    return {
        "status": "ready",
    }


# ============================================================
# Clusters
# ============================================================

@app.post(
    "/api/clusters",
    status_code=201,
)
def create_cluster(
    payload: ClusterIn,
):

    now = utcnow()

    document = {
        "name": payload.name,
        "environment": payload.environment,
        "location": payload.location,
        "kubernetes_version": payload.kubernetes_version,
        "status": "unknown",
        "created_at": now,
        "last_seen": now,
    }

    result = clusters.update_one(
        {
            "name": payload.name,
        },
        {
            "$set": {
                "environment": payload.environment,
                "location": payload.location,
                "kubernetes_version": payload.kubernetes_version,
                "last_seen": now,
            },
            "$setOnInsert": {
                "created_at": now,
                "status": "unknown",
            },
        },
        upsert=True,
    )

    existing = clusters.find_one(
        {
            "name": payload.name,
        }
    )

    if result.upserted_id:

        write_audit(
            "cluster.created",
            str(result.upserted_id),
            document,
        )

    return serialize_document(
        existing
    )


@app.get("/api/clusters")
def list_clusters():

    docs = clusters.find().sort(
        "last_seen",
        -1,
    )

    return [
        serialize_document(document)
        for document in docs
    ]


# ============================================================
# Devices / Kubernetes Nodes
# ============================================================

@app.post(
    "/api/devices",
    status_code=201,
)
def create_device(
    payload: DeviceIn,
):

    now = utcnow()

    document = {
        **payload.model_dump(),
        "updated_at": now,
    }

    result = devices.update_one(
        {
            "name": payload.name,
            "cluster": payload.cluster,
        },
        {
            "$set": document,
            "$setOnInsert": {
                "created_at": now,
            },
        },
        upsert=True,
    )

    existing = devices.find_one(
        {
            "name": payload.name,
            "cluster": payload.cluster,
        }
    )

    write_audit(
        "device.updated",
        payload.name,
        document,
    )

    return serialize_document(
        existing
    )


@app.get("/api/devices")
def list_devices(
    cluster: Optional[str] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    skip: int = Query(default=0, ge=0),
):
    """List Kubernetes nodes (devices). Supports filtering by cluster and pagination."""

    query: dict[str, Any] = {}
    if cluster:
        query["cluster"] = cluster

    docs = (
        devices.find(query)
        .sort("updated_at", -1)
        .skip(skip)
        .limit(limit)
    )

    total = devices.count_documents(query)

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [
            serialize_document(document)
            for document in docs
        ],
    }


@app.get("/api/nodes")
def list_nodes(
    cluster: Optional[str] = Query(default=None),
):
    """Return latest node info per cluster, with deduplication."""

    pipeline: list[Any] = []

    if cluster:
        pipeline.append({"$match": {"cluster": cluster}})

    pipeline += [
        {"$sort": {"updated_at": -1}},
        {
            "$group": {
                "_id": {"cluster": "$cluster", "name": "$name"},
                "doc": {"$first": "$$ROOT"},
            }
        },
        {"$replaceRoot": {"newRoot": "$doc"}},
        {"$sort": {"cluster": 1, "name": 1}},
    ]

    docs = list(devices.aggregate(pipeline))

    return [serialize_document(d) for d in docs]


# ============================================================
# Telemetry
# ============================================================

@app.post(
    "/api/telemetry",
    status_code=202,
)
def publish_telemetry(
    payload: TelemetryIn,
):

    now = utcnow()

    event = {
        **payload.model_dump(),
        "received_at": now,
    }

    # Update cluster dynamically.
    clusters.update_one(
        {
            "name": payload.cluster,
        },
        {
            "$set": {
                "status": payload.status,
                "cpu": payload.cpu,
                "memory": payload.memory,
                "disk": payload.disk,
                "pods": payload.pods,
                "node_count": payload.node_count,
                "ready_nodes": payload.ready_nodes,
                "deployment_count": payload.deployment_count,
                "pvc_count": payload.pvc_count,
                "metrics_available": payload.metrics_available,
                "last_seen": now,
            },
            "$setOnInsert": {
                "name": payload.cluster,
                "environment": "production",
                "location": "on-prem",
                "kubernetes_version": "unknown",
                "created_at": now,
            },
        },
        upsert=True,
    )

    # Store telemetry in MongoDB.
    telemetry.insert_one(
        event
    )

    # Publish to Kafka.
    producer.send(
        "cluster.telemetry",
        event,
    )

    producer.flush(
        timeout=3
    )

    return {
        "status": "accepted",
        "cluster": payload.cluster,
    }


# ============================================================
# Deployments
# ============================================================

@app.get("/api/deployments")
def list_deployments(
    cluster: Optional[str] = Query(default=None),
):
    """
    Return deployment summary per cluster from the latest telemetry snapshot.
    Each entry shows cluster name, deployment_count, pod count, pvc count,
    kubernetes_version, and last_seen timestamp.
    """
    query: dict[str, Any] = {}
    if cluster:
        query["name"] = cluster

    docs = clusters.find(
        query,
        {
            "name": 1,
            "kubernetes_version": 1,
            "deployment_count": 1,
            "pods": 1,
            "pvc_count": 1,
            "node_count": 1,
            "ready_nodes": 1,
            "status": 1,
            "last_seen": 1,
            "environment": 1,
            "location": 1,
        },
    ).sort("last_seen", -1)

    return [serialize_document(d) for d in docs]


# ============================================================
# Incidents
# ============================================================

@app.get("/api/incidents")
def list_incidents():

    docs = incidents.find().sort(
        "created_at",
        -1,
    ).limit(100)

    return [
        serialize_document(document)
        for document in docs
    ]


@app.post(
    "/api/incidents/{incident_id}/ack"
)
def acknowledge(
    incident_id: str,
):

    try:

        oid = ObjectId(
            incident_id
        )

    except Exception:

        raise HTTPException(
            status_code=400,
            detail="Invalid incident id",
        )

    result = incidents.update_one(
        {
            "_id": oid,
            "status": "open",
        },
        {
            "$set": {
                "status": "acknowledged",
                "updated_at": utcnow(),
            }
        },
    )

    if result.matched_count == 0:

        raise HTTPException(
            status_code=404,
            detail="Open incident not found",
        )

    write_audit(
        "incident.acknowledged",
        incident_id,
        {},
    )

    return {
        "status": "acknowledged",
    }


@app.post(
    "/api/incidents/{incident_id}/resolve"
)
def resolve(
    incident_id: str,
):

    try:

        oid = ObjectId(
            incident_id
        )

    except Exception:

        raise HTTPException(
            status_code=400,
            detail="Invalid incident id",
        )

    result = incidents.update_one(
        {
            "_id": oid,
            "status": {
                "$ne": "resolved"
            },
        },
        {
            "$set": {
                "status": "resolved",
                "updated_at": utcnow(),
            }
        },
    )

    if result.matched_count == 0:

        raise HTTPException(
            status_code=404,
            detail="Incident not found",
        )

    write_audit(
        "incident.resolved",
        incident_id,
        {},
    )

    return {
        "status": "resolved",
    }


# ============================================================
# Audit Log
# ============================================================

@app.get("/api/audit")
def list_audit(
    limit: int = Query(default=50, ge=1, le=500),
    skip: int = Query(default=0, ge=0),
):
    """Return recent audit log entries, newest first."""

    docs = (
        audit.find()
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )

    total = audit.count_documents({})

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [
            serialize_document(document)
            for document in docs
        ],
    }


# ============================================================
# Dashboard Summary
# ============================================================

@app.get("/api/summary")
def summary():

    # Count distinct (cluster, name) pairs to get real unique node count
    pipeline = [
        {
            "$group": {
                "_id": {
                    "cluster": "$cluster",
                    "name": "$name",
                }
            }
        },
        {"$count": "unique_devices"},
    ]

    result = list(devices.aggregate(pipeline))
    unique_device_count = result[0]["unique_devices"] if result else 0

    return {
        "clusters": clusters.count_documents({}),

        "devices": unique_device_count,

        "active_incidents": incidents.count_documents(
            {
                "status": {
                    "$ne": "resolved"
                }
            }
        ),

        "critical_incidents": incidents.count_documents(
            {
                "status": {
                    "$ne": "resolved"
                },
                "severity": "critical",
            }
        ),
    }