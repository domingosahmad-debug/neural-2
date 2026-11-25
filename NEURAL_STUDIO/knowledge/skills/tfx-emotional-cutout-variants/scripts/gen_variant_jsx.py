"""Generate backslash-free AE build JSX for the four Jane variants (V5A, V5B, V6A, V6B).

Each variant = v4 main edit (plan/shot_plan.json + plan/grade_v3.json) offset by M frames,
plus extra clips (cold open / montage / inserts / outro), FX layers and subtitles.
Usage: python scripts/gen_variant_jsx.py V5A   -> jsx/V5A_build.jsx and jsx/V5A_reset.jsx (reset guards on a given AEP name)
"""
import json, subprocess, sys
from pathlib import Path

S = Path("C:/Users/TUF/Documents/TFX_ANTIGRAVITY_STUDIO/sessions/MENTALIST_JANE_SAD_20261120")
SP = S.as_posix()
plan = json.load(open(S / "plan/shot_plan.json"))
grade = json.load(open(S / "plan/grade_v3.json"))
FPS = 30
P = "src/The Mentalist S01E01 Pilot.mp4"
E = "src/The Mentalist S01E02 Red Hair and Silver Tape.mp4"
SONG_T0 = plan["audio"]["song_time_at_frame0_s"]
WARM = {"desat": -100}
BEATS = [389.4, 401.2, 413.1, 425.6, 438.2, 450.7, 463.2, 475.1, 487.6, 500.2, 513.4, 526.6, 539.9, 553.1,
         567.0, 581.0, 594.2, 607.4, 621.4, 634.6, 647.8, 660.4]


def C(src, f0, f1, inS, **o):
    d = {"src": src, "f": [f0, f1], "in": inS}
    d.update(o)
    return d


def subs_for(clip, lines):
    """lines: [(t0,t1,text)] in source seconds -> [(abs f0, abs f1, text)]"""
    f0, inS = clip["f"][0], clip["in"]
    out = []
    for t0, t1, tx in lines:
        a = int(round(f0 + (max(t0, inS) - inS) * FPS))
        b = int(round(f0 + (t1 - inS) * FPS)) + 2
        out.append([a, min(b, clip["f"][1]), tx])
    return out


LCACHE = S / "plan/luma_cache.json"
_lc = json.load(open(LCACHE)) if LCACHE.exists() else {}


def luma(src, t0, dur):
    """mean gray luma (0-255) of 3 frames across [t0, t0+dur] of src (cached)."""
    import numpy as np
    a = (Path(src) if Path(src).is_absolute() else S / src).as_posix()
    k = f"{a}|{t0:.3f}|{dur:.3f}"
    if k not in _lc:
        vals = []
        for fr in (0.15, 0.5, 0.85):
            raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t0 + dur * fr:.3f}", "-i", a, "-frames:v", "1", "-vf", "scale=160:90,format=gray",
                                  "-f", "rawvideo", "-"], capture_output=True).stdout
            if raw:
                vals.append(float(np.frombuffer(raw, np.uint8).mean()))
        _lc[k] = sum(vals) / len(vals) if vals else 100.0
        json.dump(_lc, open(LCACHE, "w"), indent=0)
    return _lc[k]


def auto_gamma(src, t0, dur, target):
    import math
    L = max(4.0, min(250.0, luma(src, t0, dur)))
    T = max(4.0, min(250.0, target))
    g = math.log(L / 255) / math.log(T / 255)
    return round(max(0.6, min(2.3, g)), 3)


# ---------------------------------------------------------------- variant configs
V = {}

# V5A "Flashback": warm sepia memories, letterbox, grain, light leaks, glow on cutouts.
M = 29
g_lift = [1.8, 1.6, 1.33]
g_mid, g_dark, g_bright = [1.0, 0.88, 0.72], [1.55, 1.38, 1.15], [0.78, 0.68, 0.56]
V["V5A"] = dict(
    title="Flashback", M=M, total=M + 738, drop=[0], shift={},
    extras=[
        C(E, 0, 28, 1707.55, look=dict(desat=-100, gamma=[0.9, 0.8, 0.66], contrast=20), zoom=1.08, name="HOOK the note"),
        C(P, M + 0, M + 30, 1754.6, look=dict(desat=-100, gamma=g_lift), zoom=1.04, xf=10, name="MONT smile"),
        C(P, M + 31, M + 55, 1812.0, look=dict(desat=-100, gamma=g_bright), zoom=1.04, xf=8, name="MONT tv"),
        C(P, M + 56, M + 80, 1818.0, look=dict(desat=-100, gamma=g_lift), zoom=1.05, xf=8, name="MONT car night"),
        C(P, M + 81, M + 104, 1823.0, look=dict(desat=-100, gamma=[1.95, 1.72, 1.42]), zoom=1.05, xf=8, name="MONT house night"),
        C(E, M + 105, M + 125, 1708.985, look=dict(desat=-100, gamma=g_mid, contrast=25), zoom=1.06, xf=8, xo=8, speed=0.75, name="MONT grey suit"),
        C(P, M + 668, M + 737, 1763.7, look=dict(desat=-100, gamma=g_lift), zoom=1.08,
          op=[[M + 668, 0], [M + 678, 100], [M + 724, 100], [M + 737, 0]], name="OUTRO laugh"),
    ],
    grade_from=0,
    letterbox=[],
    grain=dict(f=[0, M + 737], amount=7),
    glow=[[M + 371, M + 406], [M + 463, M + 511]],
    leaks=[M + 369, M + 407, M + 451, M + 512, M + 567],
    flicker=[],
    vignette=[[0, M + 125]],
    song=[[M + 668, 0], [M + 737, -40]],
    subs=[], sub_style=None,
    bgstyle="steady", capstyle="r5",
)

# V5B "Red John": red/black grade, smiley hook + inserts, shake + directional blur hits, smiley outro push.
M = 29
hits = [389.4, 413.1, 438.2, 463.2, 487.6, 513.4, 539.9, 594.2, 621.4, 647.8]
V["V5B"] = dict(
    title="Red John", M=M, total=M + 738, drop=[0], shift={},
    extras=[
        C(P, 0, 28, 1877.0, look=dict(gamma=[1.15, 0.95, 0.9]), zoom=1.1, name="HOOK smiley"),
        C(E, M + 0, M + 125, 1710.01, speed=0.75, look=dict(desat=-30, gamma=[1.1, 0.95, 0.92]), zoom=1.08, xf=10, xo=8, name="SLOT0 jane closeup slow"),
    ] + [C(P, M + a, M + b, 1877.0, look=dict(desat=-40, exposure=1.3, contrast=60), zoom=1.05, blend="MULTIPLY",
           op=[[M + a, 0], [M + a + 14, pk], [M + b - 14, pk], [M + b, 0]], name=f"GHOST smiley {a}")
         for a, b, pk in ((16, 56, 34), (70, 110, 40))] + [
        C(P, M + 668, M + 737, 1878.4, look=dict(gamma=[1.2, 0.9, 0.85]), zoom=1.3, glow=dict(th=78, r=25, i=0.35),
          op=[[M + 668, 0], [M + 672, 100], [M + 722, 100], [M + 737, 0]], name="OUTRO smiley push"),
    ],
    grade_from=0,
    redgrade=dict(f=[0, M + 667], desat=-70, gamma=[1.25, 0.8, 0.72]),
    vignette=[[0, M + 667]],
    grain=dict(f=[0, M + 737], amount=4),
    shake=dict(f=[M + 371, M + 667], hits=[M + h for h in hits]),
    glow=[[M + 371, M + 406], [M + 463, M + 511]],
    flicker=[],
    leaks=[],
    letterbox=[],
    song=[[M + 668, 0], [M + 737, -40]],
    subs=[], sub_style=None, capstyle="r5",
)

