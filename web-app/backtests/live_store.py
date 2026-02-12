from __future__ import annotations

import json
import os
import signal
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LivePaths:
  session_dir: Path
  params_json: Path
  status_json: Path
  snapshot_json: Path
  stdout_log: Path
  stderr_log: Path


def _now_iso() -> str:
  return datetime.now(tz=timezone.utc).isoformat()


def live_root(base_dir: Path) -> Path:
  return base_dir / 'var' / 'live'


def ensure_live_dirs(base_dir: Path) -> None:
  live_root(base_dir).mkdir(parents=True, exist_ok=True)


def active_session_path(base_dir: Path) -> Path:
  return live_root(base_dir) / 'active.json'


def get_active_session_id(base_dir: Path) -> str | None:
  p = active_session_path(base_dir)
  if not p.exists():
    return None
  try:
    data = json.loads(p.read_text(encoding='utf-8'))
    sid = data.get('session_id') if isinstance(data, dict) else None
    return str(sid) if sid else None
  except Exception:
    return None


def set_active_session_id(base_dir: Path, session_id: str | None) -> None:
  p = active_session_path(base_dir)
  if session_id is None:
    try:
      if p.exists():
        p.unlink()
    except Exception:
      pass
    return
  try:
    p.write_text(json.dumps({'session_id': session_id, 'updated_at': _now_iso()}, indent=2), encoding='utf-8')
  except Exception:
    pass


def create_live_session(base_dir: Path, params: dict[str, Any]) -> tuple[str, LivePaths]:
  ensure_live_dirs(base_dir)
  session_id = str(uuid.uuid4())
  session_dir = live_root(base_dir) / session_id
  session_dir.mkdir(parents=True, exist_ok=False)

  paths = LivePaths(
    session_dir=session_dir,
    params_json=session_dir / 'params.json',
    status_json=session_dir / 'status.json',
    snapshot_json=session_dir / 'snapshot.json',
    stdout_log=session_dir / 'stdout.log',
    stderr_log=session_dir / 'stderr.log',
  )

  paths.params_json.write_text(json.dumps(params, indent=2, default=str), encoding='utf-8')
  paths.status_json.write_text(
    json.dumps(
      {
        'session_id': session_id,
        'state': 'queued',
        'created_at': _now_iso(),
        'updated_at': _now_iso(),
        'pid': None,
        'python_executable': None,
        'returncode': None,
        'error': None,
        'latest_seq': 0,
      },
      indent=2,
    ),
    encoding='utf-8',
  )

  paths.snapshot_json.write_text(json.dumps({'symbols': {}, 'stats': {}}, indent=2), encoding='utf-8')

  return session_id, paths


def read_live_status(paths: LivePaths) -> dict[str, Any]:
  if not paths.status_json.exists():
    return {'state': 'unknown', 'error': 'Missing status.json'}
  last_err: Exception | None = None
  for attempt in range(6):
    try:
      return json.loads(paths.status_json.read_text(encoding='utf-8'))
    except (PermissionError, json.JSONDecodeError) as e:
      last_err = e
      time.sleep(0.03 * (attempt + 1))
    except Exception as e:
      last_err = e
      break
  return {'state': 'unknown', 'error': f'Failed to read status.json: {last_err}'}


def write_live_status(paths: LivePaths, patch: dict[str, Any]) -> None:
  status = read_live_status(paths)
  status.update(patch)
  status['updated_at'] = _now_iso()
  # Atomic write (Windows-friendly): write temp then replace, retry briefly if locked.
  tmp = paths.status_json.with_name(paths.status_json.name + f'.{os.getpid()}.tmp')
  tmp.write_text(json.dumps(status, indent=2), encoding='utf-8')
  last_err: Exception | None = None
  for attempt in range(6):
    try:
      os.replace(tmp, paths.status_json)
      last_err = None
      break
    except PermissionError as e:
      last_err = e
      time.sleep(0.03 * (attempt + 1))
  if last_err is not None:
    try:
      if tmp.exists():
        tmp.unlink()
    except Exception:
      pass
    return


def tail_text_file(path: Path, max_bytes: int = 32_000) -> str:
  if not path.exists():
    return ''
  try:
    with path.open('rb') as f:
      f.seek(0, os.SEEK_END)
      size = f.tell()
      start = max(0, size - max_bytes)
      f.seek(start)
      return f.read().decode('utf-8', errors='replace')
  except Exception as e:
    return f'[tail error] {e}'


def stop_session_pid(pid: int | None) -> bool:
  if not pid:
    return False
  try:
    os.kill(int(pid), signal.SIGTERM)
    return True
  except Exception:
    return False
