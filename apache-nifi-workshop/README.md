                          
                          
## Canonical                           
                          
These are the outputs from the generator that emits per-dataset schema files:                          
                          
Data                          
                          
* `./data/raw/transactions.jsonl`                          
* `./data/raw/disputes.jsonl`                          
* `./data/reference/customers.csv`                          
* `./data/reference/accounts.csv`                          
* `./data/reference/merchants.csv`                          
* `./data/reference/fx_rates.csv`                          
                          
Contracts                          
                          
* `./data/contracts/raw_transactions.schema.json`                          
* `./data/contracts/raw_disputes.schema.json`                          
* `./data/contracts/reference_customers.schema.json`                          
* `./data/contracts/reference_accounts.schema.json`                          
* `./data/contracts/reference_merchants.schema.json`                          
* `./data/contracts/reference_fx_rates.schema.json`                          
* `./data/contracts/contracts_bundle.json`                          
                          
If you only have `raw_contracts.json|yaml` and not the per-file schemas, you ran an older generator.                            
Fix is: run the corrected generator (the one that writes `raw_transactions.schema.json` etc.) and proceed.                          
                          
Quick verification (run locally)                          
                          
* Check that `./data/contracts/raw_transactions.schema.json` exists and is non-empty.                          
* Check that `./data/raw/transactions.jsonl` exists and has multiple lines.                          
                          
---                          
                          
# Module 1: Ingest + contract enforcement + PII controls                          
                          
Schema reminder used here                          
                          
* Raw input: `./data/raw/transactions.jsonl`                          
* Contract: `./data/contracts/raw_transactions.schema.json`                          
                          
Goal outputs                          
                          
* `./data/curated/transactions_sanitized.jsonl`                          
* `./data/quarantine/transactions_invalid.jsonl`                          
                          
Pre-req directories (run once)                          
                          
* Ensure these exist (CreateDirectory processors or create manually):                          
                          
  * `./data/curated`                          
  * `./data/quarantine`                          
                          
Flow steps                          
                          
1. GetFile                          
                          
* Input Directory: `./data/raw`                          
* File Filter: `transactions.jsonl`                          
* Keep Source File: false (or true if you want re-runs; but then add a processed marker strategy)                          
                          
2. SplitText                          
                          
* Line Split Count: 1                          
* Remove Trailing Newlines: true                          
  Reason: JSONL must be validated one JSON object per FlowFile.                          
                          
3. ValidateJson                          
                          
* JSON Schema: load from `./data/contracts/raw_transactions.schema.json`                          
                          
  * Use an absolute path if your NiFi runs in a container and relative paths won’t resolve.                          
* Route:                          
                          
  * valid relationship -> step 4                          
  * invalid relationship -> step 8                          
  * failure relationship -> step 8                          
                          
4. EvaluateJsonPath (Destination: flowfile-attribute)                          
                          
* ip_raw = `$.ip_address`                          
* card_last4_raw = `$.card_last4`                          
* correlation_id = `$.correlation_id`                          
* transaction_id = `$.transaction_id`                          
* idempotency_key = `$.idempotency_key`                          
                          
5. Parameter Context (required for low-code tokenization)                          
   Create a Parameter Context (e.g., `fintech-dev`) and define:                          
                          
* `security.token_salt` (sensitive)                          
* `policy.mask_card_last4` = `true` or `false`                          
                          
6. UpdateAttribute                          
                          
* ip_token = `${ip_raw:append(${security.token_salt}):hash('SHA-256')}`                          
* card_masked = `${policy.mask_card_last4:equals('true'):ifElse('****', ${card_last4_raw})}`                          
* ingest_time = `${now():format("yyyy-MM-dd'T'HH:mm:ss'Z'")}`                          
* schema_version = `1.0`                          
                          
7. UpdateRecord (sanitize + attach metadata)                          
                          
* Reader: JsonTreeReader                          
* Writer: JsonRecordSetWriter                          
* Set:                          
                          
  * `/ip_address` = `${ip_token}`                          
  * `/card_last4` = `${card_masked}`                          
  * `/ingest_time` = `${ingest_time}`                          
  * `/schema_version` = `${schema_version}`                          
                          
Optional strict minimization (recommended)                          
8) QueryRecord (keep only allowed fields)                          
                          
* Reader/Writer: JsonTreeReader / JsonRecordSetWriter                          
* SQL:                          
                          
  * `SELECT transaction_id, correlation_id, event_time, customer_id, account_id, merchant_id, channel, direction, amount, currency, status, idempotency_key, auth_code, device_id, ip_address, card_last4, ingest_time, schema_version FROM FLOWFILE`                          
                          
