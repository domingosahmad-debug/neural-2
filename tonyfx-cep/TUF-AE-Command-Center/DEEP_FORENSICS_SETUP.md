# TonyFX 0.50 Deep Transition Forensics

TonyFX installs as a private CEP extension for After Effects 2023-2026.

## Install The Panel

Run `install.cmd`, close any open TonyFX panel, then reopen `Window > Extensions > TonyFX`.

## Install Or Repair Local Models

Open TonyFX `Analyze` and choose `Setup`. The idempotent setup keeps a compatible CUDA PyTorch installation and installs only missing components.

The complete Deep stack contains:

- Torchvision RAFT Small
- LightGlue with ALIKED
- TransNetV2
- Video Depth Anything Small
- Existing SAM 2.1, CoTracker 3, Depth Anything V2, OpenCLIP, DINOv2, YOLO11, FAISS, and analyzer dependencies

Repositories and model weights are stored outside the extension so updating the panel cannot delete them:

- `C:\Users\TUF\Documents\TonyFX Vision Engine\packages`
- `C:\Users\TUF\Documents\TonyFX Vision Engine\models`
- `C:\Users\TUF\Documents\TonyFX Local Engine`

## Verify

After Setup, TonyFX Analyze should report `Deep transition forensics ready`. Deep Analyze produces a V4 JSON blueprint, HTML report, and evidence contact sheet. Model processing is local and does not consume Codex or OpenAI API usage.
