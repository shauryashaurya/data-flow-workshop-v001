import csv
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
        "raw": "raw",
        "reference": "reference",
        "contracts": "contracts",
    },
    "seed": 7,
    "volumes": {
        "customers": 500,
        "accounts": 800,
        "merchants": 300,
        "transactions": 20000,
        "disputes": 200,
        "fx_days": 30,
    },
    "fx": {
        "base_ccy": "USD",
        "quote_ccys": ["USD", "EUR", "GBP", "INR", "SGD", "AED"],
    },
}

ISO_UTC_FMT = "%Y-%m-%dT%H:%M:%SZ"

RAW_TRANSACTIONS_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "raw_transactions",
    "type": "object",
    "additionalProperties": True,
    "required": [
        "transaction_id",
        "correlation_id",
        "event_time",
        "customer_id",
        "account_id",
        "merchant_id",
        "amount",
        "currency",
        "status",
        "idempotency_key",
    ],
    "properties": {
        "transaction_id": {"type": "string", "format": "uuid"},
        "correlation_id": {"type": "string", "format": "uuid"},
        "event_time": {"type": "string", "format": "date-time"},
        "customer_id": {"type": "string", "format": "uuid"},
        "account_id": {"type": "string", "format": "uuid"},
        "merchant_id": {"type": "string", "format": "uuid"},
        "channel": {"type": "string", "enum": ["CARD", "UPI", "ACH", "WIRE"]},
        "direction": {"type": "string", "enum": ["DEBIT", "CREDIT"]},
        "amount": {"type": "integer", "minimum": 0},
        "currency": {"type": "string", "minLength": 3, "maxLength": 3},
        "status": {"type": "string", "enum": ["AUTHORIZED", "CAPTURED", "SETTLED", "DECLINED"]},
        "auth_code": {"type": "string"},
        "card_last4": {"type": ["string", "null"], "pattern": "^[0-9]{4}$"},
        "device_id": {"type": "string"},
        "ip_address": {"type": "string"},
        "idempotency_key": {"type": "string"},
        "amount_base": {"type": ["integer", "null"], "minimum": 0},
        "base_currency": {"type": ["string", "null"], "minLength": 3, "maxLength": 3},
        "fx_rate": {"type": ["number", "null"]},
        "merchant_risk_tier": {"type": ["string", "null"], "enum": ["LOW", "MEDIUM", "HIGH", None]},
    },
}

RAW_DISPUTES_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "raw_disputes",
    "type": "object",
    "additionalProperties": True,
    "required": [
        "dispute_id",
        "correlation_id",
        "transaction_id",
        "opened_at",
        "reason_code",
        "status",
        "amount",
        "currency",
    ],
    "properties": {
        "dispute_id": {"type": "string", "format": "uuid"},
        "correlation_id": {"type": "string", "format": "uuid"},
        "transaction_id": {"type": "string", "format": "uuid"},
        "opened_at": {"type": "string", "format": "date-time"},
        "reason_code": {"type": "string", "enum": ["FRAUD", "NOT_RECEIVED", "DUPLICATE", "OTHER"]},
        "status": {"type": "string", "enum": ["OPEN", "WON", "LOST", "CLOSED"]},
        "amount": {"type": "integer", "minimum": 0},
        "currency": {"type": "string", "minLength": 3, "maxLength": 3},
    },
}

REFERENCE_CUSTOMERS_SCHEMA = {
    "title": "reference_customers",
    "type": "csv",
    "columns": [
        {"name": "customer_id", "type": "uuid", "required": True},
        {"name": "full_name", "type": "string", "required": True},
        {"name": "email", "type": "string", "required": True},
        {"name": "phone_e164", "type": "string", "required": True},
        {"name": "dob", "type": "date", "required": True},
        {"name": "kyc_level", "type": "enum", "values": [
            "BASIC", "STANDARD", "ENHANCED"], "required": True},
        {"name": "country", "type": "string", "required": True},
        {"name": "created_at", "type": "date-time", "required": True},
    ],
}