9. PutFile (curated)                          
                          
* Directory: `./data/curated`                          
* Filename: `transactions_sanitized.jsonl`                          
* If you want a single file, you need MergeRecord before PutFile; otherwise you’ll get one file per record. For the workshop, one-file-per-record is acceptable but noisy.                          
                          
Invalid/quarantine path                          
                          
8. UpdateAttribute (for invalid and failure from ValidateJson)                          
                          
* ingest_time, schema_version                          
* validation_errors:                          
                          
  * invalid: `${json.validation.errors}`                          
  * failure: `parse_error`                          
* source_file = `${filename}`                          
                          
9. ReplaceText (wrap invalid with metadata; keeps replayable payload)                          
                          
* Replacement Strategy: Always Replace                          
* Replacement Value (single line):                          
                          
  * `{"schema_version":"${schema_version}","ingest_time":"${ingest_time}","source_file":"${source_file}","validation_errors":"${validation_errors}","raw":${content}}`                          
                          
10. PutFile (quarantine)                          
                          
* Directory: `./data/quarantine`                          
* Filename: `transactions_invalid.jsonl` (or keep per-record)                          
                          
Low-code feasibility check (done)                          
                          
* This works if and only if `./data/contracts/raw_transactions.schema.json` exists on the NiFi node filesystem and ValidateJson is pointed at it correctly (often requires absolute path in containerized deployments).                          
                          
---                          
                          
# Module 2 (low-code): Enrichment + FX + idempotency for posting readiness                          
                          
Schema reminder used here                          
                          
* Input: `./data/curated/transactions_sanitized.jsonl`                          
* Reference:                          
                          
  * `./data/reference/merchants.csv`                          
  * `./data/reference/fx_rates.csv`                          
                          
Goal outputs                          
                          
* `./data/ledger/postings_ready.jsonl`                          
* `./data/quarantine/enrichment_unmatched.jsonl`                          
* `./data/quarantine/postings_duplicate.jsonl`                          
                          
Pre-req directories                          
                          
* `./data/ledger`                          
* `./data/lookup` (created in this module)                          
* `./data/quarantine` (already exists)                          
                          
Part A: Create FX lookup file with a single key (needed because CSV lookup is single-key)                          
                          
1. GetFile                          
                          
* Directory: `./data/reference`                          
* File Filter: `fx_rates.csv`                          
                          
2. QueryRecord (CSV -> CSV with fx_key)                          
                          
* Reader: CSVReader (first line is header)                          
* Writer: CSVRecordSetWriter                          
* SQL:                          
                          
  * `SELECT CONCAT(rate_date, '|', quote_ccy) AS fx_key, rate_date, base_ccy, quote_ccy, rate, provider FROM FLOWFILE`                          
                          
3. PutFile                          
                          
* Directory: `./data/lookup`                          
* Filename: `fx_rates_lookup.csv`                          
                          
Part B: Lookup services (Controller Services)                          
                          
4. CSVRecordLookupService: merchants                          
                          
* CSV File: `./data/reference/merchants.csv`                          
* Lookup Key Column: `merchant_id`                          
                          
5. CSVRecordLookupService: fx                          
                          
* CSV File: `./data/lookup/fx_rates_lookup.csv`                          
* Lookup Key Column: `fx_key`                          
                          
Part C: Main enrichment flow                          
                          
6. GetFile                          
                          
* Directory: `./data/curated`                          
* File Filter: `transactions_sanitized.jsonl`                          
                          
7. SplitText                          
                          
* Line Split Count: 1                          
                          
8. EvaluateJsonPath (attributes)                          
                          
* event_time = `$.event_time`                          
* currency = `$.currency`                          
* merchant_id = `$.merchant_id`                          
* idempotency_key = `$.idempotency_key`                          
                          
9. UpdateAttribute                          
                          
* rate_date = `${event_time:toDate("yyyy-MM-dd'T'HH:mm:ss'Z'"):format("yyyy-MM-dd")}`                          
* fx_key = `${rate_date:append('|'):append(${currency})}`                          
                          
10. UpdateRecord (write fx_key into the record for LookupRecord)                          
                          
* Reader/Writer: JsonTreeReader / JsonRecordSetWriter                          
* Set `/fx_key` = `${fx_key}`                          
                          
11. LookupRecord (merchant)                          
                          
