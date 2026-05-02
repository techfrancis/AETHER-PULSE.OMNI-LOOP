"""AETHER-PULSE perf-advisor — Tier 1 daemon.

Polls vLLM /metrics + Synapse fs every poll_interval_sec. Persists every
numeric metric into a SQLite history db (the substrate Tier 2 will read
to evaluate proposed config changes against this hardware's actual past).
Evaluates a small set of rules over the live stream and emits findings to
findings.jsonl + stdout.

Run:
    python advisor.py --once          # single poll + rule eval, then exit
    python advisor.py                 # daemon mode (Ctrl+C to stop)
    python advisor.py --config x.yaml # alternate config
"""

from __future__ import annotations
import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

import sensors
import rules


SCHEMA = """
CREATE TABLE IF NOT EXISTS configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint TEXT NOT NULL,
    source TEXT NOT NULL,
    summary_json TEXT NOT NULL,
    first_seen REAL NOT NULL,
    UNIQUE(fingerprint, source)
);

CREATE TABLE IF NOT EXISTS metrics (
    ts REAL NOT NULL,
    source TEXT NOT NULL,
    config_id INTEGER,
    name TEXT NOT NULL,
    value REAL NOT NULL,
    FOREIGN KEY(config_id) REFERENCES configs(id)
);

CREATE INDEX IF NOT EXISTS idx_metrics_ts ON metrics(ts);
CREATE INDEX IF NOT EXISTS idx_metrics_name_ts ON metrics(name, ts);

CREATE TABLE IF NOT EXISTS findings (
    ts REAL NOT NULL,
    rule_name TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    detail_json TEXT
);
"""


def expand_path(p: str) -> Path:
    return Path(p).expanduser().resolve()


def load_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding='utf-8'))


def open_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def upsert_config(conn: sqlite3.Connection, source: str, fingerprint: str, summary: dict, ts: float) -> int:
    row = conn.execute(
        "SELECT id FROM configs WHERE source = ? AND fingerprint = ?",
        (source, fingerprint),
    ).fetchone()
    if row:
        return row[0]
    cur = conn.execute(
        "INSERT INTO configs (fingerprint, source, summary_json, first_seen) VALUES (?, ?, ?, ?)",
        (fingerprint, source, json.dumps(summary), ts),
    )
    conn.commit()
    return cur.lastrowid


def write_metrics(conn: sqlite3.Connection, ts: float, source: str, config_id: int | None, metrics: dict[str, float]) -> int:
    rows = [
        (ts, source, config_id, k, float(v))
        for k, v in metrics.items()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    ]
    conn.executemany(
        "INSERT INTO metrics (ts, source, config_id, name, value) VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    return len(rows)


def emit_finding(conn: sqlite3.Connection, findings_log: Path, ts: float, finding: rules.Finding) -> None:
    conn.execute(
        "INSERT INTO findings (ts, rule_name, severity, message, detail_json) VALUES (?, ?, ?, ?, ?)",
        (ts, finding.rule_name, finding.severity, finding.message, json.dumps(finding.detail)),
    )
    conn.commit()
    record = {
        'ts': ts,
        'iso': datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
        'rule': finding.rule_name,
        'severity': finding.severity,
        'message': finding.message,
        'detail': finding.detail,
    }
    findings_log.parent.mkdir(parents=True, exist_ok=True)
    with findings_log.open('a', encoding='utf-8') as f:
        f.write(json.dumps(record) + '\n')
    sev_marker = {'info': 'i', 'warn': '!', 'crit': '!!'}.get(finding.severity, '?')
    stamp = datetime.fromtimestamp(ts).strftime('%H:%M:%S')
    print(f"[{stamp}] {sev_marker} {finding.rule_name}: {finding.message}", flush=True)


def poll_once(conn: sqlite3.Connection, cfg: dict, findings_log: Path, verbose: bool = False) -> dict:
    """Run one poll cycle. Returns counts for the caller's status line."""
    ts = time.time()
    summary = {'vllm_metrics': 0, 'synapse_metrics': 0, 'findings': 0}
    sensors_cfg = cfg.get('sensors', {})

    if sensors_cfg.get('vllm', {}).get('enabled', True):
        vc = sensors_cfg['vllm']
        config_id = None
        fp = sensors.vllm_config_fingerprint(vc.get('config_command', ['docker', 'inspect', 'nexus_vllm_native']))
        if fp:
            config_id = upsert_config(conn, 'vllm', fp[0], fp[1], ts)
        metrics = sensors.poll_vllm(vc['metrics_url'])
        if metrics:
            summary['vllm_metrics'] = write_metrics(conn, ts, 'vllm', config_id, metrics)

    if sensors_cfg.get('synapse', {}).get('enabled', True):
        sc = sensors_cfg['synapse']
        config_id = None
        fp = sensors.synapse_config_fingerprint(expand_path(sc['config_path']))
        if fp:
            config_id = upsert_config(conn, 'synapse', fp[0], fp[1], ts)
        snapshot = sensors.poll_synapse(
            expand_path(sc['data_dir']),
            expand_path(sc['storage_dir']),
            expand_path(sc['logs_dir']),
        )
        numeric = {k: v for k, v in snapshot.items() if k != 'log_newest_path'}
        summary['synapse_metrics'] = write_metrics(conn, ts, 'synapse', config_id, numeric)

    for finding in rules.evaluate(conn, ts, cfg.get('rules', {})):
        emit_finding(conn, findings_log, ts, finding)
        summary['findings'] += 1

    if verbose:
        stamp = datetime.fromtimestamp(ts).strftime('%H:%M:%S')
        print(f"[{stamp}] poll: vllm={summary['vllm_metrics']} synapse={summary['synapse_metrics']} findings={summary['findings']}", flush=True)

    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description="AETHER-PULSE perf-advisor (Tier 1)")
    ap.add_argument('--config', default=str(Path(__file__).parent / 'config.yaml'))
    ap.add_argument('--once', action='store_true', help='Run a single poll cycle, then exit.')
    ap.add_argument('--verbose', action='store_true', help='Print a status line per poll.')
    args = ap.parse_args()

    cfg_path = Path(args.config)
    if not cfg_path.is_file():
        print(f"[advisor] config not found: {cfg_path}", file=sys.stderr)
        return 2
    cfg = load_config(cfg_path)

    db_path = expand_path(cfg['storage']['history_db'])
    findings_log = expand_path(cfg['storage']['findings_log'])
    interval = int(cfg.get('poll_interval_sec', 60))

    print(f"[advisor] history db: {db_path}", flush=True)
    print(f"[advisor] findings:   {findings_log}", flush=True)
    print(f"[advisor] poll every: {interval}s", flush=True)

    conn = open_db(db_path)
    try:
        if args.once:
            poll_once(conn, cfg, findings_log, verbose=True)
            return 0
        while True:
            try:
                poll_once(conn, cfg, findings_log, verbose=args.verbose)
            except Exception as e:
                print(f"[advisor] poll error: {e!r}", file=sys.stderr, flush=True)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[advisor] shutdown requested", flush=True)
    finally:
        conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
