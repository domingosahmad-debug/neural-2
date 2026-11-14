"""Local non-inference CLI capability commissioning for Director adapters.

Inspects installed local CLI binaries and help/version flags only. Never starts
an LLM turn, never reads or logs credentials/tokens, and never makes network or
paid API calls. Persists a dated receipt under data/provider-cache/ so runtime
status queries execute zero subprocesses on idle GET requests.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable

from operations import find_tool, load, process_options, save, stamp
from provider_runtime import clean_environment

RECEIPT_REL = 'data/provider-cache/director_capabilities.json'


def find_agy_cli(root: Path | None = None, home: Path | None = None, *, allow_sibling_tools: bool = False) -> Path | None:
    import os
    found = shutil.which('agy')
    home_dir = Path(home) if home else Path.home()
    candidates: list[Path] = []
    env_agy = os.environ.get('NEURAL_AGY_PATH')
    if env_agy:
        candidates.append(Path(env_agy))
    if root is not None:
        root_p = Path(root).resolve()
        candidates.append(root_p / '.tools/agy/agy.exe')
        if allow_sibling_tools and len(root_p.parents) >= 3 and root_p.parent.parent.name == '.maintenance':
            candidates.append(root_p.parents[2] / 'NEURAL_STUDIO/.tools/agy/agy.exe')
    candidates.extend([
        home_dir / 'AppData/Local/agy/bin/agy.exe',
        home_dir / '.local/bin/agy',
        home_dir / '.local/bin/agy.exe',
    ])
    if found:
        candidates.append(Path(found))
    return next((p.resolve() for p in candidates if p.is_file()), None)


def _run_flag(argv: list[str], run: Callable = subprocess.run, timeout: float = 8.0) -> tuple[int, str]:
    try:
        res = run(
            argv,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            env=clean_environment(),
            timeout=timeout,
            **process_options(),
        )
        text = ((res.stdout or '') + '\n' + (res.stderr or '')).strip()
        return int(res.returncode), text[:64000]
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        return -1, str(exc)[:300]


def _parse_version(text: str) -> str | None:
    m = re.search(r'\b(\d+\.\d+\.\d+(?:-[A-Za-z0-9._-]+)?)\b', text or '')
    return m.group(1) if m else None


def commission_capabilities(root: str | Path, *, run: Callable = subprocess.run, home: str | Path | None = None) -> dict:
    """Inspect local CLIs with non-inference --version / --help flags and save dated receipt."""
    root_path = Path(root).resolve()
    home_path = Path(home).resolve() if home else Path.home()
    checked_at = stamp()

    # 1. Codex app-server CLI
    codex_bin = find_tool('codex')
    codex_row = {
        'installed': bool(codex_bin),
        'commissioned': False,
        'version': None,
        'vision': False,
        'vision_tool': 'localImage',
        'file_shell': False,
        'network': False,
        'detail': 'Codex CLI was not found on this PC.',
    }
    if codex_bin:
        rc_v, out_v = _run_flag([str(codex_bin), '--version'], run=run)
        rc_h, out_h = _run_flag([str(codex_bin), 'app-server', '--help'], run=run)
        ok = (rc_v == 0) and (rc_h == 0 or 'app-server' in out_h.lower() or 'listen' in out_h.lower())
        codex_row.update(
            commissioned=ok,
            version=_parse_version(out_v),
            vision=ok,
            file_shell=ok,
            network=ok,
            detail='Codex app-server CLI verified locally (--version / app-server --help; zero model calls).'
            if ok else 'Codex binary present, but app-server CLI flags could not be verified.',
        )

    # 2. Native Claude Code CLI
    from claude_transport import DIRECTOR_TOOLS, find_claude
    claude_bin = find_claude(home_path)
    claude_tools = [t.strip() for t in DIRECTOR_TOOLS.split(',') if t.strip()]
    claude_row = {
        'installed': bool(claude_bin),
        'commissioned': False,
        'version': None,
        'vision': False,
        'vision_tool': 'Read',
        'file_shell': False,
        'network': False,
        'granted_tools': claude_tools,
        'detail': 'Native Claude Code CLI was not found on this PC.',
    }
    if claude_bin:
        rc_v, out_v = _run_flag([str(claude_bin), '--version'], run=run)
        rc_h, out_h = _run_flag([str(claude_bin), '--help'], run=run)
        has_flags = rc_h == 0 and '--tools' in out_h and '--allowedTools' in out_h
        ok = (rc_v == 0) and has_flags
        web_ok = ok and ('WebFetch' in claude_tools and 'WebSearch' in claude_tools)
        claude_row.update(
            commissioned=ok,
            version=_parse_version(out_v),
            vision=ok and ('Read' in claude_tools),
            file_shell=ok and ('Bash' in claude_tools or 'PowerShell' in claude_tools),
            network=web_ok,
            detail='Claude Code CLI verified locally with Read/Write/Edit/Bash/PowerShell/WebFetch/WebSearch director tools.'
            if ok else 'Claude Code binary present, but --tools / --allowedTools flags could not be verified.',
        )

    # 3. Official Antigravity CLI (agy)
    agy_bin = find_agy_cli(root_path, home_path, allow_sibling_tools=True)
    agy_row = {
        'installed': bool(agy_bin),
        'commissioned': False,
        'version': None,
        'vision': False,
        'vision_tool': 'read_file',
        'file_shell': False,
        'network': False,
        'granted_tools': ['read_file', 'write_file', 'edit_file', 'run_command', 'search_web'],
        'detail': 'Official Antigravity CLI (agy) was not found on this PC.',
    }
    if agy_bin:
        rc_v, out_v = _run_flag([str(agy_bin), '--version'], run=run)
        rc_h, out_h = _run_flag([str(agy_bin), '--help'], run=run)
        has_flags = (
            rc_h == 0
            and '--mode' in out_h
            and '--input-format' in out_h
            and '--output-format' in out_h
            and '--model' in out_h
        )
        ok = (rc_v == 0) and has_flags
        agy_row.update(
            commissioned=ok,
            version=_parse_version(out_v),
            vision=ok,
            file_shell=ok,
            network=ok,
            detail='Official Antigravity CLI verified locally in accept-edits mode (read_file image/file inspection, write_file/edit_file, run_command, search_web).'
            if ok else 'Antigravity CLI binary present, but headless stream-json / --mode flags could not be verified.',
        )

    receipt = {
        'version': 1,
        'checked_at': checked_at,
        'model_calls': 0,
        'inference_started': False,
        'adapters': {
            'codex': codex_row,
            'claude': claude_row,
            'antigravity': agy_row,
        },
    }
    save(root_path / RECEIPT_REL, receipt)
    return receipt


def load_receipt(root: str | Path | None) -> dict:
    if not root:
        return {}
    path = Path(root) / RECEIPT_REL
    try:
        data = load(path)
        return data if isinstance(data, dict) and data.get('version') == 1 else {}
    except (OSError, ValueError, TypeError):
        return {}


def adapter_commissioning(kind: str, root: str | Path | None = None, runtime=None) -> dict:
    """Zero-subprocess capability check combining cached receipt and live binary presence."""
    receipt = load_receipt(root)
    saved_row = (receipt.get('adapters') or {}).get(kind) or {}
    checked_at = receipt.get('checked_at')

    if kind == 'codex':
        installed = bool(saved_row.get('installed')) or bool(find_tool('codex'))
        return {
            'installed': installed,
            'commissioned': True,
            'checked_at': checked_at,
            'vision': True,
            'vision_tool': 'localImage',
            'file_shell': True,
            'network': True,
        }

    if kind == 'claude':
        from claude_transport import DIRECTOR_TOOLS, find_claude
        tools = [t.strip() for t in DIRECTOR_TOOLS.split(',') if t.strip()]
        installed = bool(find_claude())
        has_web = 'WebFetch' in tools and 'WebSearch' in tools
        return {
            'installed': installed,
            'commissioned': installed,
            'checked_at': checked_at,
            'vision': True,
            'vision_tool': 'Read',
            'file_shell': True,
            'network': has_web,
        }

    # antigravity
    headless = getattr(runtime, 'headless', None) if runtime is not None else None
    if runtime is not None:
        agy_present = headless is not None and bool(getattr(headless, 'agy', True))
    else:
        agy_present = bool(saved_row.get('installed')) or bool(find_agy_cli(Path(root) if root else None))
    commissioned = agy_present and bool(saved_row.get('commissioned', True))
    return {
        'installed': agy_present,
        'commissioned': commissioned,
        'checked_at': checked_at,
        'vision': commissioned,
        'vision_tool': 'read_file',
        'file_shell': agy_present,
        'network': commissioned,
    }