* Reader/Writer: JsonTreeReader / JsonRecordSetWriter                          
* Lookup Service: merchants CSVRecordLookupService                          
* RecordPath for lookup key mapping:                          
                          
  * Key `merchant_id` -> RecordPath `/merchant_id`                          
* Result RecordPath: `/merchant_ref`                          
* Routing: route unmatched (send to quarantine)                          
                          
12. RouteOnAttribute (bypass FX lookup if currency is USD)                          
                          
* usd = `${currency:equals('USD')}`                          
                          
USD path                          
13a) UpdateRecord                          
                          
* Set `/fx_rate` = `1.0`                          
* Set `/amount_base` = `/amount`                          
* Set `/base_currency` = `USD`                          
* Set `/merchant_risk_tier` = `/merchant_ref.risk_tier`                          
                          
Non-USD path                          
13b) LookupRecord (fx)                          
                          
* Lookup Service: fx CSVRecordLookupService                          
* Key `fx_key` -> RecordPath `/fx_key`                          
* Result RecordPath: `/fx_ref`                          
* Routing: route unmatched (send to quarantine)                          
                          
14. QueryRecord (compute amount_base and flatten fields)                          
                          
* Reader/Writer: JsonTreeReader / JsonRecordSetWriter                          
* SQL (non-USD path):                          
                          
  * `SELECT transaction_id, correlation_id, event_time, customer_id, account_id, merchant_id, amount, currency, status, idempotency_key, CAST(fx_ref.rate AS DOUBLE) AS fx_rate, CAST(amount / CAST(fx_ref.rate AS DOUBLE) AS BIGINT) AS amount_base, 'USD' AS base_currency, merchant_ref.risk_tier AS merchant_risk_tier FROM FLOWFILE`                          
                          
15. DetectDuplicate (idempotency)                          
                          
* Cache Entry Identifier: `${idempotency_key}`                          
* Cache Service: DistributedMapCacheClientService (backed by DistributedMapCacheServer for workshop)                          
* Age Off Duration: e.g., `7 days`                          
* Non-duplicate -> PutFile ledger                          
* Duplicate -> PutFile duplicates quarantine                          
* Failure -> quarantine (cache outage)                          
                          
16. PutFile (ledger)                          
                          
* Directory: `./data/ledger`                          
* Filename: `postings_ready.jsonl` (use MergeRecord if you want one file)                          
                          
Unmatched paths (merchant unmatched, fx unmatched)                          
                          
* Wrap with ReplaceText envelope including reason and raw content                          
* PutFile to `./data/quarantine/enrichment_unmatched.jsonl`                          
                          
Duplicates path                          
                          
* PutFile to `./data/quarantine/postings_duplicate.jsonl`                          
                          
                          
* FX needs the generated `./data/lookup/fx_rates_lookup.csv` (this module creates it explicitly).                          
                          
---                          
                          
# Module 3 (low-code): Bounded retry + DLQ + replay + backpressure                          
                          
Schema reminder used here                          
                          
* Input: `./data/ledger/postings_ready.jsonl`                          
                          
Goal outputs                          
                          
* `./data/sink/` (simulated downstream)                          
* `./data/dlq/`                          
* `./data/replay/` (optional staging)                          
                          
Pre-req directories                          
                          
* `./data/dlq`                          
* `./data/replay`                          
* Do not create `./data/sink` initially if you want deterministic sink failure.                          
                          
Flow steps                          
                          
1. GetFile                          
                          
* Directory: `./data/ledger`                          
* File Filter: `postings_ready.jsonl`                          
                          
2. SplitText                          
                          
* Line Split Count: 1                          
                          
3. PutFile (sink simulation)                          
                          
* Directory: `./data/sink`                          
* Create Missing Directories: false                          
* success -> done                          
* failure -> RetryFlowFile                          
                          
4. RetryFlowFile                          
                          
* Maximum Retries: 5                          
* Penalize: true                          
* retry -> back to PutFile                          
* retries_exceeded -> DLQ write                          
                          
5. DLQ envelope                          
                          
* UpdateAttribute: dlq_time, retry_count                          
* ReplaceText:                          
                          
  * `{"dlq_time":"${dlq_time}","retry_count":"${retry.count}","payload":${content}}`                          
                          
6. PutFile (DLQ)                          
                          
* Directory: `./data/dlq`                          
                          
Replay flow (once you create `./data/sink`)                          
                          
7. GetFile                          
                          
* Directory: `./data/dlq`                          
                          
8. EvaluateJsonPath (attribute payload)                          
                          
* payload = `$.payload`                          
                          
9. ReplaceText                          
                          
