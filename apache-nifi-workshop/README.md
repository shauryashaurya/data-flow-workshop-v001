# Data Flow with NiFi - the *easy* version - minimal programming, if any...                                                                                                        
                                                                                                                                  
## Refs                                                                                                        
* Look - you've got to be able to install NiFi locally and get it started.                                                                                                        
* [Getting Started with Apache NiFi](https://nifi.apache.org/nifi-docs/getting-started.html#for-windows-users)                                                                                                        
* [Apache NiFi Overview](https://nifi.apache.org/docs/nifi-docs/html/overview.html)                                                                                                          
* [Apache NiFi User Guide](https://nifi.apache.org/nifi-docs/user-guide.html)                                                                                                          
* [NiFi System Administrator’s Guide](https://nifi.apache.org/nifi-docs/administration-guide.html)                                                                                                          
* [NiFi Components Documentation](https://nifi.apache.org/components/)                                                                                                          
* [Flow-based programming](https://en.wikipedia.org/wiki/Flow-based_programming#Concepts)                                                                                                            
                                                                                                                   
                                                                                                                     
                                                                                                                   
                                                                                                                   
# Workshop 01 - processing fintech data                                                                              
                                                                                                                                         
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
                                                                                                                                  
Pre-req directories                                                                                                                                  
                                                                                                                                  
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
                                                                                                                                  
5. Parameter Context (required for  tokenization)                                                                                                                                  
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
                                                                                                                                  
 feasibility check (done)                                                                                                                                  
                                                                                                                                  
* This works if and only if `./data/contracts/raw_transactions.schema.json` exists on the NiFi node filesystem and ValidateJson is pointed at it correctly (often requires absolute path in containerized deployments).                                                                                                                                  
                                                                                                                                  
---                                                                                                                                  
                                                                                                                                  
# Module 2: Enrichment + FX + idempotency for posting readiness                                                                                                                                  
                                                                                                                                  
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
                                                                                                                                  
# Module 3: Bounded retry + DLQ + replay + backpressure                                                                                                                                  
                                                                                                                                  
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
                                                                                                                                  
 feasibility check (done)                                                                                                                                  
                                                                                                                                  
* No custom code required.                                                                                                                                  
                                                                                                                                  
---                                                                                                                                  
                                                                                                                                  
# Module 4: Flow observability signals (counters + stall detection + metrics)                                                                                                                                  
                                                                                                                                  
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
                                                                                                                                  
 feasibility check (done)                                                                                                                                  
                                                                                                                                  
* Counters and MonitorActivity are .                                                                                                                                  
* Metrics export mechanism depends on your NiFi major version and packaging, but the rest of the module works regardless.                                                                                                                                  
                                                                                                                                  
---                                                                                                                                  
                                                                                                                                  
# Module 5: Deployment and maintenance (Registry + parameters + rollback)                                                                                                                                  
                                                                                                                                  
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
                                                                                                                                  
                                                                                                                              
                                                                                                                                  
---                                                                                                                                  
                                                                                                                                  
                                                                                                                                  
1. Every module references files that are created by the canonical generator outputs listed at the top, except:                                                                                                                                  
                                                                                                                                  
* Module 2 FX lookup file: explicitly created by the flow into `./data/lookup/fx_rates_lookup.csv`.                                                                                                                                  
                                                                                                                                  
2. The only path-related footgun is NiFi runtime filesystem resolution:                                                                                                                                  
                                                                                                                                  
* If NiFi runs in Docker/Kubernetes, `./data/...` must exist inside the container/pod filesystem or be mounted, and ValidateJson needs an absolute path as seen by NiFi.                                                                                                                                  
                                                                                                                                  
                                                                              
---                                                                              
# Workshop 02 - observability on 01                                                                              
                                                                              
* Telemetry JSONL files generated under `./data/obs/raw/`:                                                                                                        
  * `nifi_bulletins.jsonl`                                                                              
  * `nifi_provenance.jsonl`                                                                              
  * `flow_kpis.jsonl`                                                                              
  * `alerts.jsonl`                                                                              
* Contracts generated under `./data/obs/contracts/`:                                                                                              
  * `observability_contracts.json`                                                                              
  * `observability_contracts.yaml`                                                                              
                                                                              
Contract model (important for correctness)                                                                              
                                                                              
* The contract files above describe required fields per dataset (they are not JSON Schema documents).                                                                              
Because of that, the “contract enforcement” is implemented as required-field presence checks using Expression Language (`isEmpty()`), not ValidateJson with a JSON Schema file. ([Apache NiFi][1])                                                                              
                                                                                             
Pre-flight checks (do these before building anything)                                                                              
                                                                              
1. Confirm these files exist on the NiFi node filesystem (or mounted into the NiFi container/pod):                                                                                           
* `./data/obs/raw/nifi_bulletins.jsonl`                                                                              
* `./data/obs/raw/nifi_provenance.jsonl`                                                                              
* `./data/obs/raw/flow_kpis.jsonl`                                                                              
* `./data/obs/raw/alerts.jsonl`                                                                              
* `./data/obs/contracts/observability_contracts.json`                                                                              
                                                                              
2. Confirm these directories exist (CreateDirectory once if needed):                                                                                            
* `./data/obs/curated/raw`                                                                              
* `./data/obs/curated/normalized`                                                                              
* `./data/obs/quarantine`                                                                              
* `./data/obs/kpis`                                                                              
* `./data/obs/alerts`                                                                              
                                                                              
If any path is missing, fix the filesystem/mounts first. Do not proceed with processor work until these paths resolve from the NiFi runtime.                                                                              
                                                                              
---                                                                              
                                                                              
## Observability workshop                                                                               
                                                                              
### Module 1 : Telemetry intake + required-field contract checks                                                                              
                                                                              
Input files                                                                              
                                                                              
* `./data/obs/raw/*.jsonl` (4 datasets)                                                                              
                                                                              
Outputs                                                                              
                                                                              
* Valid: `./data/obs/curated/raw/<dataset>/`                                                                              
* Invalid: `./data/obs/quarantine/<dataset>/`                                                                              
                                                                              
Build 4 identical intake subflows (one per dataset).                                                                               
Example shown for bulletins; repeat with dataset-specific required fields.                                                                              
                                                                              
Bulletins required fields (from contract)                                                                              
                                                                              
* `event_time,node_id,group_id,component_id,component_type,bulletin_level,category,message`                                                                              
                                                                              
1. GetFile                                                                              
                                                                              
* Input Directory: `./data/obs/raw`                                                                              
* File Filter: `nifi_bulletins.jsonl`                                                                              
                                                                              
2. SplitText                                                                              
                                                                              
* Line Split Count: 1                                                                              
* Remove Trailing Newlines: true                                                                              
                                                                              
3. EvaluateJsonPath (Destination: flowfile-attribute)                                                                              
                                                                              
* event_time = `$.event_time`                                                                              
* node_id = `$.node_id`                                                                              
* group_id = `$.group_id`                                                                              
* component_id = `$.component_id`                                                                              
* component_type = `$.component_type`                                                                              
* bulletin_level = `$.bulletin_level`                                                                              
* category = `$.category`                                                                              
* message = `$.message`                                                                              
                                                                              
4. UpdateAttribute                                                                              
                                                                              
* req_ok =                                                                              
  `${event_time:isEmpty():not()                                                                              
    :and(${node_id:isEmpty():not()})                                                                              
    :and(${group_id:isEmpty():not()})                                                                              
    :and(${component_id:isEmpty():not()})                                                                              
    :and(${component_type:isEmpty():not()})                                                                              
    :and(${bulletin_level:isEmpty():not()})                                                                              
    :and(${category:isEmpty():not()})                                                                              
    :and(${message:isEmpty():not()})}`                                                                              
* ingest_time = `${now():format("yyyy-MM-dd'T'HH:mm:ss'Z'")}`                                                                              
                                                                              
`isEmpty()` and boolean `and()` are defined in NiFi EL. ([Apache NiFi][1])                                                                              
                                                                              
5. RouteOnAttribute                                                                              
                                                                              
* valid: `${req_ok:equals('true')}`                                                                              
* invalid: `${req_ok:equals('false')}`                                                                              
  (RouteOnAttribute routes based on Expression Language over attributes. ([Apache NiFi][2]))                                                                              
                                                                              
6. PutFile (valid)                                                                              
                                                                              
* Directory: `./data/obs/curated/raw/bulletins`                                                                              
                                                                              
7. Invalid path envelope + PutFile                                                                              
                                                                              
* ReplaceText (Always Replace) with:                                                                              
  `{"dataset":"bulletins","ingest_time":"${ingest_time}","missing_required":${req_ok:equals('false')},"raw":${content}}`                                                                              
* PutFile Directory: `./data/obs/quarantine/bulletins`                                                                              
                                                                              
Repeat for:                                                                              
                                                                              
* Provenance required fields: `event_time,node_id,flowfile_uuid,event_type,component_id,file_size,attributes`                                                                              
* KPIs required fields: `window_start,window_end,flow_name,metric_name,metric_value,dimensions`                                                                              
* Alerts required fields: `alert_time,alert_type,severity,signal,context`                                                                              
                                                                              
Best practices (deployment/maintenance)                                                                              
                                                                              
* Keep intake validation shallow and deterministic (presence checks + quarantine). Anything heavier belongs downstream; otherwise observability flow becomes fragile under malformed telemetry spikes.                                                                              
* Quarantine format must preserve original payload for replay and debugging; do not drop raw content at ingest.                                                                              
                                                                              
---                                                                              
                                                                              
### Module 2: Normalize telemetry into one unified event model                                                                              
                                                                              
Inputs                                                                              
                                                                              
* `./data/obs/curated/raw/<dataset>/`                                                                              
                                                                              
Output                                                                              
                                                                              
* `./data/obs/curated/normalized/telemetry_event/`                                                                              
                                                                              
Target normalized schema (single record per event)                                                                              
                                                                              
* event_time                                                                              
* event_kind: bulletin|provenance|kpi|alert                                                                              
* severity (derived; e.g., bulletin_level -> severity)                                                                              
* node_id                                                                              
* component_id (if present)                                                                              
* message (if present)                                                                              
* trace fields (optional): trace.correlation_id, trace.transaction_id, trace.idempotency_key                                                                              
* raw (optional) or keep minimal raw pointer                                                                              
                                                                              
Build 4 normalization subflows, each emitting the same normalized structure. Use QueryRecord because it provides explicit field selection/aliasing and calculations. ([Apache NiFi][3])                                                                              
                                                                              
Example: bulletins -> telemetry_event                                                                              
                                                                              
1. GetFile (from `./data/obs/curated/raw/bulletins`) -> SplitText (if needed; if you stored one JSON per file, skip SplitText)                                                                              
                                                                              
2. QueryRecord                                                                              
                                                                              
* Record Reader: JsonTreeReader ([Apache NiFi][4])                                                                              
* Record Writer: JsonRecordSetWriter                                                                              
* SQL:                                                                              
  `SELECT                                                                              
     event_time AS event_time,                                                                              
     'bulletin' AS event_kind,                                                                              
     bulletin_level AS severity,                                                                              
     node_id AS node_id,                                                                              
     component_id AS component_id,                                                                              
     message AS message,                                                                              
     "trace.correlation_id" AS trace_correlation_id,                                                                              
     "trace.transaction_id" AS trace_transaction_id,                                                                              
     "trace.idempotency_key" AS trace_idempotency_key                                                                              
   FROM FLOWFILE`                                                                              
                                                                              
3. PutFile                                                                              
                                                                              
* Directory: `./data/obs/curated/normalized/telemetry_event`                                                                              
                                                                              
Repeat similarly for provenance/kpi/alert, setting `event_kind` accordingly and mapping fields that exist.                                                                              
                                                                              
Best practices (deployment/maintenance)                                                                              
                                                                              
* Keep normalized schema stable and version it; downstream dashboards/alert rules should not chase field renames.                                                                              
* Do not push high-cardinality IDs into metric label dimensions; keep them in event logs/provenance-style records, not aggregates.                                                                              
                                                                              
---                                                                              
                                                                              
### Module 3: Derive SLO signals from KPIs (windowed aggregation)                                                                              
                                                                              
Inputs                                                                              
                                                                              
* `./data/obs/curated/raw/kpis/` (validated KPI records)                                                                              
                                                                              
Outputs                                                                              
                                                                              
* `./data/obs/kpis/derived_slos/` (one record per flow_name+window)                                                                              
                                                                              
Goal derived SLO record per (flow_name, window_start, window_end)                                                                              
                                                                              
* succeeded                                                                              
* failed                                                                              
* dlq_count                                                                              
* backpressure_engaged                                                                              
* latency_ms_p95                                                                              
* error_rate = failed / (failed + succeeded)                                                                              
                                                                              
 steps                                                                              
                                                                              
1. GetFile (kpis) -> SplitText (1 line)                                                                              
                                                                              
2. EvaluateJsonPath (attributes)                                                                              
                                                                              
* window_start = `$.window_start`                                                                              
* flow_name = `$.flow_name`                                                                              
                                                                              
3. UpdateAttribute                                                                              
                                                                              
* kpi_key = `${window_start:append('|'):append(${flow_name})}`                                                                              
                                                                              
4. MergeRecord                                                                              
                                                                              
* Record Reader: JsonTreeReader                                                                              
* Record Writer: JsonRecordSetWriter                                                                              
* Correlation Attribute Name: `kpi_key`                                                                              
* Minimum Number of Records: 3                                                                              
* Maximum Number of Records: 50                                                                              
* Maximum Bin Age: 30 sec                                                                              
  (Goal: gather metrics for the same window+flow into one FlowFile to enable conditional aggregation.)                                                                              
                                                                              
5. QueryRecord (pivot/aggregate)                                                                              
                                                                              
* Reader/Writer: JsonTreeReader / JsonRecordSetWriter                                                                              
* SQL:                                                                              
  `SELECT                                                                              
     window_start,                                                                              
     window_end,                                                                              
     flow_name,                                                                              
     SUM(CASE WHEN metric_name = 'postings_succeeded' THEN metric_value ELSE 0 END) AS succeeded,                                                                              
     SUM(CASE WHEN metric_name = 'postings_failed' THEN metric_value ELSE 0 END) AS failed,                                                                              
     SUM(CASE WHEN metric_name = 'dlq_count' THEN metric_value ELSE 0 END) AS dlq_count,                                                                              
     MAX(CASE WHEN metric_name = 'backpressure_engaged' THEN metric_value ELSE 0 END) AS backpressure_engaged,                                                                              
     MAX(CASE WHEN metric_name = 'latency_ms_p95' THEN metric_value ELSE 0 END) AS latency_ms_p95                                                                              
   FROM FLOWFILE                                                                              
   GROUP BY window_start, window_end, flow_name`                                                                              
                                                                              
6. QueryRecord (compute error_rate safely)                                                                              
                                                                              
* SQL:                                                                              
  `SELECT                                                                              
     window_start, window_end, flow_name,                                                                              
     succeeded, failed, dlq_count, backpressure_engaged, latency_ms_p95,                                                                              
     CASE WHEN (succeeded + failed) = 0 THEN 0 ELSE failed / (succeeded + failed) END AS error_rate                                                                              
   FROM FLOWFILE`                                                                              
                                                                              
7. PutFile                                                                              
                                                                              
* Directory: `./data/obs/kpis/derived_slos`                                                                              
                                                                              
Best practices (deployment/maintenance)                                                                              
                                                                              
* Use explicit correlation keys for MergeRecord; otherwise you will mix windows/flows and silently compute nonsense.                                                                              
* Keep bin age small and bounded; large bins during load spikes create memory pressure and delayed alerting.                                                                              
                                                                              
                                                                              
---                                                                              
                                                                              
### Module 4: Alert event generation + stall detection                                                                               
                                                                              
Inputs                                                                              
                                                                              
* `./data/obs/kpis/derived_slos/`                                                                              
                                                                              
Outputs                                                                              
                                                                              
* `./data/obs/alerts/` (structured alert events)                                                                              
                                                                              
Parameters (Parameter Context)                                                                              
                                                                              
* `alert.error_rate_threshold` (e.g., 0.02)                                                                              
* `alert.dlq_threshold` (e.g., 10)                                                                              
* `alert.latency_p95_threshold` (e.g., 2000)                                                                              
* `alert.backpressure_trigger` (e.g., 1)                                                                              
                                                                              
 steps (threshold alerts)                                                                              
                                                                              
1. GetFile (derived_slos)                                                                              
                                                                              
2. EvaluateJsonPath (attributes)                                                                              
                                                                              
* error_rate = `$.error_rate`                                                                              
* dlq_count = `$.dlq_count`                                                                              
* latency_ms_p95 = `$.latency_ms_p95`                                                                              
* backpressure_engaged = `$.backpressure_engaged`                                                                              
* flow_name = `$.flow_name`                                                                              
* window_start = `$.window_start`                                                                              
                                                                              
3. RouteOnAttribute                                                                              
                                                                              
* error_rate_high: `${error_rate:toNumber():gt(${alert.error_rate_threshold})}`                                                                              
* dlq_high: `${dlq_count:toNumber():gt(${alert.dlq_threshold})}`                                                                              
* latency_high: `${latency_ms_p95:toNumber():gt(${alert.latency_p95_threshold})}`                                                                              
* backpressure_on: `${backpressure_engaged:toNumber():equals(${alert.backpressure_trigger})}`                                                                              
                                                                              
4. For each alert relationship: ReplaceText to emit a single-line alert JSON                                                                              
   Example (error_rate_high):                                                                              
                                                                              
* `{"alert_time":"${now():format(\"yyyy-MM-dd'T'HH:mm:ss'Z'\")}","alert_type":"error_rate_high","severity":"HIGH","context":{"flow_name":"${flow_name}","window_start":"${window_start}"},"signal":{"error_rate":${error_rate}}}`                                                                              
                                                                              
5. PutFile                                                                              
                                                                              
* Directory: `./data/obs/alerts`                                                                              
                                                                              
Optional: Stall detection on a live flow                                                                              
                                                                              
* MonitorActivity emits FlowFiles to `inactive` and `activity.restored` when no FlowFiles are routed to `success` for the threshold duration, and it supports a “Reporting Node” setting for clusters. ([Apache NiFi][5])                                                                              
  Route those relationships to the same alert writer (ReplaceText + PutFile).                                                                              
                                                                              
Best practices (deployment/maintenance)                                                                              
                                                                              
* Alerts must be deduped/suppressed to avoid storms during known outages; build suppression as a stateful gate if you productionize this.                                                                              
* Separate “data quality” alerts (contract failures, enrichment misses) from “system health” alerts (backpressure, stalls); they page different owners.                                                                              
                                                                              
---                                                                              
                                                                              
### Module 5: Productionizing the observability plane + optional live NiFi integration                                                                              
                                                                              
Guaranteed (file-based) deployment pattern                                                                              
                                                                              
* Keep this observability plane as a separate Process Group (or separate NiFi instance if you want hard isolation).                                                                              
* Version the PG, parameterize filesystem paths and thresholds, and promote across environments (Registry-based or your standard flow promotion approach).                                                                              
                                                                              
Optional live integration (only if you enable these tasks in the monitored NiFi)                                                                              
                                                                              
* SiteToSiteBulletinReportingTask publishes bulletins via Site-to-Site and warns that if it isn’t scheduled frequently, some bulletins may not be sent due to short retention. ([Apache NiFi][6])                                                                              
* SiteToSiteProvenanceReportingTask publishes provenance events via Site-to-Site to another NiFi instance (or the same). ([Apache NiFi][7])                                                                              
                                                                              
 steps (optional live integration)                                                                              
                                                                              
1. On the monitored NiFi: enable Site-to-Site input/output per your security policy.                                                                              
2. Add and configure:                                                                              
                                                                              
* SiteToSiteBulletinReportingTask ([Apache NiFi][6])                                                                              
* SiteToSiteProvenanceReportingTask ([Apache NiFi][7])                                                                              
                                                                              
3. On the observability NiFi: create a receiving PG that ingests incoming Site-to-Site FlowFiles and routes them into Modules 1–2 normalization.                                                                              
                                                                              
Best practices (deployment/maintenance)                                                                              
                                                                              
* Run observability ingestion on separate resources where possible; during incidents the monitored NiFi is already stressed.                                                                              
* Schedule bulletin reporting frequently enough to meet its retention constraints, otherwise you will lose incident signals. ([Apache NiFi][6])                                                                              
                                                                              
---                                                                              
                                                                              
## System administration best practices for NiFi (deployment and maintenance)                                                                              
                                                                              
1. Repository layout is a first-order reliability decision                                                                              
                                                                              
* FlowFile repository is a write-ahead log of FlowFile metadata and pointers to content; this is central to restart resiliency. ([Apache NiFi][8])                                                                              
* Keep repositories on appropriate storage; do not co-locate everything by default. (Operational guidance commonly recommends separating Content from FlowFile repo to reduce contention; vendor docs echo this.) ([Cloudera Legacy Documentation][9])                                                                              
                                                                              
2. Configure multiple content repositories when you need throughput and I/O isolation                                                                              
                                                                              
* Multiple content repository directories can be configured using the `nifi.content.repository.directory.<name>=...` pattern. ([Cloudera Legacy Documentation][10])                                                                              
  Use it to spread I/O across disks rather than pushing one volume into saturation.                                                                              
                                                                              
3. Backpressure guardrails: don’t “tune it away”                                                                              
                                                                              
* Default connection backpressure commonly starts at 10,000 FlowFiles and 1 GB; raising limits to avoid “red queues” usually just moves the failure to disk pressure and swapping. ([Cloudera Legacy Documentation][11])                                                                              
  Enforce guardrails using Flow Analysis Rules such as RestrictBackpressureSettings (policy-level control). ([Apache NiFi][12])                                                                              
                                                                              
4. Always enable and manage flow configuration archiving                                                                              
                                                                              
* NiFi has properties to enable archiving flow configuration backups (flow.xml.gz archives) so you can recover from bad changes. ([Cloudera Legacy Documentation][13])                                                                              
  Treat this as a break-glass recovery path alongside Registry rollback.                                                                              
                                                                              
5. Secure-by-default posture and access binding                                                                              
                                                                              
* NiFi administration guidance notes default binding behavior and emphasizes configuring HTTPS/security to expose the UI beyond loopback safely. ([Apache NiFi][14])                                                                              
                                
## MOAR REFs	                            
[1]: https://nifi.apache.org/docs/nifi-docs/html/expression-language-guide.html?utm_source=chatgpt.com "Apache NiFi Expression Language Guide"                                                                              
[2]: https://nifi.apache.org/docs/nifi-docs/components/org.apache.nifi/nifi-standard-nar/1.6.0/org.apache.nifi.processors.standard.RouteOnAttribute/index.html?utm_source=chatgpt.com "RouteOnAttribute"                                                                              
[3]: https://nifi.apache.org/docs/nifi-docs/components/org.apache.nifi/nifi-standard-nar/1.6.0/org.apache.nifi.processors.standard.QueryRecord/index.html?utm_source=chatgpt.com "QueryRecord"                                                                              
[4]: https://nifi.apache.org/components/org.apache.nifi.json.JsonTreeReader/?utm_source=chatgpt.com "JsonTreeReader - Apache NiFi"                                                                              
[5]: https://nifi.apache.org/components/org.apache.nifi.processors.standard.MonitorActivity/?utm_source=chatgpt.com "MonitorActivity - Apache NiFi"                                                                              
[6]: https://nifi.apache.org/components/org.apache.nifi.reporting.SiteToSiteBulletinReportingTask/?utm_source=chatgpt.com "SiteToSiteBulletinReportingTask - Apache NiFi"                                                                              
[7]: https://nifi.apache.org/components/org.apache.nifi.reporting.SiteToSiteProvenanceReportingTask/?utm_source=chatgpt.com "SiteToSiteProvenanceReporting..."                                                                              
[8]: https://nifi.apache.org/docs/nifi-docs/html/nifi-in-depth.html?utm_source=chatgpt.com "Apache NiFi In Depth"                                                                              
[9]: https://docs-archive.cloudera.com/cfm/2.1.1/nifi-admin-guide/topics/nifi-content-repository.html?utm_source=chatgpt.com "Content Repository | Cloudera on Premises"                                                                              
[10]: https://docs-archive.cloudera.com/cfm/2.1.2/nifi-admin-guide/topics/nifi-file-system-content-repository-properties.html?utm_source=chatgpt.com "File System Content Repository Properties"                                                                              
[11]: https://docs-archive.cloudera.com/cfm/2.0.4/nifi-user-guide/topics/nifi-settings.html?utm_source=chatgpt.com "Settings | Cloudera on Premises"                                                                              
[12]: https://nifi.apache.org/components/org.apache.nifi.flowanalysis.rules.RestrictBackpressureSettings/?utm_source=chatgpt.com "RestrictBackpressureSettings - Apache NiFi"                                                                              
[13]: https://docs-archive.cloudera.com/cfm/2.0.4/nifi-admin-guide/topics/nifi-core-properties-br.html?utm_source=chatgpt.com "Core Properties | Cloudera on Premises"                                                                              
[14]: https://nifi.apache.org/docs/nifi-docs/html/administration-guide.html?utm_source=chatgpt.com "NiFi System Administrator's Guide"                                                                              
                                                                              
---                          
---                          