# V6A "It's Over" (r5): E08 park climax as complete sequential performances (room between lines), matched flashbacks.
E7 = "src/The Mentalist S06E07 The Great Red Dragon.mp4"
E8 = "src/The Mentalist S06E08 Red John.mp4"
def seq(specs, start=0):
    out, f = [], start
    for src, t0, t1, o in specs:
        n = int(round((t1 - t0) * FPS))
        out.append(C(src, f, f + n - 1, t0, **o)); f += n
    return out, f
(s1, s3, s4, s5, s6, s7), X = seq([
    (E8, 2312.7, 2321.9, dict(audio=3, T=70, name="DLG let me live")),
    (E8, 2335.3, 2340.6, dict(audio=3, T=62, name="DLG blink")),
    (E8, 2341.9, 2349.4, dict(audio=3, T=62, name="DLG are you sorry")),
    (E8, 2356.5, 2360.7, dict(audio=3, T=62, name="DLG good good")),
    (E8, 2362.3, 2364.6, dict(audio=3, T=62, name="DLG afraid to die")),
    (E8, 2367.9, 2371.0, dict(audio=3, T=62, name="DLG good"))])
M = X + 4
a6 = C(E8, X, M + 368, 2489.6, audio=3, audio_out=M + 352, T=72, name="DLG its over lisbon")
aO = C(E8, M + 668, M + 739, 2552.0, audio=0, look=dict(desat=-100, gamma=[1.0, 0.97, 0.92]), T=110,
       op=[[M + 668, 0], [M + 676, 100], [M + 726, 100], [M + 739, 0]], zoom=1.06, name="OUTRO child laughs")
def at(clip, t):
    return int(round(clip["f"][0] + (t - clip["in"]) * FPS))
fbw0, fbw1 = at(s4, 2344.5), at(s4, 2346.4)
fbd0, fbd1 = at(s4, 2347.8), s4["f"][1]
V["V6A"] = dict(
    title="It's Over", M=M, total=M + 740, drop=[0, 126, 186], shift={},
    extras=[s1, s3, s4, s5, s6, s7, a6, aO,
            C(P, fbw0, fbw1, 1872.4, look=dict(desat=-100), T=95, zoom=1.05,
              op=[[fbw0, 0], [fbw0 + 7, 88], [fbw1 - 7, 88], [fbw1, 0]], name="FB the room hallway (wife Angela)"),
            C(P, fbd0, fbd1, 1877.0, look=dict(desat=-100), T=95, zoom=1.06,
              op=[[fbd0, 0], [fbd0 + 7, 88], [fbd1 - 7, 88], [fbd1, 0]], name="FB smiley in the room (daughter Charlotte)")],
    grade_from=0,
    softgrade=dict(f=[0, M + 368], desat=-30, gamma=[0.97, 1.0, 1.06]),
    letterbox=[],
    grain=dict(f=[0, M + 739], amount=4),
    glow=[[M + 371, M + 406], [M + 463, M + 511]],
    leaks=[M + 369, M + 512, M + 567],
    flicker=[],
    vignette=[[0, M + 368]],
    song=[[M - 29, -9], [M + 335, -9], [M + 356, 0], [M + 660, 0], [M + 690, -30]],
    subs=subs_for(s1, [(2313.7, 2315.6, "Please don't k*ll me. Let me live."), (2315.9, 2318.6, "9-1-1. What's your emergency?"),
                       (2318.9, 2321.4, "Please... let me live.")])
    + subs_for(s3, [(2335.35, 2337.45, 'I want you to blink once for "no"'), (2337.5, 2340.2, 'and twice for "yes."')])
    + subs_for(s4, [(2342.0, 2346.7, "Are you sorry that you k*lled my wife, Angela"), (2347.3, 2349.4, "and my daughter, Charlotte?")])
    + subs_for(s5, [(2356.5, 2358.6, "Good."), (2359.0, 2360.6, "Good.")])
    + subs_for(s6, [(2362.4, 2364.5, "Are you afraid to die?")])
    + subs_for(s7, [(2368.2, 2370.6, "Good.")])
    + subs_for(a6, [(2489.86, 2492.99, "It's over. It's done."), (2495.12, 2497.34, "I just want you to know I'm okay."), (2499.08, 2501.87, "And I'm gonna miss you.")]),
    sub_style=dict(font="BarlowCondensed-Regular", size=52, y=950, shadow=True, tracking=40),
    capstyle="r5",
)

# V6B "Sorry" (r5): E07 press -> one continuous E02 diner confession (no jump cuts) -> E07 lines -> being sorry. Old caption style.
(b1, b2, b5, b6, b7), M = seq([
    (E7, 1796.0, 1801.15, dict(audio=2, T=70, name="DLG ten years ago")),
    (E, 1695.4, 1713.4, dict(audio=2, name="DLG diner confession")),
    (E7, 1748.8, 1751.6, dict(audio=2, T=60, name="DLG did you murder")),
    (E7, 2334.6, 2340.4, dict(audio=2, T=66, name="DLG letting go")),
    (E7, 2348.3, 2351.6, dict(audio=2, T=66, name="DLG sorry for everything"))])
eT = C(E, M + 0, M + 253, 1724.40, audio=2, zoom=1.06, name="DLG being sorry")
def fb(src, inS, t0, t1, name, **o):
    f0, f1 = at(b2, t0), at(b2, t1)
    return C(src, f0, f1, inS, op=[[f0, 0], [f0 + 6, 80], [f1 - 6, 80], [f1, 0]], **o, name=name)
V["V6B"] = dict(
    title="Sorry", M=M, total=M + 710, drop=[0, 126], shift={186: 254},
    extras=[b1, b2,
            fb(E8, 2549.0, 1696.1, 1697.5, "FB child park (daughter)", look=dict(desat=-100, gamma=[1.0, 0.97, 0.92]), T=120, zoom=1.06),
            fb(P, 1872.3, 1701.5, 1702.7, "FB doorway (her mother)", look=dict(desat=-100, contrast=20, gamma=[0.85, 0.85, 0.85]), zoom=1.06),
            fb(P, 1878.0, 1711.2, 1712.5, "FB smiley (killed them)", look=dict(desat=-100, contrast=20, gamma=[0.85, 0.85, 0.85]), zoom=1.08),
            b5, b6, b7, eT],
    grade_from=0,
    tealgrade=dict(f=[0, M + 253], desat=-35, gamma=[0.9, 1.0, 1.15]),
    vignette=[[0, M + 253]],
    grain=dict(f=[0, M + 709], amount=3),
    glow=[[M + 371, M + 406], [M + 463, M + 511]],
    flicker=[],
    leaks=[M + 369, M + 407, M + 512],
    letterbox=[],
    song=[[M - 29, -10], [M + 254, -10], [M + 272, 0], [M + 668, 0], [M + 709, -40]],
    subs=subs_for(b1, [(1796.8, 1797.85, "Ten years ago,"), (1797.9, 1799.6, "the s*rial k*ller known as Red John"), (1799.65, 1801.1, "k*lled my wife and daughter.")])
    + subs_for(b2, [(1695.66, 1698.10, "I'd have a daughter... about your age,"), (1698.16, 1699.9, "if I hadn't caused her death."),
                    (1701.62, 1703.2, "Her and her mother."), (1704.9, 1706.1, "Out of arrogance..."), (1706.2, 1708.4, "stupidity."),
                    (1709.6, 1711.32, "I made an evil man very angry"), (1711.36, 1713.3, "and he k*lled them to teach me a lesson.")])
    + subs_for(b5, [(1749.03, 1751.0, "Did you m*rder my wife and daughter?")])
    + subs_for(b6, [(2334.66, 2336.66, "No, I'm not quitting."), (2338.66, 2340.3, "I'm letting go.")])
    + subs_for(b7, [(2348.9, 2351.5, "I'm sorry. For everything.")])
    + subs_for(eT, [(1724.40, 1727.20, "Being sorry is far worse punishment than being dead."), (1727.3, 1728.14, "Everybody dies."),
                    (1728.78, 1732.34, "Very few people ever feel truly sorry...")]),
    sub_style=dict(font="Arial-BoldMT", size=46, y=930, shadow=True),
)

