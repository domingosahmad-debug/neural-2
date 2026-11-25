#!/usr/bin/env bash
# usage: r5_build_one.sh VAR OPEN_AEP_NAME   -- reset guard (closes OPEN_AEP only if clean) then build VAR. Stops on any non-ok.
set -u
S="C:/Users/TUF/Documents/TFX_ANTIGRAVITY_STUDIO/sessions/MENTALIST_JANE_SAD_20261120"
B="C:/Users/TUF/Documents/New project/NEURAL_STUDIO/knowledge/skills/tfx-tonyfx-execution/scripts"
V="$1"; G="$2"
cd "$S" || exit 2
python scripts/gen_variant_jsx.py "$V" "$G" || exit 3
t0=$(date +%s)
( cd "$B" && python bridge.py --bridge-dir C:/Users/TUF/Documents/ae-mcp-bridge --wait-seconds 60 dispatch "$S/jsx/${V}_reset.jsx" ) | tail -3
r="jsx/${V}_reset_report.txt"
if [ ! -f "$r" ] || [ "$(stat -c %Y "$r")" -lt "$t0" ]; then echo "RESET REPORT NOT FRESH - stop (do not replay)"; exit 4; fi
echo "reset: $(cat "$r")"
case "$(cat "$r")" in ok*) ;; *) echo "RESET GUARD - stop"; exit 5;; esac
t1=$(date +%s)
( cd "$B" && python bridge.py --bridge-dir C:/Users/TUF/Documents/ae-mcp-bridge --wait-seconds 60 dispatch "$S/jsx/${V}_build.jsx" ) | tail -3
r="jsx/${V}_build_report.json"
if [ ! -f "$r" ] || [ "$(stat -c %Y "$r")" -lt "$t1" ]; then echo "BUILD REPORT NOT FRESH - stop (do not replay)"; exit 6; fi
python -c "import json;d=json.load(open('$r'));print('build ok',d.get('ok'),'layers',d.get('numLayers'),'saved',d.get('saved'),'err',d.get('err'),'warn',d.get('warn')[:8])"
