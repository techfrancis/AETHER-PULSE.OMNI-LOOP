"""Sensors: poll vLLM /metrics + Synapse filesystem; return canonical dicts.

Outputs:
- poll_vllm() returns flat metric_name -> float dict (Prometheus exposition).
- poll_synapse() returns activity snapshot (cards_count, storage_bytes,
  ingest_active, log mtimes).
- *_config_fingerprint() return (sha256_short, summary_dict) for diffing
  against the SQLite configs table.

Sensors are pure: no DB, no logging side-effects. The advisor module wires
them to the history writer and rule engine.
"""

from __future__ import annotations
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any

import requests
import yaml


# Prometheus exposition: NAME{LABELS} VALUE  — labels optional.
_METRIC_LINE = re.compile(r'^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{[^}]*\})?\s+([0-9eE.+-]+)')


def parse_vllm_metrics(text: str) -> dict[str, float]:
    """Parse Prometheus exposition format. First-occurrence wins per metric.

    vLLM is single-engine here so labels are constant — collapsing to
    first-occurrence keeps the schema flat without losing signal.
    """
    out: dict[str, float] = {}
    for line in text.splitlines():
        if not line or line.startswith('#'):
            continue
        m = _METRIC_LINE.match(line)
        if not m:
            continue
        name, value = m.group(1), m.group(2)
        if name in out:
            continue
        try:
            out[name] = float(value)
        except ValueError:
            continue
    return out


def poll_vllm(metrics_url: str, timeout: int = 5) -> dict[str, float] | None:
    try:
        r = requests.get(metrics_url, timeout=timeout)
        r.raise_for_status()
    except requests.RequestException:
        return None
    return parse_vllm_metrics(r.text)


def vllm_config_fingerprint(config_command: list[str]) -> tuple[str, dict[str, Any]] | None:
    """Hash docker inspect of the vLLM container into a stable fingerprint.

    None when the container isn't running.
    """
    try:
        result = subprocess.run(config_command, capture_output=True, text=True, timeout=10)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if not data:
        return None
    container = data[0]
    args = container.get('Args', []) or []
    env = sorted(container.get('Config', {}).get('Env', []) or [])
    image = container.get('Config', {}).get('Image', '')
    fingerprint_input = json.dumps({'image': image, 'args': args, 'env': env}, sort_keys=True)
    digest = hashlib.sha256(fingerprint_input.encode()).hexdigest()[:16]
    summary = {'cmd': ' '.join(args), 'image': image}
    return digest, summary


def _dir_size(p: Path) -> int:
    total = 0
    for f in p.glob('**/*'):
        try:
            if f.is_file():
                total += f.stat().st_size
        except OSError:
            continue
    return total


def poll_synapse(data_dir: Path, storage_dir: Path, logs_dir: Path, active_threshold_sec: int = 180) -> dict[str, Any]:
    """Activity snapshot of the Synapse host-side state."""
    now = time.time()
    out: dict[str, Any] = {}

    if data_dir.is_dir():
        cards = list(data_dir.glob('**/*.md'))
        out['cards_count'] = len(cards)
        out['data_newest_mtime'] = max((p.stat().st_mtime for p in cards), default=0.0)
    else:
        out['cards_count'] = 0
        out['data_newest_mtime'] = 0.0

    out['storage_bytes'] = _dir_size(storage_dir) if storage_dir.is_dir() else 0

    if logs_dir.is_dir():
        logs = sorted(logs_dir.glob('ingest-*.log'), key=lambda p: p.stat().st_mtime, reverse=True)
        if logs:
            mtime = logs[0].stat().st_mtime
            out['log_newest_path'] = str(logs[0])
            out['log_newest_mtime'] = mtime
            out['ingest_active'] = 1.0 if (now - mtime) < active_threshold_sec else 0.0
        else:
            out['log_newest_path'] = None
            out['log_newest_mtime'] = 0.0
            out['ingest_active'] = 0.0
    else:
        out['log_newest_path'] = None
        out['log_newest_mtime'] = 0.0
        out['ingest_active'] = 0.0

    return out


def synapse_config_fingerprint(config_path: Path) -> tuple[str, dict[str, Any]] | None:
    if not config_path.is_file():
        return None
    text = config_path.read_text(encoding='utf-8')
    digest = hashlib.sha256(text.encode()).hexdigest()[:16]
    try:
        cfg = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return digest, {}
    summary = {
        'concurrency': cfg.get('dendrite', {}).get('concurrency'),
        'model': cfg.get('llm', {}).get('model'),
        'context_window': cfg.get('llm', {}).get('context_window'),
        'request_timeout': cfg.get('llm', {}).get('request_timeout'),
        'embed_provider': cfg.get('embed_model', {}).get('provider'),
    }
    return digest, summary