# ---------------------------------------------------------------- r3: distinct main edit + spin-blur bg stacks per variant
S1 = "src/The Mentalist S06E01 The Desert Rose.mp4"
S2 = "src/The Mentalist S06E02 Black-Winged Redbird.mp4"
S3 = "src/The Mentalist S06E03 Wedding in Red.mp4"
S4 = "src/The Mentalist S06E04 Red Listed.mp4"
S5 = "src/The Mentalist S06E05 The Red Tattoo.mp4"


def Mn(src, inS, name, **o):
    d = dict(src=src, name=name)
    d["in"] = inS
    d.update(o)
    return d


def Bg(src, inS, name, **o):
    d = dict(src=src, name=name)
    d["in"] = inS
    d.update(o)
    return d


# V5A Flashback: memory / love lost - wedding watched from a doorway, Jane alone at windows.
V["V5A"]["main"] = {
    126: Mn(S3, 2386.9, "wedding doorway sad smile"),
    186: Mn(S1, 43.75, "jane at window long", speed=0.75),
    409: Mn(S3, 2356.2, "ring hands"),
    433: Mn(S3, 2400.5, "jane sad smile"),
    453: Mn(S3, 2403.4, "kiss"),
    514: Mn(S2, 2439.8, "jane window close sad"),
    530: Mn(S3, 2373.2, "ring"),
    533: Mn(S1, 5.2, "window"),
    535: Mn(S3, 2395.0, "jane watching"),
    538: Mn(S2, 2415.8, "jane window dark"),
    551: Mn(S1, 30.0, "window 2"),
    568: Mn(S3, 2405.6, "jane doorway"),
    587: Mn(S1, 37.0, "window 3"),
    605: Mn(S2, 2443.5, "lisbon window"),
    624: Mn(S1, 8.3, "window 4"),
    631: Mn(S2, 2460.1, "jane"),
    650: Mn(S2, 2369.7, "jane recorder"),
}
V["V5A"]["bg"] = {
    1: [Bg(S3, 2356.3, "ring"), Bg(P, 1754.7, "jane laugh"), Bg(S3, 2387.5, "doorway"), Bg(S1, 44.5, "window"),
        Bg(S3, 2403.5, "kiss"), Bg(P, 1823.1, "house night"), Bg(S2, 2440.5, "jane"), Bg(S3, 2373.5, "ring 2"),
        Bg(S1, 31.0, "window 2"), Bg(P, 1812.1, "tv"), Bg(S3, 2418.4, "kiss 2"), Bg(S2, 2391.5, "window dark"),
        Bg(S3, 2396.0, "watching"), Bg(P, 1818.1, "car night"), Bg(S1, 38.0, "window 3"), Bg(S3, 2407.0, "doorway 2")],
    2: [Bg(S3, 2401.5, "sad smile"), Bg(S1, 46.5, "window"), Bg(P, 1755.5, "jane laugh 2"), Bg(S3, 2357.5, "hands"),
        Bg(S2, 2416.8, "window dark"), Bg(S3, 2388.8, "doorway"), Bg(P, 1824.0, "house"), Bg(S1, 6.2, "window 4"),
        Bg(S3, 2374.5, "ring 3"), Bg(S2, 2442.0, "jane close"), Bg(S3, 2408.2, "doorway 3"), Bg(P, 1813.0, "tv 2"),
        Bg(S1, 9.0, "window 5"), Bg(S3, 2419.0, "kiss 3"), Bg(S2, 2461.5, "jane 2"), Bg(S1, 32.5, "window 6")],
}

# V5B Red John: menace / violence - bloody smile victim, explosions, bodies, darkness, police lights.
V["V5B"]["main"] = {
    126: Mn(S1, 2465.4, "bloody painted smile"),
    186: Mn(S4, 1567.0, "jane dark garage long", speed=0.9),
    409: Mn(S5, 2020.0, "dark hallway figure"),
    433: Mn(S1, 2332.3, "flashlight dark"),
    453: Mn(S2, 2092.4, "car explosion"),
    514: Mn(S5, 2139.9, "body on floor"),
    530: Mn(S5, 2313.5, "police lights"),
    533: Mn(S2, 2093.6, "explosion 2"),
    535: Mn(S1, 2470.0, "bloody face 2"),
    538: Mn(S5, 2289.4, "jane car police lights"),
    551: Mn(S2, 2455.4, "dying man"),
    568: Mn(S5, 2145.4, "jane over body"),
    587: Mn(S1, 2460.1, "jane phone close"),
    605: Mn(S5, 1982.4, "jane dark room"),
    624: Mn(S5, 260.2, "body carpet"),
    631: Mn(S5, 2011.0, "jane dark room 2"),
    650: Mn(S1, 2477.3, "jane close"),
}
V["V5B"]["bgT"] = 58
V["V5B"]["bg"] = {
    1: [Bg(P, 1877.1, "smiley"), Bg(S1, 2466.0, "bloody face"), Bg(S2, 2092.6, "explosion"), Bg(S5, 2140.5, "body"),
        Bg(S5, 2048.2, "headlights"), Bg(S1, 2333.0, "flashlight"), Bg(S2, 2424.4, "bars"), Bg(S5, 2020.8, "hallway"),
        Bg(S5, 260.4, "body carpet"), Bg(S1, 51.0, "suspect grid"), Bg(S5, 114.5, "prisoner night"), Bg(S2, 2456.0, "dying man"),
        Bg(S4, 2447.0, "prison van"), Bg(S1, 93.4, "jane dark"), Bg(S5, 2313.55, "police lights"), Bg(P, 1878.5, "smiley 2")],
    2: [Bg(S1, 2472.0, "bloody face 2"), Bg(S5, 1966.0, "dark room"), Bg(S2, 2093.8, "explosion 2"), Bg(P, 1877.6, "smiley 3"),
        Bg(S5, 2142.5, "body 2"), Bg(S1, 2335.0, "flashlight 2"), Bg(S4, 1580.0, "garage"), Bg(S5, 27.0, "lisbon flashlight"),
        Bg(S2, 2457.5, "dying man 2"), Bg(S1, 52.5, "suspect grid 2"), Bg(S5, 2049.0, "headlights 2"), Bg(S5, 116.0, "prisoner 2"),
        Bg(S4, 2470.0, "prison van 2"), Bg(S1, 2474.5, "bloody face 3"), Bg(S5, 2021.8, "hallway 2"), Bg(S2, 2094.4, "fire")],
}