* Replace with `${payload}`                          
                          
10. PutFile                          
                          
* Directory: `./data/sink`                          
                          
Backpressure check                          
                          
* Set connection backpressure on the queue into PutFile (e.g., 500 objects / 50 MB) and observe upstream throttling.                          
                          
Low-code feasibility check (done)                          
                          
* No custom code required.                          
                          
---                          
                          
# Module 4 (low-code): Flow observability signals (counters + stall detection + metrics)                          
                          
Schema reminder used here                          
                          
* Input can be any “success path” (e.g., Module 2 or 3 stream). We’ll use `./data/ledger/postings_ready.jsonl`.                          
                          
Goal outputs                          
                          
* `./data/alerts/` for generated operational alerts                          
* Metrics endpoint (depends on NiFi version)                          
                          
Pre-req directories                          
                          
* `./data/alerts`                          
                          
Flow steps                          
                          
1. GetFile -> SplitText (same as prior modules)                          
                          
2. EvaluateJsonPath -> UpdateAttribute                          
                          
* Extract and standardize:                          
                          
  * trace.correlation_id                          
  * trace.transaction_id                          
  * trace.idempotency_key                          
                          
3. UpdateCounter (entry and outcomes)                          
                          
* ledger.postings.in                          
* ledger.postings.succeeded (after sink success)                          
* ledger.postings.failed (after sink failure/DLQ)                          
                          
4. MonitorActivity (stall detection)                          
                          
* Place on a critical connection (e.g., before sink PutFile)                          
* Inactivity Threshold: 2 minutes                          
* inactive -> alert writer                          
* activity.restored -> alert writer                          
                          
5. Alert writer                          
                          
* UpdateAttribute: alert_time, alert_type, trace ids                          
* ReplaceText to structured JSON alert                          
* PutFile -> `./data/alerts`                          
                          
Metrics export (version-sensitive)                          
                          
* If you have PrometheusReportingTask available: enable it and expose `/metrics`.                          
* If not available in your build: use whatever your NiFi version provides for metrics export (your ops team likely already has a standard; keep it consistent with that).                          
                          
Low-code feasibility check (done)                          
                          
* Counters and MonitorActivity are low-code.                          
* Metrics export mechanism depends on your NiFi major version and packaging, but the rest of the module works regardless.                          
                          
---                          
                          
# Module 5 (low-code): Deployment and maintenance (Registry + parameters + rollback)                          
                          
Schema reminder used here                          
                          
* Same data paths; the point is controlling them via parameters, not hardcoding.                          
                          
Goal outputs                          
                          
* Versioned flows in NiFi Registry                          
* Deterministic promotion across environments                          
* Rollback via version restore                          
* No environment drift                          
                          
Steps                          
                          
1. Parameterize everything environment-specific                          
                          
* All directories (`./data/...`) must be parameters:                          
                          
  * paths.raw_dir                          
  * paths.curated_dir                          
  * paths.quarantine_dir                          
  * paths.lookup_dir                          
  * paths.ledger_dir                          
  * paths.sink_dir                          
* Security values (token salt) as sensitive parameters:                          
                          
  * security.token_salt                          
                          
2. Apply Parameter Context to the root Process Group                          
                          
* No hardcoded file paths in processors                          
                          
3. Connect NiFi to NiFi Registry                          
                          
* Add Registry Client                          
* Start version control on the PG                          
* Commit versions with meaningful changesets                          
                          
4. Promotion                          
                          
* In target env, import from Registry by version                          
* Bind the correct Parameter Context for that env                          
* Start PG                          
                          
5. Rollback                          
                          
* Restore previous PG version from version history                          
* Parameters stay environment-specific and do not require re-editing the flow logic                          
                          
Low-code feasibility check (done)                          
                          
* Full low-code in UI.                          
                          
---                          
                          
                          
1. Every module references files that are created by the canonical generator outputs listed at the top, except:                          
                          
* Module 2 FX lookup file: explicitly created by the flow into `./data/lookup/fx_rates_lookup.csv`.                          
                          
2. The only path-related footgun is NiFi runtime filesystem resolution:                          
                          
* If NiFi runs in Docker/Kubernetes, `./data/...` must exist inside the container/pod filesystem or be mounted, and ValidateJson needs an absolute path as seen by NiFi.                          
                          
If you tell me your NiFi runtime mode (bare metal vs Docker vs k8s) and the NiFi major version (1.x vs 2.x), I can tighten the few version-specific knobs (ValidateJson schema property name and metrics export task) without introducing new ambiguity.                          
