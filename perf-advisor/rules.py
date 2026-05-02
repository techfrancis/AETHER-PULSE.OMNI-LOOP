"""Rule evaluation against metric history.

Each rule reads recent rows from the SQLite db and yields Finding records.
Conservative thresholds — false positives erode trust faster than false
negatives during the bootstrap phase.

Cooldown: each rule has a minimum gap between repeat firings (default 10min)
so a sustained condition produces one alert, not one per poll.
"""

from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from typing import Iterator


@dataclass
class Finding:
    rule_name: str
    severity: str  # 'info' | 'warn' | 'crit'
    message: str
    detail: dict


def _recent(conn: sqlite3.Connection, name: str, source: str, since_ts: float) -> list[tuple[float, float]]:
    rows = conn.execute(
        "SELECT ts, value FROM metrics WHERE name = ? AND source = ? AND ts >= ? ORDER BY ts ASC",
        (name, source, since_ts),
    ).fetchall()
    return [(float(t), float(v)) for t, v in rows]


def _last_finding_ts(conn: sqlite3.Connection, rule_name: str) -> float:
    row = conn.execute("SELECT MAX(ts) FROM findings WHERE rule_name = ?", (rule_name,)).fetchone()
    return float(row[0]) if row and row[0] else 0.0


def _cooldown_ok(conn: sqlite3.Connection, rule_name: str, ts: float, cooldown_sec: int = 600) -> bool:
    return (ts - _last_finding_ts(conn, rule_name)) >= cooldown_sec


def rule_vllm_queue_saturated(conn, ts, params) -> Iterator[Finding]:
    sustained = int(params.get('sustained_minutes', 5)) * 60
    threshold = float(params.get('threshold', 16))
    samples = _recent(conn, 'vllm:num_requests_running', 'vllm', ts - sustained)
    if len(samples) < 3:
        return
    if all(v >= threshold for _, v in samples) and _cooldown_ok(conn, 'vllm_queue_saturated', ts):
        yield Finding(
            rule_name='vllm_queue_saturated',
            severity='warn',
            message=f"vLLM running queue at {threshold:.0f} for >{sustained//60}min — concurrency cap reached",
            detail={'samples': len(samples), 'sustained_sec': sustained, 'threshold': threshold},
        )


def rule_vllm_kv_cache_high(conn, ts, params) -> Iterator[Finding]:
    sustained = int(params.get('sustained_minutes', 2)) * 60
    threshold = float(params.get('threshold_pct', 85)) / 100.0
    samples = _recent(conn, 'vllm:kv_cache_usage_perc', 'vllm', ts - sustained)
    if len(samples) < 2:
        return
    if all(v >= threshold for _, v in samples) and _cooldown_ok(conn, 'vllm_kv_cache_high', ts):
        peak = max(v for _, v in samples)
        yield Finding(
            rule_name='vllm_kv_cache_high',
            severity='warn',
            message=f"KV cache {peak*100:.0f}% sustained >{sustained//60}min — long-context risk",
            detail={'peak_pct': peak * 100, 'sustained_sec': sustained},
        )


def rule_vllm_throughput_drop(conn, ts, params) -> Iterator[Finding]:
    drop_pct = float(params.get('drop_pct', 25)) / 100.0
    baseline_window = int(params.get('baseline_window_minutes', 30)) * 60
    eval_window = int(params.get('eval_window_minutes', 5)) * 60

    samples = _recent(conn, 'vllm:generation_tokens_total', 'vllm', ts - baseline_window)
    if len(samples) < 5:
        return
    eval_start = ts - eval_window
    baseline = [(t, v) for t, v in samples if t < eval_start]
    eval_part = [(t, v) for t, v in samples if t >= eval_start]
    if len(baseline) < 2 or len(eval_part) < 2:
        return
    base_rate = (baseline[-1][1] - baseline[0][1]) / max(baseline[-1][0] - baseline[0][0], 1)
    eval_rate = (eval_part[-1][1] - eval_part[0][1]) / max(eval_part[-1][0] - eval_part[0][0], 1)
    if base_rate <= 0:
        return
    delta = (eval_rate - base_rate) / base_rate
    if delta <= -drop_pct and _cooldown_ok(conn, 'vllm_throughput_drop', ts):
        yield Finding(
            rule_name='vllm_throughput_drop',
            severity='crit',
            message=f"Generation tok/s dropped {abs(delta)*100:.0f}% (baseline {base_rate:.1f} -> now {eval_rate:.1f})",
            detail={'baseline_tok_s': base_rate, 'eval_tok_s': eval_rate, 'drop_pct': abs(delta) * 100},
        )