REFERENCE_ACCOUNTS_SCHEMA = {
    "title": "reference_accounts",
    "type": "csv",
    "columns": [
        {"name": "account_id", "type": "uuid", "required": True},
        {"name": "customer_id", "type": "uuid", "required": True},
        {"name": "account_type", "type": "enum", "values": [
            "WALLET", "CHECKING", "CREDIT"], "required": True},
        {"name": "status", "type": "enum", "values": [
            "ACTIVE", "SUSPENDED", "CLOSED"], "required": True},
        {"name": "base_currency", "type": "string", "required": True},
        {"name": "opened_at", "type": "date-time", "required": True},
    ],
}

REFERENCE_MERCHANTS_SCHEMA = {
    "title": "reference_merchants",
    "type": "csv",
    "columns": [
        {"name": "merchant_id", "type": "uuid", "required": True},
        {"name": "merchant_name", "type": "string", "required": True},
        {"name": "mcc", "type": "string", "required": True},
        {"name": "country", "type": "string", "required": True},
        {"name": "risk_tier", "type": "enum", "values": [
            "LOW", "MEDIUM", "HIGH"], "required": True},
        {"name": "created_at", "type": "date-time", "required": True},
    ],
}

REFERENCE_FX_RATES_SCHEMA = {
    "title": "reference_fx_rates",
    "type": "csv",
    "columns": [
        {"name": "rate_date", "type": "date", "required": True},
        {"name": "base_ccy", "type": "string", "required": True},
        {"name": "quote_ccy", "type": "string", "required": True},
        {"name": "rate", "type": "decimal", "required": True},
        {"name": "provider", "type": "string", "required": True},
    ],
}

QUALITY_RULES = {
    "raw_transactions": [
        {"rule": "amount is integer minor units",
            "check": "amount is int and amount >= 0"},
        {"rule": "currency length 3", "check": "len(currency) == 3"},
        {"rule": "correlation_id present", "check": "present and UUID-shaped"},
        {"rule": "idempotency_key present", "check": "present and non-empty"},
    ],
    "raw_disputes": [
        {"rule": "amount is integer minor units",
            "check": "amount is int and amount >= 0"},
        {"rule": "currency length 3", "check": "len(currency) == 3"},
        {"rule": "references transaction_id",
            "check": "transaction_id appears in raw transactions"},
    ],
}


def utc_now():
    return datetime.now(timezone.utc)


def iso_utc(dt):
    return dt.astimezone(timezone.utc).strftime(ISO_UTC_FMT)


def ensure_dirs(base_dir, subdirs):
    os.makedirs(base_dir, exist_ok=True)
    for _, rel in subdirs.items():
        os.makedirs(os.path.join(base_dir, rel), exist_ok=True)


