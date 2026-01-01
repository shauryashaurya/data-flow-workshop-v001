import json
import os
import random
import uuid
from datetime import datetime, timedelta, timezone

from faker import Faker

# Config block: edit values here
CONFIG = {
    "base_dir": "./data",
    "subdirs": {
        "obs_raw": "obs/raw",
        "obs_contracts": "obs/contracts",
        "obs_curated": "obs/curated",
    },
    "seed": 11,
    "volumes": {
        "bulletins": 2000,
        "provenance": 5000,
        "kpis": 300,
        "alerts": 50,
        "days": 2,
    },
    "flows": ["ingest_validate", "enrich_post", "dlq_replay", "observability_plane"],
    "nodes": ["n1", "n2", "n3"],
}

ISO_UTC_FMT = "%Y-%m-%dT%H:%M:%SZ"

CONTRACTS = {
    "version": "1.0",
    "datasets": {
        "nifi_bulletins": {
            "path": "obs/raw/nifi_bulletins.jsonl",
            "required": ["event_time", "node_id", "group_id", "component_id", "component_type", "bulletin_level", "category", "message"],
        },
        "nifi_provenance": {
            "path": "obs/raw/nifi_provenance.jsonl",
            "required": ["event_time", "node_id", "flowfile_uuid", "event_type", "component_id", "file_size", "attributes"],
        },
        "flow_kpis": {
            "path": "obs/raw/flow_kpis.jsonl",
            "required": ["window_start", "window_end", "flow_name", "metric_name", "metric_value", "dimensions"],
        },
        "alerts": {
            "path": "obs/raw/alerts.jsonl",
            "required": ["alert_time", "alert_type", "severity", "signal", "context"],
        },
    },
}


def iso_utc(dt):
    return dt.astimezone(timezone.utc).strftime(ISO_UTC_FMT)


def ensure_dirs(base_dir, subdirs):
    os.makedirs(base_dir, exist_ok=True)
    for _, rel in subdirs.items():
        os.makedirs(os.path.join(base_dir, rel), exist_ok=True)


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(
                ",", ":"), ensure_ascii=False) + "\n")


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def yaml_escape(s):
    if s is None:
        return "null"
    if isinstance(s, bool):
        return "true" if s else "false"
    if isinstance(s, (int, float)):
        return str(s)
    if isinstance(s, str):
        needs_quotes = any(c in s for c in [":", "{", "}", "[", "]", ",", "#", "&", "*", "!",
                           "|", ">", "%", "@", "`", "\"", "'"]) or s.strip() != s or s == "" or "\n" in s
        if needs_quotes:
            return "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"") + "\""
        return s
    return "\"" + str(s).replace("\\", "\\\\").replace("\"", "\\\"") + "\""


def to_yaml(obj, indent=0):
    sp = "  " * indent
    if isinstance(obj, dict):
        lines = []
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                lines.append(f"{sp}{k}:")
                lines.append(to_yaml(v, indent + 1))
            else:
                lines.append(f"{sp}{k}: {yaml_escape(v)}")
        return "\n".join(lines)
    if isinstance(obj, list):
        lines = []
        for v in obj:
            if isinstance(v, (dict, list)):
                lines.append(f"{sp}-")
                lines.append(to_yaml(v, indent + 1))
            else:
                lines.append(f"{sp}- {yaml_escape(v)}")
        return "\n".join(lines)
    return f"{sp}{yaml_escape(obj)}"