def rule_synapse_ingest_stalled(conn, ts, params) -> Iterator[Finding]:
    stall = int(params.get('stall_seconds', 300))
    active = _recent(conn, 'ingest_active', 'synapse', ts - 60)
    log_mtime = _recent(conn, 'log_newest_mtime', 'synapse', ts - 60)
    if not active or not log_mtime:
        return
    latest_active = active[-1][1]
    latest_mtime = log_mtime[-1][1]
    if latest_active >= 1.0 and (ts - latest_mtime) > stall and _cooldown_ok(conn, 'synapse_ingest_stalled', ts):
        yield Finding(
            rule_name='synapse_ingest_stalled',
            severity='warn',
            message=f"Synapse ingest log silent for {ts-latest_mtime:.0f}s while marked active",
            detail={'silent_seconds': ts - latest_mtime, 'stall_threshold': stall},
        )


def rule_synapse_cards_per_min_drop(conn, ts, params) -> Iterator[Finding]:
    drop_pct = float(params.get('drop_pct', 25)) / 100.0
    baseline_window = int(params.get('baseline_window_minutes', 60)) * 60
    eval_window = int(params.get('eval_window_minutes', 10)) * 60
    samples = _recent(conn, 'cards_count', 'synapse', ts - baseline_window)
    if len(samples) < 4:
        return
    eval_start = ts - eval_window
    baseline = [(t, v) for t, v in samples if t < eval_start]
    eval_part = [(t, v) for t, v in samples if t >= eval_start]
    if len(baseline) < 2 or len(eval_part) < 2:
        return
    base_rate = (baseline[-1][1] - baseline[0][1]) / max((baseline[-1][0] - baseline[0][0]) / 60, 1)
    eval_rate = (eval_part[-1][1] - eval_part[0][1]) / max((eval_part[-1][0] - eval_part[0][0]) / 60, 1)
    if base_rate <= 0.5:
        return  # not actively ingesting — drop_pct is meaningless
    delta = (eval_rate - base_rate) / base_rate
    if delta <= -drop_pct and _cooldown_ok(conn, 'synapse_cards_per_min_drop', ts):
        yield Finding(
            rule_name='synapse_cards_per_min_drop',
            severity='warn',
            message=f"Synapse cards/min dropped {abs(delta)*100:.0f}% (baseline {base_rate:.2f} -> now {eval_rate:.2f})",
            detail={'baseline_cpm': base_rate, 'eval_cpm': eval_rate, 'drop_pct': abs(delta) * 100},
        )


def rule_synapse_no_recent_activity(conn, ts, params) -> Iterator[Finding]:
    inactive = int(params.get('inactive_minutes', 30)) * 60
    samples = _recent(conn, 'log_newest_mtime', 'synapse', ts - 120)
    if not samples:
        return
    latest = samples[-1][1]
    if latest > 0 and (ts - latest) > inactive and _cooldown_ok(conn, 'synapse_no_recent_activity', ts, cooldown_sec=3600):
        yield Finding(
            rule_name='synapse_no_recent_activity',
            severity='info',
            message=f"No Synapse ingest activity for {(ts-latest)/60:.0f}min",
            detail={'inactive_minutes': (ts - latest) / 60},
        )


RULES = {
    'vllm_queue_saturated': rule_vllm_queue_saturated,
    'vllm_kv_cache_high': rule_vllm_kv_cache_high,
    'vllm_throughput_drop': rule_vllm_throughput_drop,
    'synapse_ingest_stalled': rule_synapse_ingest_stalled,
    'synapse_cards_per_min_drop': rule_synapse_cards_per_min_drop,
    'synapse_no_recent_activity': rule_synapse_no_recent_activity,
}


def evaluate(conn: sqlite3.Connection, ts: float, rules_cfg: dict) -> Iterator[Finding]:
    for name, params in rules_cfg.items():
        if not params.get('enabled', True):
            continue
        fn = RULES.get(name)
        if fn is None:
            continue
        yield from fn(conn, ts, params)
