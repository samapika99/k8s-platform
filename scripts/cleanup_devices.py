#!/usr/bin/env python3
"""
cleanup_devices.py
------------------
Removes duplicate device records from MongoDB.
Keeps only the most-recently-updated document for each (cluster, name) pair.
Run once after deploying the fix to clear the 9437-record bloat.
"""
import os
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "edgeops")

mongo = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = mongo[MONGO_DB]
devices = db.devices

total_before = devices.count_documents({})
print(f"Devices before cleanup: {total_before}")

# Find all unique (cluster, name) combos
pipeline = [
    {"$sort": {"updated_at": -1}},
    {
        "$group": {
            "_id": {"cluster": "$cluster", "name": "$name"},
            "keep_id": {"$first": "$_id"},
            "count": {"$sum": 1},
        }
    },
    {"$match": {"count": {"$gt": 1}}},
]

duplicates = list(devices.aggregate(pipeline))
print(f"Duplicate (cluster, name) pairs found: {len(duplicates)}")

deleted_total = 0
for dup in duplicates:
    keep_id = dup["keep_id"]
    cluster = dup["_id"]["cluster"]
    name = dup["_id"]["name"]

    result = devices.delete_many(
        {
            "cluster": cluster,
            "name": name,
            "_id": {"$ne": keep_id},
        }
    )
    deleted_total += result.deleted_count
    print(f"  Kept {keep_id} | deleted {result.deleted_count} duplicates of {name}@{cluster}")

total_after = devices.count_documents({})
print(f"\nDeleted {deleted_total} duplicate records.")
print(f"Devices after cleanup: {total_after}")
