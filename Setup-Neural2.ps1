# Neural 2.0 setup for Windows 10/11. Run from the repository root:
#   powershell -ExecutionPolicy Bypass -File .\Setup-Neural2.ps1            (core app)
#   powershell -ExecutionPolicy Bypass -File .\Setup-Neural2.ps1 -Voice     (also local voice/ASR/helper models, ~1.5 GB)
#   powershell -ExecutionPolicy Bypass -File .\Setup-Neural2.ps1 -CheckOnly (report only, installs nothing)
# Downloads only from official sources and verifies SHA-256 where the source publishes fixed files.
param([switch]$Voice, [switch]$CheckOnly, [switch]$SkipTonyFX)
$ErrorActionPreference = 'Stop'
$Repo = $PSScriptRoot
$NS2 = Join-Path $Repo 'NEURAL_STUDIO_2'
$NS1 = Join-Path $Repo 'NEURAL_STUDIO'
$ElectronVersion = '44.7.2'

function Say($m) { Write-Host "[Neural2] $m" }
function Need($ok, $m) { if ($ok) { Say "OK   $m" } else { Say "MISS $m" } }

# ---- 1. Report what is installed --------------------------------------------------------
$py = Get-Command python -ErrorAction SilentlyContinue
$pyOk = $false
if ($py) { & $py.Source -c "import sys; raise SystemExit(0 if sys.version_info >= (3,12) else 1)"; $pyOk = ($LASTEXITCODE -eq 0) }
Need $pyOk 'Python 3.12+ on PATH (python.org installer, tick "Add to PATH")'
$ae = Get-ChildItem "$env:ProgramFiles\Adobe" -Directory -Filter 'Adobe After Effects *' -ErrorAction SilentlyContinue
Need ([bool]$ae) 'Adobe After Effects 2023-2026'
Need ([bool](Get-Command ffmpeg -ErrorAction SilentlyContinue)) 'ffmpeg/ffprobe on PATH (winget install Gyan.FFmpeg)'
Need ([bool](Get-Command git -ErrorAction SilentlyContinue)) 'git'
Need ([bool](Get-Command claude -ErrorAction SilentlyContinue) -or (Test-Path "$HOME\.local\bin\claude.exe")) 'Claude Code CLI (claude)'
Need ([bool](Get-Command codex -ErrorAction SilentlyContinue) -or (Test-Path "$env:LOCALAPPDATA\OpenAI\Codex\bin")) 'Codex CLI (codex) - optional'
Need ([bool](Get-Command opencode -ErrorAction SilentlyContinue) -or (Test-Path "$env:APPDATA\ai.opencode.desktop\cli")) 'OpenCode CLI - optional, free models'
Need ([bool](Get-Command agy -ErrorAction SilentlyContinue) -or (Test-Path "$env:LOCALAPPDATA\agy\bin\agy.exe") -or (Test-Path "$NS1\.tools\agy\agy.exe")) 'Antigravity CLI (agy) - optional, Gemini'
Need (Test-Path "$NS2\runtime\electron.exe") "Electron $ElectronVersion desktop runtime"
if ($CheckOnly) { Say 'Check only. Nothing installed.'; exit 0 }
if (-not $pyOk) { throw 'Install Python 3.12+ first (https://www.python.org/downloads/), then rerun.' }

# ---- 2. Python packages for the companion service --------------------------------------
Say 'Installing Python packages (user site)...'
& $py.Source -m pip install --user --disable-pip-version-check -r (Join-Path $Repo 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'pip install failed.' }

# ---- 3. Electron desktop runtime (official GitHub release) -------------------------------
$rt = Join-Path $NS2 'runtime'
if (-not (Test-Path "$rt\electron.exe")) {
  $zip = Join-Path $env:TEMP "electron-v$ElectronVersion-win32-x64.zip"
  Say "Downloading Electron $ElectronVersion..."
  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
  Invoke-WebRequest "https://github.com/electron/electron/releases/download/v$ElectronVersion/electron-v$ElectronVersion-win32-x64.zip" -OutFile $zip
  New-Item -ItemType Directory -Force $rt | Out-Null
  Expand-Archive $zip -DestinationPath $rt -Force
  Remove-Item $zip
}

# ---- 4. Local folders (data, AE bridge exchange) ----------------------------------------
New-Item -ItemType Directory -Force (Join-Path $NS2 'data') | Out-Null
$bridge = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'ae-mcp-bridge'
New-Item -ItemType Directory -Force $bridge | Out-Null
foreach ($f in 'ae_command.json', 'ae_mcp_result.json') {
  $p = Join-Path $bridge $f
  if (-not (Test-Path $p)) { [IO.File]::WriteAllText($p, '{}', (New-Object Text.UTF8Encoding($false))) }
}
Say "AE bridge exchange folder: $bridge"

# ---- 5. TonyFX After Effects panel (CEP) -------------------------------------------------
if (-not $SkipTonyFX) {
  Say 'Installing the TonyFX panel into your user CEP extensions folder...'
  & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Repo 'tonyfx-cep\TUF-AE-Command-Center\install.ps1')
  Say 'Unsigned CEP panels need PlayerDebugMode=1 for your CSXS version. See SETUP.md step 5 (you set it yourself).'
}

# ---- 6. Optional local voice / ASR / helper models ---------------------------------------
function Get-Verified($url, $dest, $sha) {
  if ((Test-Path $dest) -and ((Get-FileHash $dest -Algorithm SHA256).Hash -eq $sha.ToUpper())) { Say "OK   $(Split-Path $dest -Leaf)"; return }
  New-Item -ItemType Directory -Force (Split-Path $dest) | Out-Null
  Say "Downloading $(Split-Path $dest -Leaf)..."
  Invoke-WebRequest $url -OutFile $dest
  if ((Get-FileHash $dest -Algorithm SHA256).Hash -ne $sha.ToUpper()) { Remove-Item $dest; throw "Hash mismatch: $dest" }
}
if ($Voice) {
  & $py.Source -m pip install --disable-pip-version-check --target "$NS1\.tools\voice-python" kokoro-onnx==0.6.1 soundfile onnxruntime
  & $py.Source -m pip install --disable-pip-version-check --target "$NS1\.tools\helper-python" llama-cpp-python==0.3.36 --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
  & $py.Source -m pip install --disable-pip-version-check --target "$Repo\.caption_deps" faster-whisper==1.2.1
  Get-Verified 'https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/resolve/main/Qwen3-0.6B-Q8_0.gguf' "$NS1\.models\Qwen3-0.6B-Q8_0.gguf" '9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031'
  Get-Verified 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.onnx' "$NS1\.models\kokoro\kokoro-v1.0.onnx" 'beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a'
  Get-Verified 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin' "$NS1\.models\kokoro\voices-v1.0.bin" 'bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d'
  $env:PYTHONPATH = "$Repo\.caption_deps"
  & $py.Source -c "from huggingface_hub import snapshot_download as s; [s('Systran/faster-whisper-'+n, local_dir=r'$NS1\.models\faster-whisper-'+n) for n in ('small.en','base')]"
  Remove-Item Env:PYTHONPATH
}

# ---- 7. Desktop shortcut -----------------------------------------------------------------
$wsh = New-Object -ComObject WScript.Shell
$lnk = $wsh.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Neural 2.0.lnk'))
$lnk.TargetPath = Join-Path $NS2 'Launch-Neural-2.cmd'
$lnk.WorkingDirectory = $NS2
$lnk.Save()
Say 'Done. Sign in to your own AI CLIs (SETUP.md step 6), then open "Neural 2.0" on your desktop.'
