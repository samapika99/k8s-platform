import json
import os
from datetime import datetime, timezone

from kafka import KafkaConsumer
from prometheus_client import Counter, Gauge, start_http_server
from pymongo import MongoClient

processed = Counter("edgeops_telemetry_processed_total", "Telemetry events processed")
created = Counter("edgeops_incidents_created_total", "Incidents created")
consumer_lag = Gauge("edgeops_worker_last_event_timestamp", "Timestamp of last processed event")

mongo = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
db = mongo[os.getenv("MONGO_DB", "edgeops")]
clusters = db.clusters
telemetry = db.telemetry
incidents = db.incidents

consumer = KafkaConsumer(
    "cluster.telemetry",
    bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP", "localhost:9092"),
    group_id="edgeops-telemetry-worker",
    auto_offset_reset="earliest",
    value_deserializer=lambda value: json.loads(value),
)


def now():
    return datetime.now(timezone.utc)


def evaluate(event):
    if event["disk"] >= 90:
        return "critical", "Storage usage exceeded 90%"
    if event["memory"] >= 90:
        return "critical", "Memory usage exceeded 90%"
    if event["cpu"] >= 90:
        return "warning", "CPU usage exceeded 90%"
    if event["disk"] >= 80:
        return "warning", "Storage usage exceeded 80%"
    return None, None


def process(event):
    event["processed_at"] = now()
    telemetry.insert_one(event)

    clusters.update_one(
        {"name": event["cluster"]},
        {"$set": {
            "status": event["status"],
            "last_seen": now(),
            "cpu": event["cpu"],
            "memory": event["memory"],
            "disk": event["disk"],
            "pods": event["pods"],
        }},
        upsert=True,
    )

    severity, reason = evaluate(event)

    if severity:
        # Basic deduplication: do not create another open incident for the same
        # cluster/reason within the same active state.
        existing = incidents.find_one({
            "cluster": event["cluster"],
            "reason": reason,
            "status": {"$ne": "resolved"},
        })
        if not existing:
            incidents.insert_one({
                "cluster": event["cluster"],
                "severity": severity,
                "reason": reason,
                "status": "open",
                "created_at": now(),
            })
            created.inc()

    processed.inc()


if __name__ == "__main__":
    start_http_server(8001)
    for message in consumer:
        process(message.value)