def write_csv(path, fieldnames, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


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


def weighted_choice(rng, items):
    values = [v for v, _ in items]
    weights = [w for _, w in items]
    return rng.choices(values, weights=weights, k=1)[0]


def gen_fx_rates(rng, start_date, days, base_ccy, quote_ccys):
    providers = ["provider_a", "provider_b"]
    rows = []
    for i in range(days):
        d = start_date + timedelta(days=i)
        for q in quote_ccys:
            if q == base_ccy:
                continue
            rate = round(rng.uniform(0.2, 120.0), 6)
            rows.append({
                "rate_date": d.strftime("%Y-%m-%d"),
                "base_ccy": base_ccy,
                "quote_ccy": q,
                "rate": str(rate),
                "provider": rng.choice(providers),
            })
    return rows


def main():
    base_dir = CONFIG["base_dir"]
    subdirs = CONFIG["subdirs"]
    seed = CONFIG["seed"]
    vols = CONFIG["volumes"]
    fx_cfg = CONFIG["fx"]

    ensure_dirs(base_dir, subdirs)

    raw_dir = os.path.join(base_dir, subdirs["raw"])
    ref_dir = os.path.join(base_dir, subdirs["reference"])
    contracts_dir = os.path.join(base_dir, subdirs["contracts"])

    rng = random.Random(seed)
    Faker.seed(seed)
    fake = Faker()

    countries = ["US", "IN", "GB", "SG", "AE", "DE", "FR"]
    currencies = ["USD", "EUR", "GBP", "INR", "SGD", "AED"]
    mccs = ["5411", "5812", "5999", "4111", "4812", "6012", "5732"]
    kyc_levels = ["BASIC", "STANDARD", "ENHANCED"]

    now = utc_now()

    customer_rows = []
    customer_ids = []
    for _ in range(vols["customers"]):
        cid = str(uuid.uuid4())
        customer_ids.append(cid)
        created_at = now - \
            timedelta(days=rng.randint(0, 365), seconds=rng.randint(0, 86400))
        customer_rows.append({
            "customer_id": cid,
            "full_name": fake.name(),
            "email": fake.email(),
            "phone_e164": fake.msisdn()[:15],
            "dob": fake.date_of_birth(minimum_age=18, maximum_age=75).strftime("%Y-%m-%d"),
            "kyc_level": rng.choice(kyc_levels),
            "country": rng.choice(countries),
            "created_at": iso_utc(created_at),
        })

    account_rows = []
    account_ids = []
    for _ in range(vols["accounts"]):
        aid = str(uuid.uuid4())
        account_ids.append(aid)
        opened_at = now - \
            timedelta(days=rng.randint(0, 365), seconds=rng.randint(0, 86400))
        base_ccy = rng.choice(currencies)
        account_rows.append({
            "account_id": aid,
            "customer_id": rng.choice(customer_ids),
            "account_type": weighted_choice(rng, [("WALLET", 60), ("CHECKING", 30), ("CREDIT", 10)]),
            "status": weighted_choice(rng, [("ACTIVE", 92), ("SUSPENDED", 6), ("CLOSED", 2)]),
            "base_currency": base_ccy,
            "opened_at": iso_utc(opened_at),
        })

    merchant_rows = []
    merchant_ids = []
    for _ in range(vols["merchants"]):
        mid = str(uuid.uuid4())
        merchant_ids.append(mid)
        created_at = now - \
            timedelta(days=rng.randint(0, 900), seconds=rng.randint(0, 86400))
        merchant_rows.append({
            "merchant_id": mid,
            "merchant_name": fake.company(),
            "mcc": rng.choice(mccs),
            "country": rng.choice(countries),
            "risk_tier": weighted_choice(rng, [("LOW", 70), ("MEDIUM", 25), ("HIGH", 5)]),
            "created_at": iso_utc(created_at),
        })

    account_by_id = {r["account_id"]: r for r in account_rows}

    tx_rows = []
    for _ in range(vols["transactions"]):
        txid = str(uuid.uuid4())
        corr = str(uuid.uuid4())
        aid = rng.choice(account_ids)
        acct = account_by_id[aid]
        event_time = now - \
            timedelta(days=rng.randint(0, 30), seconds=rng.randint(0, 86400))
        ccy = rng.choice(currencies)
        amt_minor = rng.randint(100, 250000)
        status = weighted_choice(
            rng, [("AUTHORIZED", 25), ("CAPTURED", 30), ("SETTLED", 35), ("DECLINED", 10)])
        channel = weighted_choice(
            rng, [("CARD", 55), ("UPI", 25), ("ACH", 15), ("WIRE", 5)])
        direction = weighted_choice(rng, [("DEBIT", 85), ("CREDIT", 15)])
        idemp = f"{acct['customer_id']}:{aid}:{txid[:8]}"
        tx_rows.append({
            "transaction_id": txid,
            "correlation_id": corr,
            "event_time": iso_utc(event_time),
            "customer_id": acct["customer_id"],
            "account_id": aid,
            "merchant_id": rng.choice(merchant_ids),
            "channel": channel,
            "direction": direction,
            "amount": amt_minor,
            "currency": ccy,
            "status": status,
            "auth_code": str(rng.randint(100000, 999999)),
            "card_last4": str(rng.randint(0, 9999)).zfill(4) if channel == "CARD" else None,
            "device_id": f"dev_{rng.randint(1, 20000)}",
            "ip_address": fake.ipv4_public(),
            "idempotency_key": idemp,
            "amount_base": None,
            "base_currency": acct["base_currency"],
            "fx_rate": None,
            "merchant_risk_tier": None,
        })

    dispute_rows = []
    tx_sample = rng.sample(tx_rows, k=min(vols["disputes"], len(tx_rows)))
    for t in tx_sample:
        did = str(uuid.uuid4())
        event_dt = datetime.strptime(
            t["event_time"], ISO_UTC_FMT).replace(tzinfo=timezone.utc)
        opened_at = event_dt + \
            timedelta(days=rng.randint(1, 10), seconds=rng.randint(0, 86400))
        dispute_rows.append({
            "dispute_id": did,
            "correlation_id": t["correlation_id"],
            "transaction_id": t["transaction_id"],
            "opened_at": iso_utc(opened_at),
            "reason_code": weighted_choice(rng, [("FRAUD", 40), ("NOT_RECEIVED", 25), ("DUPLICATE", 15), ("OTHER", 20)]),
            "status": weighted_choice(rng, [("OPEN", 55), ("WON", 15), ("LOST", 15), ("CLOSED", 15)]),
            "amount": int(max(100, t["amount"] * rng.uniform(0.2, 1.0))),
            "currency": t["currency"],
        })

    fx_start = (utc_now() - timedelta(days=vols["fx_days"])).date()
    fx_rows = gen_fx_rates(
        rng, fx_start, vols["fx_days"], fx_cfg["base_ccy"], fx_cfg["quote_ccys"])

    write_csv(os.path.join(ref_dir, "customers.csv"),
              ["customer_id", "full_name", "email", "phone_e164",
                  "dob", "kyc_level", "country", "created_at"],
              customer_rows)

    write_csv(os.path.join(ref_dir, "accounts.csv"),
              ["account_id", "customer_id", "account_type",
                  "status", "base_currency", "opened_at"],
              account_rows)

    write_csv(os.path.join(ref_dir, "merchants.csv"),
              ["merchant_id", "merchant_name", "mcc",
                  "country", "risk_tier", "created_at"],
              merchant_rows)

    write_csv(os.path.join(ref_dir, "fx_rates.csv"),
              ["rate_date", "base_ccy", "quote_ccy", "rate", "provider"],
              fx_rows)

    write_jsonl(os.path.join(raw_dir, "transactions.jsonl"), tx_rows)
    write_jsonl(os.path.join(raw_dir, "disputes.jsonl"), dispute_rows)

    write_json(os.path.join(contracts_dir,
               "raw_transactions.schema.json"), RAW_TRANSACTIONS_SCHEMA)
    write_yaml(os.path.join(contracts_dir,
               "raw_transactions.schema.yaml"), RAW_TRANSACTIONS_SCHEMA)

    write_json(os.path.join(contracts_dir,
               "raw_disputes.schema.json"), RAW_DISPUTES_SCHEMA)
    write_yaml(os.path.join(contracts_dir,
               "raw_disputes.schema.yaml"), RAW_DISPUTES_SCHEMA)

    write_json(os.path.join(contracts_dir,
               "reference_customers.schema.json"), REFERENCE_CUSTOMERS_SCHEMA)
    write_yaml(os.path.join(contracts_dir,
               "reference_customers.schema.yaml"), REFERENCE_CUSTOMERS_SCHEMA)

    write_json(os.path.join(contracts_dir,
               "reference_accounts.schema.json"), REFERENCE_ACCOUNTS_SCHEMA)
    write_yaml(os.path.join(contracts_dir,
               "reference_accounts.schema.yaml"), REFERENCE_ACCOUNTS_SCHEMA)

    write_json(os.path.join(contracts_dir,
               "reference_merchants.schema.json"), REFERENCE_MERCHANTS_SCHEMA)
    write_yaml(os.path.join(contracts_dir,
               "reference_merchants.schema.yaml"), REFERENCE_MERCHANTS_SCHEMA)

    write_json(os.path.join(contracts_dir,
               "reference_fx_rates.schema.json"), REFERENCE_FX_RATES_SCHEMA)
    write_yaml(os.path.join(contracts_dir,
               "reference_fx_rates.schema.yaml"), REFERENCE_FX_RATES_SCHEMA)

    bundle = {
        "version": "1.0",
        "generated_at": iso_utc(utc_now()),
        "paths": {
            "raw": raw_dir,
            "reference": ref_dir,
            "contracts": contracts_dir,
        },
        "schemas": {
            "raw_transactions": "raw_transactions.schema.json",
            "raw_disputes": "raw_disputes.schema.json",
            "reference_customers": "reference_customers.schema.json",
            "reference_accounts": "reference_accounts.schema.json",
            "reference_merchants": "reference_merchants.schema.json",
            "reference_fx_rates": "reference_fx_rates.schema.json",
        },
        "quality_rules": QUALITY_RULES,
    }

    write_json(os.path.join(contracts_dir, "contracts_bundle.json"), bundle)
    write_yaml(os.path.join(contracts_dir, "contracts_bundle.yaml"), bundle)


if __name__ == "__main__":
    main()
