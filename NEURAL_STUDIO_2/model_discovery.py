"""Automatic local model discovery for Antigravity (Gemini) and free OpenCode CLIs."""
import json
import os
from pathlib import Path
import subprocess
import threading

from providers_engine import gemini
from providers_engine.transport import FREE_ID, environment, executable

_SYNC_LOCK = threading.Lock()


def _run_lines(command, timeout=15):
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        env=environment(),
        timeout=timeout,
        creationflags=flags,
    )
    if completed.returncode != 0:
        return []
    return (completed.stdout or '').splitlines()


def discover_agy_models():
    """Return newly discovered high/xhigh/orchestrator Antigravity Gemini models."""
    try:
        cmd = gemini.executable() + ['models']
    except (ValueError, OSError):
        return []
    rows = []
    for raw in _run_lines(cmd, timeout=15):
        line = raw.strip()
        if not line:
            continue
        parts = line.split('\t', 1) if '\t' in line else line.split(None, 1)
        model_id = parts[0].strip()
        if not model_id.startswith('gemini-'):
            continue
        try:
            gemini.validate(model_id, 'high')
        except ValueError:
            continue
        label = (parts[1].strip() if len(parts) > 1 and parts[1].strip() else model_id)
        if '(Antigravity)' not in label:
            label = f'{label} (Antigravity)'
        rows.append({
            'provider': 'gemini',
            'model': model_id,
            'label': label,
            'source': 'Auto-discovered from installed Antigravity subscription catalog; quota checked at invocation',
        })
    return rows


def discover_opencode_free_models():
    """Return free OpenCode models from the installed opencode-cli catalog."""
    try:
        cli = executable('opencode')
    except (ValueError, OSError):
        return []
    desktop = Path(cli).name == 'opencode-cli.exe'
    cmd = [cli, 'models', '--standalone'] if desktop else [cli, 'models', 'opencode', '--pure']
    rows = []
    for raw in _run_lines(cmd, timeout=15):
        model_id = raw.strip()
        if not FREE_ID.fullmatch(model_id):
            continue
        short = model_id.removeprefix('opencode/').removesuffix('-free')
        rows.append({
            'provider': 'opencode',
            'model': model_id,
            'label': f'OpenCode {short} (free)',
            'source': 'Auto-discovered from installed OpenCode CLI catalog; shared free quota; requires tools/opencode_free_probe.py pass before use',
        })
    return rows


def sync_catalog(root):
    """Merge newly discovered local Antigravity & free OpenCode models into model_catalog.json."""
    root = Path(root)
    catalog_path = root / 'model_catalog.json'
    with _SYNC_LOCK:
        if catalog_path.is_file():
            data = json.loads(catalog_path.read_text(encoding='utf-8'))
        else:
            data = {'scope': 'Local model catalog', 'models': []}
        models = list(data.get('models') or [])
        existing = {(m.get('provider'), m.get('model')) for m in models if isinstance(m, dict)}
        discovered = discover_agy_models() + discover_opencode_free_models()
        added = []
        for entry in discovered:
            key = (entry['provider'], entry['model'])
            if key not in existing:
                models.append(entry)
                existing.add(key)
                added.append(entry['model'])
        if added:
            data['models'] = models
            tmp = catalog_path.with_suffix('.json.tmp')
            tmp.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
            tmp.replace(catalog_path)
        return {'added': added, 'total': len(models)}


def sync_catalog_async(root):
    """Run sync_catalog in a background daemon thread without failing startup."""
    def _worker():
        try:
            sync_catalog(root)
        except Exception:
            pass

    thread = threading.Thread(target=_worker, name='neural-model-discovery', daemon=True)
    thread.start()
    return thread