# V6A It's Over: the park - the kill, the body, Lisbon, running, the phone.
V["V6A"]["main"] = {
    409: Mn(E8, 2330.0, "jane trees close"),
    433: Mn(E8, 2305.0, "jane approaching"),
    453: Mn(E8, 2408.2, "hand on throat"),
    514: Mn(E8, 2444.6, "jane over body wide"),
    530: Mn(E8, 2320.2, "rj lying"),
    533: Mn(E8, 2410.0, "throat 2"),
    535: Mn(E8, 2380.0, "jane trees 2"),
    538: Mn(E8, 2460.6, "lisbon fbi"),
    551: Mn(E8, 2470.0, "lisbon fbi 2"),
    568: Mn(E8, 2504.6, "running"),
    587: Mn(E8, 2390.0, "jane trees 3"),
    605: Mn(E8, 2420.0, "jane trees 4"),
    624: Mn(E8, 2510.0, "running 2"),
    631: Mn(E8, 2430.0, "jane trees 5"),
    650: Mn(E8, 2450.0, "over body 2"),
}
V["V6A"]["bg"] = {
    1: [Bg(E8, 2306.5, "approach"), Bg(E8, 2320.5, "rj lying"), Bg(E8, 2335.0, "jane"), Bg(E8, 2408.5, "throat"),
        Bg(E8, 2445.5, "over body"), Bg(E8, 2462.0, "lisbon"), Bg(E8, 2506.0, "running"), Bg(E8, 2345.0, "jane 2"),
        Bg(E8, 2411.0, "throat 2"), Bg(E8, 2452.0, "body 2"), Bg(E8, 2515.0, "running 2"), Bg(E8, 2355.0, "jane 3"),
        Bg(E8, 2475.0, "fbi"), Bg(E8, 2312.0, "approach 2"), Bg(E8, 2400.0, "jane 4"), Bg(E8, 2530.0, "running 3")],
    2: [Bg(E8, 2365.0, "jane 5"), Bg(E8, 2321.0, "rj 2"), Bg(E8, 2448.0, "body 3"), Bg(E8, 2520.0, "running 4"),
        Bg(E8, 2409.5, "throat 3"), Bg(E8, 2480.0, "fbi 2"), Bg(E8, 2340.0, "jane 6"), Bg(E8, 2308.5, "approach 3"),
        Bg(E8, 2425.0, "jane 7"), Bg(E8, 2540.0, "running 5"), Bg(E8, 2455.0, "body 4"), Bg(E8, 2370.0, "jane 8"),
        Bg(E8, 2466.0, "lisbon 2"), Bg(E8, 2415.0, "jane 9"), Bg(E8, 2525.0, "running 6"), Bg(E8, 2435.0, "jane 10")],
}

# V6B Sorry: guilt - the suicide note, deleted files, interrogation, phones in the dark, the press.
V["V6B"]["main"] = {
    254: Mn(S2, 2026.4, "jane in the dark long"),
    409: Mn(S2, 2213.3, "suicide note"),
    433: Mn(S2, 2100.2, "jane"),
    453: Mn(S2, 2219.2, "deleting files"),
    514: Mn(S2, 2346.3, "jane leaning"),
    530: Mn(S2, 2424.4, "man behind bars"),
    533: Mn(S2, 2117.0, "jane 2"),
    535: Mn(S4, 1736.0, "lisbon phone"),
    538: Mn(S1, 2229.0, "lisbon dark office"),
    551: Mn(S1, 2323.0, "jane car phone"),
    568: Mn(S2, 2110.0, "jane 3"),
    587: Mn(S1, 360.0, "interrogation jane"),
    605: Mn(S1, 2170.2, "jane car night"),
    624: Mn(S4, 1745.0, "lisbon phone 2"),
    631: Mn(S1, 380.0, "interrogation 2"),
    650: Mn(S1, 2240.0, "lisbon office 2"),
}
V["V6B"]["bg"] = {
    1: [Bg(S2, 2213.5, "note"), Bg(E7, 1795.5, "press"), Bg(S2, 2219.2, "deleting"), Bg(S1, 2230.0, "lisbon office"),
        Bg(E7, 1749.2, "did you murder"), Bg(S2, 2028.0, "jane dark"), Bg(S1, 2325.0, "car phone"), Bg(E7, 2335.0, "letting go"),
        Bg(S2, 2120.0, "jane"), Bg(S1, 395.0, "interrogation"), Bg(E7, 2348.5, "sorry"), Bg(S4, 1740.0, "lisbon phone"),
        Bg(S2, 2347.0, "leaning"), Bg(E7, 1798.0, "press 2"), Bg(S2, 2214.3, "note 2"), Bg(S1, 2172.0, "car night")],
    2: [Bg(E7, 1750.2, "murder 2"), Bg(S2, 2031.0, "dark 2"), Bg(S1, 2235.0, "office 2"), Bg(S2, 2213.9, "note 3"),
        Bg(E7, 2337.0, "letting go 2"), Bg(S1, 2328.0, "car phone 2"), Bg(S2, 2105.0, "jane 4"), Bg(E7, 1800.0, "press 3"),
        Bg(S4, 1747.0, "phone 3"), Bg(S2, 2219.6, "deleting 2"), Bg(S1, 405.0, "interrogation 3"), Bg(E7, 2350.0, "sorry 2"),
        Bg(S2, 2370.5, "recorder"), Bg(S1, 2175.0, "car night 2"), Bg(S2, 2035.0, "dark 3"), Bg(E7, 1752.0, "murder 3")],
}


import os
_CS = S / "plan/r5/cutspec.json"
CUTSPEC = {V_: {int(k): v for k, v in d.items()} for V_, d in json.load(open(_CS)).items()} if _CS.exists() else {}
# ---------------------------------------------------------------- JSX generation
def absp(p):
    p = Path(p)
    return (p if p.is_absolute() else S / p).as_posix()


def js_str(t):
    return "String.fromCharCode(" + ",".join(str(ord(c)) for c in t) + ")"


