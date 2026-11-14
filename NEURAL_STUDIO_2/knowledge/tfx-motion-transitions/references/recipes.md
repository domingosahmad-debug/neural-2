# Recipes with their original scope
## User-authored sword match, September 6
Wide sword-loading shot [824,851) to hands/sword close-up [851,893), 30 fps. User S_BlurMoCurves center about [949.954,444.558], Z 1→0.0009918 and rotation 0→101 at exclusive frame 851. Last visible frame 850 actually evaluates to Z 0.5065, rotation 41.88. Copy the attention transfer and acceleration, not these coordinates for unrelated footage.
Directional blur over [848,856), amount 10 at848,73 at851,10 at855; BCC angle144/spread9. This nonzero tail is user-authored. Preserve it in an unrelated repair.

## Earlier normalized easing recipe
For cubic control points (0.09,0.72),(0.94,0.27), scalar duration D and value delta V: outgoing speed = (V/D)*(0.72/0.09), influence9%; incoming speed = (V/D)*((1-0.27)/(1-0.94)), influence6%. Preserve sign for scalar properties. This is a specific historical curve, not universal cinematic easing. Multi-dimensional/spatial AE properties need correct per-dimension/spatial treatment. Verify sampled values rather than merely trusting formula conversion.

## Detailed expanding edge echo
Duplicate actual RGB footage, preserving source time/framing/grade. A matte may restrict RGB coverage; a binary mask used as the edge image loses face/clothing details.
Earlier successful local recipe: S_EdgeDetect Mono Edges, saturation0 → S_Glow brightness1.4/threshold0/width160/Expand Borders → 4ColorGradient same accent at all corners, Soft Light (historical enum19; verify version). Overlay blend Screen, audio off. Opacity 0→100 one frame later→0 at last visible frame; expand only the duplicate from base scale to1.5x. Historical zero-speed Bezier influence90 opacity/82 scale. Tune accent, pivot and duration to shot; don't zoom the base by accident. Deep Glow tutorial values are not identical to S_Glow.

## Twixtor
Historical fast–slow–fast recipes use150–35–150 or160–35–160 percent; select only with reference/user evidence. Native input FPS; integrate speed across duration to determine consumed source time, plus handles (at least two native frames where appropriate). Avoid double processing an already interpolated source. Fix warp artifacts by changing shot/range or method, not hiding them behind stronger glow.

## Quinn res 2 body recipe (Tony, 12 November 2026)

Exact keys: `../../tfx-live-action-accepted-pipeline/references/quinn-res2-accepted-20261112.json` (`zoom`, `cutTransition`, `shots`). Z Dist A: 1.0→0.52, out −2.4545/21.92%, in −2.024/26.77%. B: 0.52→1.0, out 1.5696/31.25%, in 1.9687/27.84%. Final shot: 1.0→0.7 over 25 f, −0.5/50%. Transition Blur Amount: −4 f 0 (out 1183.55/5.99%), cut 44 (in 1591.92/6.78%, out −599.86/19.8%), +4 f 0 (in −909.13/11.24%); Angle 140, Spread 38. Rescale speeds when range/duration change; keep influences.
