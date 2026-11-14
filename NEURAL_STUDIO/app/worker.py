"""Read-only worker handoff helper; never executes models, shell commands or AE."""
from pathlib import Path
import argparse
import json
from server import Store, ROOT

parser=argparse.ArgumentParser();parser.add_argument('action',choices=['brief','validate']);parser.add_argument('task_directory',type=Path);args=parser.parse_args()
task_dir=args.task_directory.resolve()
if not task_dir.is_relative_to((ROOT/'stations').resolve()):raise SystemExit('Task must belong to this studio')
task=json.loads((task_dir/'TASK.json').read_text(encoding='utf-8'));store=Store()
expected=store.task_folder(task['station'],task['id'])
if expected!=task_dir:raise SystemExit('Task identity/path mismatch')
if args.action=='brief':print((task_dir/'KICKOFF_PROMPT.txt').read_text(encoding='utf-8'))
else:print(json.dumps(store.validate(task['station'],task_dir),indent=2,ensure_ascii=False))
