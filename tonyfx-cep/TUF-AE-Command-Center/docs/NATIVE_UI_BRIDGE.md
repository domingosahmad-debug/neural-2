# TonyFX native AE interaction â€” v1

The script route and the native window route share **one existing TonyFX command owner**. Native UI is local Windows input directed only at `AfterFX.exe`. It is not another model, a cloud screen service, or a second editor. The ordinary `runScriptFile` route remains available for precise property work.

Commands: `uiCapabilities`, `uiSnapshot`, `uiActivate`, `uiClick`, `uiDoubleClick`, `uiStroke`, `uiScroll`, `uiKey`, `uiText`.

Use `python/native_ui_client.py COMMAND --out RESULT.json`. The client refuses an occupied bridge and matches only the new command's terminal result. An uncertain timeout must be reconciled, never resent.

## Observe, input once, observe again

1. Acquire exclusive editor ownership. A screenshot request still uses the shared bridge; do not compete with a render or another director. Preserve dirty user work before changing project/view state.
2. Call `uiSnapshot`. Read its returned `image` in the vision-capable worker. If more than one AE window is available, select a returned `hwnd` explicitly in `--args` rather than guessing. A background AE snapshot has no image; `uiActivate` is explicit and requires its returned observation.
3. Send one action using `--observation OBSERVATION.json --args JSON`. Use `--args-file ACTION.json` for structured Unicode/multiline JSON payloads without shell quoting. Coordinates are relative to that screenshot's full window. Mouse args are `x,y,button:left|right,modifiers:[ALT|CTRL|SHIFT]`; `uiStroke` uses `points:[[x,y],...]` and `durationMs:100..10000`. `uiScroll` uses `x,y,delta` in Windows wheel units (+120 = one notch up). `uiKey` uses `keys`, e.g. `ALT+W`, `CTRL+S`, `PAGEUP`, `NUMPAD0`. `uiText` uses printable Unicode `text`; send control keys separately. No Windows-key/system shortcuts.
4. Inspect `afterImage`; capture another `uiSnapshot` before the next action. Each observation expires after120 seconds and is consumed by a single input. Changed project, comp/item, frame, selection, tool, focused window, window layout, foreground app or substantial screenshot change refuses input. A partially completed input returns `uncertain`; inspect actual state and do not retry the old observation.

Example (coordinates must come from the real returned screenshot):

```text
python python/native_ui_client.py uiSnapshot --out observation.json
python python/native_ui_client.py uiKey --observation observation.json --args "{\"keys\":\"ALT+W\"}"
```

For CEP bridge JSON producers, use the same `ae_command.json` schema as other commands. Input args include `observationId` and `expectedContext` copied exactly from the screenshot result. TonyFX evaluates current native context immediately before the helper runs; the helper verifies the live command ID and lock owner before input. Evidence is local under the bridge's `ui/` folder.

## Native Roto Brush

Native Roto Brush means opening the footage in the **Layer panel**, selecting Roto Brush or Refine Edge, drawing observed foreground/background strokes, checking propagation through the requested span and freezing only after review. Tool selection, brush size, green/red selection strokes, parameter refinement and span/freeze controls require their own observed actions. They are not replaced by a claim that an alpha sequence is native Roto Brush.

The new primitives make those interactions possible; they do not certify every AE workflow or promise perfect masks automatically. Adobe exposes existing Roto Brush Path properties and some matte controls; native stroke creation/propagation must be verified against the running AE version. A script-only limitation is not proof of a limitation of the model. Screenshot interpretation and frame-by-frame matte acceptance remain necessary.

Never use UI to dismiss an unknown save dialog, discard manual work, control other apps, automate sign-in/security settings, or conceal a failed selection. No automatic GUI retry, bridge lock deletion, competing editor, or project replacement.