def build(var):
    cfg = V[var]
    M, total = cfg["M"], cfg["total"]
    JSXN = f"{var}_build"
    shots = [s for s in plan["shots"] if s["f"][0] not in cfg["drop"]]
    srcs = []
    MAIN = cfg.get("main", {})
    BG = cfg.get("bg", {})
    CUTS = CUTSPEC.get(var, {})  # per-version cutout source overrides {n: {src,in,nf}}
    allc = shots + cfg["extras"] + list(MAIN.values()) + [c for v in BG.values() for c in v] + list(CUTS.values())
    for s in allc:
        if "src" in s and absp(s["src"]) not in srcs:
            srcs.append(absp(s["src"]))
    widths = {a: int(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width", "-of", "csv=p=0", a],
                                    capture_output=True, text=True).stdout.strip()) for a in srcs}
    idx = {a: i for i, a in enumerate(srcs)}
    L = []
    add = L.append
    add("#target aftereffects")
    add("(function(){")
    add("var R={ok:false,steps:[],warn:[],fxnames:{}};")
    add("function enc(v){if(v===null||v===undefined)return 'null';if(typeof v==='number'||typeof v==='boolean')return String(v);"
        "if(v instanceof Array){var a=[];for(var i=0;i<v.length;i++)a.push(enc(v[i]));return '['+a.join(',')+']';}"
        "if(typeof v==='object'){var b=[];for(var k in v)b.push(enc(String(k))+':'+enc(v[k]));return '{'+b.join(',')+'}';}"
        "var s=String(v),o='';for(var j=0;j<s.length;j++){var c=s.charCodeAt(j);o+=(c<32||c==34||c==92||c>126)?'?':s.charAt(j);}return String.fromCharCode(34)+o+String.fromCharCode(34);}")
    add(f"function out(){{var f=new File('{SP}/jsx/{JSXN}_report.json');f.encoding='UTF-8';f.open('w');f.write(enc(R));f.close();}}")
    add("var p=app.project;")
    add("if(!(p && p.file===null && p.numItems===0 && !p.dirty && !p.renderQueue.rendering)){R.err='GUARD: project not empty/untitled/clean or rendering';"
        "R.state={file:(p&&p.file)?decodeURI(p.file.absoluteURI):null,n:p?p.numItems:-1,dirty:p?p.dirty:null};out();return;}")
    add(f"app.beginUndoGroup('JANE {var} build');")
    add("try{")
    add("function imp(path,seq){var f=new File(path);if(!f.exists)throw new Error('missing '+path);var io=new ImportOptions(f);if(seq){io.sequence=true;io.forceAlphabetical=true;}return p.importFile(io);}")
    add(f"var fold=p.items.addFolder('JANE_{var}_SOURCES');")
    add(f"var comp=p.items.addComp('JANE_{var}',1920,1080,1,{total}/{FPS},{FPS});comp.bgColor=[0,0,0];")
    add("var IT={};")
    for a, i in idx.items():
        add(f"IT[{i}]=imp('{a}',false);IT[{i}].parentFolder=fold;")
    add(f"var song=imp('{plan['audio']['song']}',false);song.parentFolder=fold;")
    for n in (1, 2):
        cdn = f"{var}_cut{n}" if n in CUTS else f"cut{n}"
        add(f"var cut{n}=imp('{SP}/cutouts/{cdn}/{cdn}_0000.png',true);cut{n}.mainSource.conformFrameRate={FPS};cut{n}.mainSource.alphaMode=AlphaMode.STRAIGHT;cut{n}.parentFolder=fold;")
        add(f"var str{n}=imp('{SP}/cutouts/strobe{n}/strobe{n}_0000.png',true);str{n}.mainSource.conformFrameRate={FPS};str{n}.parentFolder=fold;")
    add("comp.motionBlur=true;comp.shutterAngle=360;comp.shutterPhase=-180;")
    add("R.steps.push('imported');")
    add(f"function sec(fr){{return fr/{FPS};}}")
    add("function TG(l){return l.property('ADBE Transform Group');}")
    add("function foot(item,f0,f1,inS,speed,scale,name,px,py){var l=comp.layers.add(item);l.audioEnabled=false;var st=100/(speed||1);l.stretch=st;"
        "l.startTime=sec(f0)-inS*st/100;l.inPoint=sec(f0);l.outPoint=sec(f1+1);TG(l).property('ADBE Scale').setValue([scale,scale]);"
        "TG(l).property('ADBE Position').setValue([px||960,py||540]);l.name=name;return l;}")
    add("function seqL(item,f0,fin,f1,name){var l=comp.layers.add(item);l.startTime=sec(f0);l.inPoint=sec(fin);l.outPoint=sec(f1+1);l.name=name;return l;}")
    add("function solid(col,f0,f1,name,w,h){var l=comp.layers.addSolid(col,name,w||1920,h||1080,1,sec(f1+1)-sec(f0));l.startTime=sec(f0);l.inPoint=sec(f0);l.outPoint=sec(f1+1);return l;}")
    add("function adj(f0,f1,name){var l=solid([1,1,1],f0,f1,name);l.adjustmentLayer=true;return l;}")
    add("function fxp(fx,nm,mn){for(var i=1;i<=fx.numProperties;i++){var q=fx.property(i);if(q.name===nm&&q.propertyValueType!==PropertyValueType.NO_VALUE)return q;}"
        "if(mn){try{var z=fx.property(mn);if(z)return z;}catch(e){}}R.warn.push('fx param '+nm+' in '+fx.matchName);return null;}")
    add("function setFx(fx,nm,v,mn){var q=fxp(fx,nm,mn);if(q){try{q.setValue(v);return true;}catch(e){R.warn.push('set '+nm+' '+e);}}return false;}")
    add("function keyFx(fx,nm,ks,mn){var q=fxp(fx,nm,mn);if(!q)return;for(var i=0;i<ks.length;i++){q.setValueAtTime(sec(ks[i][0]),ks[i][1]);}}")
    add("function names(fx){var a=[];for(var i=1;i<=fx.numProperties;i++){a.push(fx.property(i).name+'|'+fx.property(i).matchName);}R.fxnames[fx.matchName]=a.join(' ; ');}")
    add("function ell(l,cx,cy,rx,ry,feather,inv){var m=l.property('ADBE Mask Parade').addProperty('ADBE Mask Atom');var sh=new Shape();var k=0.5523;"
        "sh.vertices=[[cx,cy-ry],[cx+rx,cy],[cx,cy+ry],[cx-rx,cy]];sh.inTangents=[[-rx*k,0],[0,-ry*k],[rx*k,0],[0,ry*k]];sh.outTangents=[[rx*k,0],[0,ry*k],[-rx*k,0],[0,-ry*k]];sh.closed=true;"
        "m.property('ADBE Mask Shape').setValue(sh);m.inverted=!!inv;m.property('ADBE Mask Feather').setValue([feather,feather]);return m;}")
    add("function vign(f0,f1,op){var vg=solid([0,0,0],f0,f1,'VIGNETTE '+f0);ell(vg,960,540,1050,640,420,true);TG(vg).property('ADBE Opacity').setValue(op);return vg;}")
    add("function look(l,o){var E=l.property('ADBE Effect Parade');if(o.desat){var hs=E.addProperty('ADBE HUE SATURATION');setFx(hs,'Master Saturation',o.desat);}"
        "if(o.gamma){var lv=E.addProperty('ADBE Pro Levels2');setFx(lv,'Red Gamma',o.gamma[0]);setFx(lv,'Green Gamma',o.gamma[1]);setFx(lv,'Blue Gamma',o.gamma[2]);}"
        "if(o.exposure){var ex=E.addProperty('ADBE Exposure2');setFx(ex,'Exposure',o.exposure);}"
        "if(o.contrast){var bc=E.addProperty('ADBE Brightness & Contrast 2');setFx(bc,'Contrast',o.contrast);}}")
    add("function glow(l,th,r,i){var g=l.property('ADBE Effect Parade').addProperty('ADBE Glo2');names(g);setFx(g,'Glow Threshold',th);setFx(g,'Glow Radius',r);setFx(g,'Glow Intensity',i);return g;}")
    add("function bgL(item,f0,f1,inS,sc,r0,r1,name,zf){zf=zf||1.06;var l=foot(item,f0,f1,inS,1,sc,name);l.motionBlur=true;var r=TG(l).property('ADBE Rotate Z');"
        "r.setValueAtTime(sec(f0),r0);r.setValueAtTime(sec(f1+1),r1);var s=TG(l).property('ADBE Scale');s.setValueAtTime(sec(f0),[sc*zf,sc*zf]);s.setValueAtTime(sec(f1+1),[sc,sc]);return l;}")
    add("function ez(q){for(var i=1;i<=q.numKeys;i++){for(var n=1;n<=3;n++){try{var a=[];for(var j=0;j<n;j++)a.push(new KeyframeEase(0,70));q.setTemporalEaseAtKey(i,a,a);break;}catch(e){}}}}")
    add("function tanim(t,g0,g1,ein,eout,bin,bout,dy,s0,s1,cx,cy){var tg=TG(t);var op=tg.property('ADBE Opacity');var ps=tg.property('ADBE Position');var sc=tg.property('ADBE Scale');"
        "var bl=t.property('ADBE Effect Parade').addProperty('ADBE Gaussian Blur 2');var bq=fxp(bl,'Blurriness');try{var re=fxp(bl,'Repeat Edge Pixels');if(re)re.setValue(1);}catch(e){}"
        "op.setValueAtTime(sec(g0),0);op.setValueAtTime(sec(g0+ein),100);op.setValueAtTime(sec(g1+1-eout),100);op.setValueAtTime(sec(g1+1),0);"
        "ps.setValueAtTime(sec(g0),[cx,cy+dy]);ps.setValueAtTime(sec(g0+ein),[cx,cy]);ps.setValueAtTime(sec(g1+1-eout),[cx,cy]);ps.setValueAtTime(sec(g1+1),[cx,cy-dy*0.8]);"
        "sc.setValueAtTime(sec(g0),[s0,s0]);sc.setValueAtTime(sec(g0+ein),[100,100]);sc.setValueAtTime(sec(g1+1-eout),[s1,s1]);"
        "if(bq){bq.setValueAtTime(sec(g0),bin);bq.setValueAtTime(sec(g0+ein),0);bq.setValueAtTime(sec(g1+1-eout),0);bq.setValueAtTime(sec(g1+1),bout);ez(bq);}"
        "ez(op);ez(ps);ez(sc);}")
    add("function vol(l,ks){var a=l.property('ADBE Audio Group').property('ADBE Audio Levels');for(var i=0;i<ks.length;i++)a.setValueAtTime(sec(ks[i][0]),[ks[i][1],ks[i][1]]);}")

    # song
    add(f"var sl=comp.layers.add(song);sl.startTime=sec({M})-{SONG_T0};sl.name='SONG';")
    if cfg["song"]:
        add(f"vol(sl,{json.dumps(cfg['song'])});")
    sl_end = M + 709 if total <= M + 710 else total - 1
    add(f"sl.outPoint=sec({total});")

    # main edit
    cn = 0
    for sh in plan["shots"]:
        f0, f1 = sh["f"]
        if sh.get("cutout"):
            cn += 1
        if f0 in cfg["drop"] or "src" not in sh:
            continue
        a = absp(sh["src"])
        sc = round(1920 / widths[a] * 100, 4)
        tag = sh.get("tag", "")[:40]
        inS = sh["in"]
        if f0 in cfg["shift"]:
            nf = cfg["shift"][f0]
            inS = round(inS + (nf - f0) / FPS * sh.get("speed", 1), 4)
            f0 = nf
        A0, A1 = f0 + M, f1 + M
        if sh.get("cutout"):
            pu = sh.get("plain_until")
            if cn in CUTS:
                a = absp(CUTS[cn]["src"]); inS = CUTS[cn]["in"]; sc = round(1920 / widths[a] * 100, 4)
                tag = CUTS[cn].get("name", tag)
            if pu:
                add(f"foot(IT[{idx[a]}],{A0},{pu + M},{inS},{sh.get('speed', 1)},{sc},{js_str('F' + str(f0) + ' plain ' + tag)});")
            fs = (pu + 1 + M) if pu else A0
            if cn in BG:
                bl = BG[cn]
                fr, k, starts = fs, 0, []
                while fr <= A1:
                    c = bl[k % len(bl)]
                    steady = cfg.get("bgstyle") == "steady"
                    ln = c.get("len", (4 + (k % 2)) if steady else (2 + (k % 2)))
                    e = min(A1, fr + ln - 1)
                    b_ = absp(c["src"])
                    bsc = round(1920 / widths[b_] * 100 * c.get("zoom", 1.3), 4)
                    sgn = 1 if k % 2 == 0 else -1
                    r0 = sgn * c.get("rot", 7)
                    vn = f"B{cn}_{k}"
                    if steady:
                        span = max(1, A1 + 1 - fs)
                        ra, rb = round(-3 + 6 * (fr - fs) / span, 3), round(-3 + 6 * (e + 1 - fs) / span, 3)
                        add(f"var {vn}=bgL(IT[{idx[b_]}],{fr},{e},{c['in']},{bsc},{ra},{rb},{js_str('BG' + str(cn) + ' ' + c.get('name', ''))},1.02);")
                    else:
                        add(f"var {vn}=bgL(IT[{idx[b_]}],{fr},{e},{c['in']},{bsc},{r0},{-r0 * 0.4},{js_str('BG' + str(cn) + ' ' + c.get('name', ''))});")
                    gm = auto_gamma(c["src"], c["in"], 0.15, c.get("T", cfg.get("bgT", 78)))
                    lk = dict(desat=c.get("desat", -35), gamma=[gm, gm, gm])
                    if c.get("contrast"):
                        lk["contrast"] = c["contrast"]
                    add(f"look({vn},{json.dumps(lk)});")
                    starts.append(fr)
                    fr, k = e + 1, k + 1
                ks = []
                for st_ in starts:
                    ks += [[st_, 12], [st_ + 1, 5]]
                amt = "setFx(rb,'Amount',3);" if cfg.get("bgstyle") == "steady" else f"keyFx(rb,'Amount',{json.dumps(ks)});"
                add(f"(function(){{var v=adj({fs},{A1},'SPIN BLUR {cn}');var rb=v.property('ADBE Effect Parade').addProperty('ADBE Radial Blur');names(rb);"
                    f"setFx(rb,'Type',1);setFx(rb,'Center',[960,540]);{amt}}})();")
            else:
                add(f"seqL(str{cn},{fs},{fs},{A1},'STROBE{cn}');")
            add(f"seqL(cut{cn},{A0},{fs},{A1},'CUT{cn}');")
        elif f0 in MAIN:
            mo = MAIN[f0]
            b_ = absp(mo["src"])
            sc = round(1920 / widths[b_] * 100 * mo.get("scale", 100) / 100, 4)
            px, py = mo.get("pos", [960, 540])
            spd = mo.get("speed", 1)
            add(f"var L{f0}=foot(IT[{idx[b_]}],{A0},{A1},{mo['in']},{spd},{sc},{js_str('F' + str(f0) + ' ' + mo.get('name', ''))},{px},{py});")
            z = mo.get("zoom", 1.05)
            if z:
                zz = round(sc * z, 4)
                add(f"var zs=TG(L{f0}).property('ADBE Scale');zs.setValueAtTime(sec({A0}),[{sc},{sc}]);zs.setValueAtTime(sec({A1}+1),[{zz},{zz}]);")
            T = mo.get("T", grade.get(str(sh["f"][0]), {}).get("ref_L", 70))
            gm = auto_gamma(mo["src"], mo["in"], (A1 - A0 + 1) / FPS * spd, T)
            lk = dict(gamma=[gm, gm, gm])
            if mo.get("desat"):
                lk["desat"] = mo["desat"]
            if mo.get("contrast"):
                lk["contrast"] = mo["contrast"]
            add(f"look(L{f0},{json.dumps(lk)});")
        else:
            if sh.get("scale"):
                sc = round(sc * sh["scale"] / 100, 4)
            px, py = sh.get("pos", [960, 540])
            add(f"var L{f0}=foot(IT[{idx[a]}],{A0},{A1},{inS},{sh.get('speed', 1)},{sc},{js_str('F' + str(f0) + ' ' + tag)},{px},{py});")
            if sh.get("zoom"):
                z = round(sc * sh["zoom"], 4)
                add(f"var zs=TG(L{f0}).property('ADBE Scale');zs.setValueAtTime(sec({A0}),[{sc},{sc}]);zs.setValueAtTime(sec({A1}+1),[{z},{z}]);")
            g = sh.get("grade")
            if g:
                add(f"look(L{f0},{{exposure:{g['exposure']}}});")
                if g.get("vignette"):
                    add(f"vign({A0},{A1},85);")
    add("R.steps.push('main');")

    # extra clips
    for k, c in enumerate(cfg["extras"]):
        a = absp(c["src"])
        sc = round(1920 / widths[a] * 100, 4)
        f0, f1 = c["f"]
        xf, xo = c.get("xf", 0), c.get("xo", 0)
        inS = round(c["in"] - xf / FPS * c.get("speed", 1), 4)
        f0, f1 = f0 - xf, f1 + xo
        vn = f"X{k}"
        add(f"var {vn}=foot(IT[{idx[a]}],{f0},{f1},{inS},{c.get('speed', 1)},{sc},{js_str('X ' + c.get('name', ''))});")
        if c.get("blend"):
            add(f"{vn}.blendingMode=BlendingMode.{c['blend']};")
        if (xf or xo) and not c.get("op"):
            ok_ = [[f0, 0], [f0 + xf, 100]] if xf else [[f0, 100]]
            ok_ += [[f1 + 1 - xo, 100], [f1 + 1, 0]] if xo else []
            add(f"var xop=TG({vn}).property('ADBE Opacity');" + "".join(f"xop.setValueAtTime(sec({fr}),{v});" for fr, v in ok_) + "ez(xop);")
        if c.get("video") is False:
            add(f"{vn}.enabled=false;")
        if "audio" in c:
            ao = c.get("audio_out", f1)
            g = c["audio"]
            add(f"{vn}.audioEnabled=true;vol({vn},[[{f0},-50],[{f0 + 2},{g}],[{ao - 2},{g}],[{ao},-50]]);")
        if c.get("zoom"):
            z = round(sc * c["zoom"], 4)
            add(f"var zs=TG({vn}).property('ADBE Scale');zs.setValueAtTime(sec({f0}),[{sc},{sc}]);zs.setValueAtTime(sec({f1}+1),[{z},{z}]);")
        lk = dict(c.get("look") or {})
        if c.get("T") and c.get("video") is not False:
            gm = auto_gamma(c["src"], c["in"], (f1 - f0 + 1) / FPS * c.get("speed", 1), c["T"])
            tint = lk.get("gamma", [1, 1, 1])
            lk["gamma"] = [round(gm * t, 3) for t in tint]
        if lk:
            add(f"look({vn},{json.dumps(lk)});")
        if c.get("glow"):
            gl = c["glow"]
            add(f"glow({vn},{gl['th']},{gl['r']},{gl['i']});")
        if c.get("op"):
            add(f"var op=TG({vn}).property('ADBE Opacity');" + "".join(f"op.setValueAtTime(sec({fr}),{v});" for fr, v in c["op"]))
    add("R.steps.push('extras');")

    # per-slot looks from v4
    for key, g in sorted(grade.items(), key=lambda kv: int(kv[0])):
        a0, b0 = g["f"]
        if a0 in cfg["drop"] or a0 in MAIN:
            continue
        if a0 in cfg["shift"]:
            a0 = cfg["shift"][a0]
        add(f"(function(){{var v=adj({a0 + M},{b0 + M},'LV {key}');var E=v.property('ADBE Effect Parade');")
        if g.get("desat"):
            add(f"var hs=E.addProperty('ADBE HUE SATURATION');setFx(hs,'Master Saturation',{g['desat']});")
        r_, g_, b_ = g["gamma"]
        add(f"var lv=E.addProperty('ADBE Pro Levels2');setFx(lv,'Red Gamma',{r_});setFx(lv,'Green Gamma',{g_});setFx(lv,'Blue Gamma',{b_});}})();")
    # variant global grades (under GRADE adj)
    for gk in ("redgrade", "tealgrade", "softgrade"):
        if cfg.get(gk):
            gg = cfg[gk]
            add(f"(function(){{var v=adj({gg['f'][0]},{gg['f'][1]},'{gk.upper()}');look(v,{json.dumps({'desat': gg['desat'], 'gamma': gg['gamma']})});}})();")
    for va, vb in cfg.get("vignette", []):
        add(f"vign({va},{vb},80);")
    add(f"var ga=adj({cfg['grade_from']},{M + 667},'GRADE adj');var shp=ga.property('ADBE Effect Parade').addProperty('ADBE Sharpen');setFx(shp,'Sharpen Amount',18);"
        "var bc=ga.property('ADBE Effect Parade').addProperty('ADBE Brightness & Contrast 2');setFx(bc,'Contrast',20);")
    add("R.steps.push('looks');")

    # v4 captions (offset)
    cst = plan["caption_style"]
    r5 = cfg.get("capstyle") == "r5"
    caps = plan["captions"]
    grp, gidx, prev = [], [], None
    for txt, a0, a1 in caps:
        if prev and txt.startswith(prev[0]) and a0 == prev[2] + 1:
            grp[-1][1] = a1
        else:
            grp.append([a0, a1])
        gidx.append(len(grp) - 1)
        prev = (txt, a0, a1)
    for ci, (txt, a0, a1) in enumerate(caps):
        ov = plan.get("caption_overrides", {}).get(txt, {})
        if r5:
            g0, g1 = grp[gidx[ci]][0] + M, grp[gidx[ci]][1] + M
            gd = g1 - g0 + 1
            ein, eout = max(3, min(8, gd // 3)), max(3, min(6, gd // 4))
            add(f"(function(){{var t=comp.layers.addText({js_str(txt)});var sp=t.property('ADBE Text Properties').property('ADBE Text Document');var d=sp.value;"
                "d.resetCharStyle();d.fontSize=80;try{d.font='BarlowCondensed-Medium';}catch(e){R.warn.push('font');}d.tracking=120;d.applyFill=true;d.fillColor=[1,1,1];d.applyStroke=false;"
                "d.justification=ParagraphJustification.CENTER_JUSTIFY;sp.setValue(d);"
                f"t.startTime=0;t.inPoint=sec({a0 + M});t.outPoint=sec({a1 + M}+1);var r=t.sourceRectAtTime(sec({a0 + M}),false);"
                "TG(t).property('ADBE Anchor Point').setValue([r.left+r.width/2,r.top+r.height/2]);"
                f"tanim(t,{g0},{g1},{ein},{eout},12,10,12,94,102,960,{cst['center_y']});t.name='CAP '+{js_str(txt)};"
                + ("var ds=t.property('ADBE Effect Parade').addProperty('ADBE Drop Shadow');setFx(ds,'Opacity',204);setFx(ds,'Distance',4);setFx(ds,'Softness',12);" if ov.get("shadow") else "")
                + ("" if ov.get("blend") == "normal" else "t.blendingMode=BlendingMode.DIFFERENCE;"
                   "var u=t.duplicate();u.moveAfter(t);u.blendingMode=BlendingMode.NORMAL;u.name='CAPSH '+t.name.substr(4);"
                   "var uf=u.property('ADBE Effect Parade').addProperty('ADBE Fill');setFx(uf,'Color',[0,0,0,1]);"
                   "var ub=u.property('ADBE Effect Parade').addProperty('ADBE Box Blur2');setFx(ub,'Blur Radius',9);"
                   "TG(u).property('ADBE Opacity').expression='value*0.42';")
                + "})();")
            continue
        add(f"(function(){{var t=comp.layers.addText({js_str(txt)});var sp=t.property('ADBE Text Properties').property('ADBE Text Document');var d=sp.value;"
            f"d.resetCharStyle();d.fontSize={cst['font_size']};try{{d.font='{cst['font']}';}}catch(e){{R.warn.push('font');}}d.applyFill=true;d.fillColor=[1,1,1];d.applyStroke=false;"
            "d.justification=ParagraphJustification.CENTER_JUSTIFY;sp.setValue(d);"
            f"t.startTime=0;t.inPoint=sec({a0 + M});t.outPoint=sec({a1 + M}+1);var r=t.sourceRectAtTime(sec({a0 + M}),false);"
            f"TG(t).property('ADBE Position').setValue([960,{cst['center_y']}-(r.top+r.height/2)]);t.name='CAP '+{js_str(txt)};"
            + ("var ds=t.property('ADBE Effect Parade').addProperty('ADBE Drop Shadow');setFx(ds,'Opacity',204);setFx(ds,'Distance',4);setFx(ds,'Softness',12);" if ov.get("shadow") else "")
            + ("" if ov.get("blend") == "normal" else "t.blendingMode=BlendingMode.DIFFERENCE;")
            + "})();")
    # v4 flashes (offset)
    for sh in plan["shots"]:
        if sh.get("flash"):
            add(f"solid([1,1,1],{sh['f'][0] + M},{sh['f'][1] + M},'FLASH {sh['f'][0]}');")
        if sh.get("fade_from_white"):
            f0 = sh["f"][0]
            fk = sh.get("fade_keys", [[f0, 100], [f0 + 7, 0]])
            add(f"var fw=solid([1,1,1],{f0 + M},{fk[-1][0] + M}-1,'FADE WHITE {f0}');var op=TG(fw).property('ADBE Opacity');"
                + "".join(f"op.setValueAtTime(sec({fr + M}),{v});" for fr, v in fk))
    add("R.steps.push('captions+flashes');")

    # variant FX layers
    for ga_, gb_ in cfg.get("glow", []):
        add(f"(function(){{var v=adj({ga_},{gb_},'GLOW {ga_}');glow(v,82,30,0.3);}})();")
    if cfg.get("shake"):
        sk = cfg["shake"]
        a0, b0 = sk["f"]
        pos, scl, bl = [[a0, [960, 540]]], [[a0, 104]], [[a0, 0]]
        jit = [[26, -18], [-20, 14], [12, -8], [0, 0]]
        for n, h in enumerate(sk["hits"]):
            h = int(round(h))
            sgn = 1 if n % 2 == 0 else -1
            pos += [[h - 1, [960, 540]]] + [[h + i, [960 + sgn * dx, 540 + dy]] for i, (dx, dy) in enumerate(jit)]
            scl += [[h - 1, 104], [h, 112], [h + 6, 104]]
            bl += [[h - 1, 0], [h, 45], [h + 3, 0]]
        add(f"(function(){{var v=adj({a0},{b0},'SHAKE');var E=v.property('ADBE Effect Parade');var tr=E.addProperty('ADBE Geometry2');names(tr);"
            f"keyFx(tr,'Position',{json.dumps(pos)},'ADBE Geometry2-0002');keyFx(tr,'Scale',{json.dumps(scl)},'ADBE Geometry2-0003');"
            f"var db=E.addProperty('ADBE Motion Blur');names(db);setFx(db,'Direction',90);keyFx(db,'Blur Length',{json.dumps(bl)});}})();")
    if cfg.get("grain"):
        gr = cfg["grain"]
        add(f"(function(){{var v=adj({gr['f'][0]},{gr['f'][1]},'GRAIN');var n=v.property('ADBE Effect Parade').addProperty('ADBE Noise');names(n);"
            f"setFx(n,'Amount of Noise',{gr['amount']});var q=fxp(n,'Noise Type');if(q){{try{{q.setValue(0);}}catch(e){{}}}}}})();")
    for n, fl in enumerate(cfg.get("leaks", [])):
        cx = 260 if n % 2 == 0 else 1660
        add(f"(function(){{var l=solid([1,0.52,0.18],{fl},{fl + 9},'LEAK {fl}');ell(l,{cx},420,760,560,520,false);l.blendingMode=BlendingMode.ADD;"
            f"var o=TG(l).property('ADBE Opacity');o.setValueAtTime(sec({fl}),0);o.setValueAtTime(sec({fl + 2}),75);o.setValueAtTime(sec({fl + 9}),0);"
            f"var ps=TG(l).property('ADBE Position');ps.setValueAtTime(sec({fl}),[960,540]);ps.setValueAtTime(sec({fl + 9}),[{960 + (200 if n % 2 == 0 else -200)},540]);}})();")
    for fr, opv in cfg.get("flicker", []):
        add(f"(function(){{var l=solid([1,1,1],{fr},{fr},'FLICK {fr}');TG(l).property('ADBE Opacity').setValue({opv});}})();")
    for la, lb in cfg.get("letterbox", []):
        add(f"(function(){{var a=solid([0,0,0],{la},{lb},'BAR TOP',1920,138);TG(a).property('ADBE Position').setValue([960,69]);"
            f"var b=solid([0,0,0],{la},{lb},'BAR BOT',1920,138);TG(b).property('ADBE Position').setValue([960,1011]);}})();")
    add("R.steps.push('fx');")

    # subtitles
    st = cfg.get("sub_style")
    for a0, a1, txt in cfg["subs"]:
        if r5:
            d_ = a1 - a0 + 1
            ein, eout = max(3, min(7, d_ // 4)), max(3, min(6, d_ // 5))
            add(f"(function(){{var t=comp.layers.addText({js_str(txt)});var sp=t.property('ADBE Text Properties').property('ADBE Text Document');var d=sp.value;"
                f"d.resetCharStyle();d.fontSize={st['size']};try{{d.font='{st['font']}';}}catch(e){{R.warn.push('subfont');}}d.tracking={st.get('tracking', 0)};d.applyFill=true;d.fillColor=[1,1,1];d.applyStroke=false;"
                "d.justification=ParagraphJustification.CENTER_JUSTIFY;sp.setValue(d);"
                f"t.startTime=0;t.inPoint=sec({a0});t.outPoint=sec({a1}+1);var r=t.sourceRectAtTime(sec({a0}),false);"
                "TG(t).property('ADBE Anchor Point').setValue([r.left+r.width/2,r.top+r.height/2]);"
                f"tanim(t,{a0},{a1},{ein},{eout},8,6,8,97,101.5,960,{st['y']});t.name='SUB '+{js_str(txt[:30])};"
                + ("var ds=t.property('ADBE Effect Parade').addProperty('ADBE Drop Shadow');setFx(ds,'Opacity',230);setFx(ds,'Distance',3);setFx(ds,'Softness',10);" if st["shadow"] else "")
                + "})();")
            continue
        add(f"(function(){{var t=comp.layers.addText({js_str(txt)});var sp=t.property('ADBE Text Properties').property('ADBE Text Document');var d=sp.value;"
            f"d.resetCharStyle();d.fontSize={st['size']};try{{d.font='{st['font']}';}}catch(e){{R.warn.push('subfont');}}d.applyFill=true;d.fillColor=[1,1,1];d.applyStroke=false;"
            "d.justification=ParagraphJustification.CENTER_JUSTIFY;sp.setValue(d);"
            f"t.startTime=0;t.inPoint=sec({a0});t.outPoint=sec({a1}+1);var r=t.sourceRectAtTime(sec({a0}),false);"
            f"TG(t).property('ADBE Position').setValue([960,{st['y']}-(r.top+r.height/2)]);t.name='SUB '+{js_str(txt[:30])};"
            f"var o=TG(t).property('ADBE Opacity');o.setValueAtTime(sec({a0}),0);o.setValueAtTime(sec({a0 + 3}),100);o.setValueAtTime(sec({a1 - 2}),100);o.setValueAtTime(sec({a1 + 1}),0);"
            + ("var ds=t.property('ADBE Effect Parade').addProperty('ADBE Drop Shadow');setFx(ds,'Opacity',230);setFx(ds,'Distance',3);setFx(ds,'Softness',10);" if st["shadow"] else "")
            + "})();")
    add("R.steps.push('subs');")
    add("try{var fnt=comp.layers.length;}catch(e){}")
    add(f"p.save(new File('{SP}/MENTALIST_JANE_{var}.aep'));")
    add("R.saved=decodeURI(p.file.absoluteURI);R.numLayers=comp.numLayers;R.ok=true;")
    add("}catch(e){R.err=String(e)+' line '+e.line;}finally{app.endUndoGroup();}")
    add("out();")
    add("})();")
    js = "\n".join(L) + "\n"
    assert "\\" not in js, "backslash in JSX"
    (S / f"jsx/{JSXN}.jsx").write_text(js, encoding="utf-8")
    return js


def reset_jsx(var, guard_name):
    js = ("#target aftereffects\n(function(){\n"
          f"var S='{SP}';var r='';var p=app.project;\n"
          "if(p&&p.file===null&&p.numItems===0&&!p.renderQueue.rendering){r='ok already-empty';}\n"
          f"else if(!p||!p.file||decodeURI(p.file.absoluteURI).indexOf('{guard_name}')<0||p.dirty||p.renderQueue.rendering)"
          "{r='GUARD '+(p&&p.file?decodeURI(p.file.absoluteURI):'none')+' dirty='+(p?p.dirty:'');}\n"
          "else{p.close(CloseOptions.DO_NOT_SAVE_CHANGES);app.newProject();var q=app.project;r='ok n='+q.numItems+' dirty='+q.dirty+' file='+(q.file?'set':'none');}\n"
          f"var f=new File(S+'/jsx/{var}_reset_report.txt');f.open('w');f.write(r);f.close();\n}})();\n")
    assert "\\" not in js
    (S / f"jsx/{var}_reset.jsx").write_text(js, encoding="utf-8")


if __name__ == "__main__":
    var, guard = sys.argv[1], sys.argv[2]
    js = build(var)
    reset_jsx(var, guard)
    json.dump({k: {kk: vv for kk, vv in v.items()} for k, v in V.items()}, open(S / "plan/variants.json", "w"), indent=1)
    print(var, "ok", len(js), "bytes; total frames", V[var]["total"], "subs", len(V[var]["subs"]))
