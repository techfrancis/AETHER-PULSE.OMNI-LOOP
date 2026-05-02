# perf-advisor (AETHER-PULSE Tier 1)

Rule-based monitor + metric/config history for the local CORTEX.X / Synapse stack. First component of AETHER-PULSE's perf-watcher pillar — sister to the existing threat-watcher pillar (REVENANT → aether-core → Cortex.X → Axon).

## What it does today

- Polls `vLLM /metrics` and Synapse host filesystem every `poll_interval_sec` (default 60s).
- Persists every numeric metric to `~/.aether-pulse/perf-advisor/history.db` (SQLite), tagged with the config fingerprint that produced it.
- Snapshots vLLM container args + Synapse config hash; writes a new `configs` row only when the fingerprint changes.
- Evaluates 6 conservative rules over the live window; emits findings to `findings.jsonl` + stdout.

## What it sets up for later

The `metrics` + `configs` tables are the substrate Tier 2 will read to answer counterfactuals:

> "If I bump Synapse concurrency from 16 to 32, what does our own history say will happen on this hardware?"

That requires real metric/config pairs over time — Tier 1 is the data-collection layer.

## Run

```bash
cd perf-advisor
pip install -r requirements.txt

# Sanity-check one cycle
python advisor.py --once --verbose

# Daemon mode
python advisor.py --verbose
```

The history db and findings log live under `~/.aether-pulse/perf-advisor/`. Override paths via `config.yaml`.

## Rules (current)

| Rule | Severity | Trigger |
|---|---|---|
| `vllm_queue_saturated` | warn | running queue at concurrency cap >5min |
| `vllm_kv_cache_high` | warn | KV cache >85% sustained >2min |
| `vllm_throughput_drop` | crit | gen tok/s drops >25% vs 30min baseline |
| `synapse_ingest_stalled` | warn | log marked active but silent >5min |
| `synapse_cards_per_min_drop` | warn | cards/min drops >25% vs 1h baseline |
| `synapse_no_recent_activity` | info | (disabled by default) no ingest >30min |

Each rule has a 10-min cooldown — a sustained condition produces one alert, not one per poll.

## Quick history queries

```bash
sqlite3 ~/.aether-pulse/perf-advisor/history.db
```

```sql
-- Configs we've observed
SELECT id, source, summary_json, datetime(first_seen, 'unixepoch')
  FROM configs ORDER BY first_seen DESC;

-- Last 20 findings
SELECT datetime(ts, 'unixepoch'), severity, rule_name, message
  FROM findings ORDER BY ts DESC LIMIT 20;

-- vLLM running-queue depth across configs
SELECT c.summary_json, AVG(m.value) AS avg_running, COUNT(*) AS samples
  FROM metrics m LEFT JOIN configs c ON m.config_id = c.id
  WHERE m.name = 'vllm:num_requests_running' AND m.source = 'vllm'
  GROUP BY c.id;

-- Synapse cards growth
SELECT datetime(ts, 'unixepoch') AS at, value AS cards
  FROM metrics WHERE name = 'cards_count' AND source = 'synapse'
  ORDER BY ts DESC LIMIT 20;
```

## Why a separate module from `aether-core`

`aether-core` (Go gRPC) is the threat-mitigation router: kernel telemetry → trust check → WASM mitigation, millisecond-latency. perf-advisor's signals are operational, not adversarial: minute-cadence Prometheus + filesystem polling. Mixing the two would muddy `aether-core`'s sub-second budget and force a Python<>Go boundary where Python alone is enough at Tier 1. Keeping them sibling modules under the same OMNI-LOOP umbrella preserves the architectural pattern (sensor → router → cognitive → mitigation) on each side without coupling release cadences.

## Next: Tier 2 (LLM-augmented)

Same data stream, but Gemma reads rolling windows + recent log diffs + config diffs and flags anomalies the rule set wouldn't catch. Tracked under a separate Jira ticket; design doc lands once Tier 1 has accumulated >24h of data.

## Process

- **Branching** follows Railhead's convention: `feature/TF-###-perf-advisor-*`.
- **Commit-msg hook**: AETHER-PULSE.OMNI-LOOP installs Railhead's `pre_flight.py` as `commit-msg` (see repo-root `.git/hooks/`).
- **Releases** will use Railhead's `railhead-release.yml` template once the module ships its first `v0.1.0-rcN` tag — see `.gitlab-ci.yml` for the include skeleton.
