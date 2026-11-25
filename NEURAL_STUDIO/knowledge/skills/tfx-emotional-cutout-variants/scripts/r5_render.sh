#!/usr/bin/env bash
S="C:/Users/TUF/Documents/TFX_ANTIGRAVITY_STUDIO/sessions/MENTALIST_JANE_SAD_20261120"
AR="/c/Program Files/Adobe/Adobe After Effects 2024/Support Files/aerender.exe"
cd "$S" || exit 2
for V in V5A V5B V6A V6B; do
  "$AR" -project "$(cygpath -w "$S/MENTALIST_JANE_$V.aep")" -comp "JANE_$V" -OMtemplate "H.264 - Match Render Settings - 15 Mbps" -output "$(cygpath -w "$S/proof/proof_${V}_r5.mp4")" > "proof/render_${V}_r5.log" 2>&1
  echo "$V exit $? $(ls proof/proof_${V}_r5.mp4 2>/dev/null)"
done