def write_yaml(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        f.write(to_yaml(obj) + "\n")


def main():
    base_dir = CONFIG["base_dir"]
    subdirs = CONFIG["subdirs"]
    rng = random.Random(CONFIG["seed"])
    Faker.seed(CONFIG["seed"])
    fake = Faker()

    ensure_dirs(base_dir, subdirs)

    raw_dir = os.path.join(base_dir, subdirs["obs_raw"])
    contracts_dir = os.path.join(base_dir, subdirs["obs_contracts"])

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=CONFIG["volumes"]["days"])

    flowfile_uuids = [str(uuid.uuid4()) for _ in range(2000)]
    trace_pool = [{
        "trace.correlation_id": str(uuid.uuid4()),
        "trace.transaction_id": str(uuid.uuid4()),
        "trace.idempotency_key": f"k:{uuid.uuid4().hex[:12]}",
        "schema_version": "1.0",
    } for _ in range(1000)]

    bulletin_levels = ["INFO", "WARN", "ERROR"]
    event_types = ["RECEIVE", "FETCH", "ROUTE",
                   "CONTENT_MODIFIED", "SEND", "DROP", "FORK", "JOIN", "CLONE"]
    component_types = ["Processor", "ControllerService", "ReportingTask"]

    bulletins = []
    for _ in range(CONFIG["volumes"]["bulletins"]):
        t = start + timedelta(seconds=rng.randint(0,
                              int((now - start).total_seconds())))
        trace = rng.choice(trace_pool) if rng.random() < 0.6 else {}
        bulletins.append({
            "event_time": iso_utc(t),
            "node_id": rng.choice(CONFIG["nodes"]),
            "group_id": str(uuid.uuid4()),
            "component_id": str(uuid.uuid4()),
            "component_type": rng.choice(component_types),
            "bulletin_level": rng.choices(bulletin_levels, weights=[70, 20, 10], k=1)[0],
            "category": rng.choice(["Backpressure", "Repository", "Security", "FlowFile", "Processor"]),
            "message": fake.sentence(nb_words=10),
            "trace.correlation_id": trace.get("trace.correlation_id"),
            "trace.transaction_id": trace.get("trace.transaction_id"),
            "trace.idempotency_key": trace.get("trace.idempotency_key"),
        })

    provenance = []
    for _ in range(CONFIG["volumes"]["provenance"]):
        t = start + timedelta(seconds=rng.randint(0,
                              int((now - start).total_seconds())))
        ff = rng.choice(flowfile_uuids)
        trace = rng.choice(trace_pool) if rng.random() < 0.8 else {
            "schema_version": "1.0"}
        provenance.append({
            "event_time": iso_utc(t),
            "node_id": rng.choice(CONFIG["nodes"]),
            "flowfile_uuid": ff,
            "event_type": rng.choice(event_types),
            "component_id": str(uuid.uuid4()),
            "transit_uri": rng.choice([None, "file://data", "s2s://nifi", "https://sink/api"]),
            "file_size": rng.randint(50, 250000),
            "attributes": trace,
        })

    kpis = []
    for _ in range(CONFIG["volumes"]["kpis"]):
        w_end = start + \
            timedelta(seconds=rng.randint(
                0, int((now - start).total_seconds())))
        w_start = w_end - timedelta(minutes=5)
        flow = rng.choice(CONFIG["flows"])
        metric = rng.choice(["postings_succeeded", "postings_failed", "dlq_count",
                            "queue_depth", "backpressure_engaged", "latency_ms_p95"])
        val = rng.uniform(
            0, 500) if metric != "backpressure_engaged" else rng.choice([0, 1])
        kpis.append({
            "window_start": iso_utc(w_start),
            "window_end": iso_utc(w_end),
            "flow_name": flow,
            "metric_name": metric,
            "metric_value": float(val),
            "dimensions": {"env": "dev", "cluster": "c1"},
        })

    alerts = []
    for _ in range(CONFIG["volumes"]["alerts"]):
        t = start + timedelta(seconds=rng.randint(0,
                              int((now - start).total_seconds())))
        trace = rng.choice(trace_pool) if rng.random() < 0.4 else {}
        alerts.append({
            "alert_time": iso_utc(t),
            "alert_type": rng.choice(["stall_detected", "error_rate_high", "dlq_rate_high", "backpressure_engaged"]),
            "severity": rng.choice(["LOW", "MEDIUM", "HIGH"]),
            "signal": {"value": rng.uniform(0, 1), "window_minutes": 5},
            "context": {
                "flow_name": rng.choice(CONFIG["flows"]),
                "node_id": rng.choice(CONFIG["nodes"]),
                "component_id": str(uuid.uuid4()),
                "trace.correlation_id": trace.get("trace.correlation_id"),
                "trace.transaction_id": trace.get("trace.transaction_id"),
            },
        })

    write_jsonl(os.path.join(raw_dir, "nifi_bulletins.jsonl"), bulletins)
    write_jsonl(os.path.join(raw_dir, "nifi_provenance.jsonl"), provenance)
    write_jsonl(os.path.join(raw_dir, "flow_kpis.jsonl"), kpis)
    write_jsonl(os.path.join(raw_dir, "alerts.jsonl"), alerts)

    write_json(os.path.join(contracts_dir,
               "observability_contracts.json"), CONTRACTS)
    write_yaml(os.path.join(contracts_dir,
               "observability_contracts.yaml"), CONTRACTS)


if __name__ == "__main__":
    main()
