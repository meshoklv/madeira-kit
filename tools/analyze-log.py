#!/usr/bin/env python3
"""Summarise a Madeira run log (Documents/logs/<exe>-<date>.txt or madeira-log.txt).

  analyze-log.py <log> [--run N | --all]

By default the last run in the file is analysed (a run starts at the "Custom exe:" line).
Logs may contain binary bytes: the file is read as bytes and decoded with replacement.

What it looks for:
  env      [madeira-env] K=V       - what Madeira actually exported from madeira.cfg (verify, do not trust the file)
  modules  "Load module NAME"     - load order, the last module loaded
  crashes  [exc] code=... addr=... (first chance), [guest-exact] rip=... with [guest-state] x86 registers,
           [rtcs] pre: code=c0000409 (fastfail), NtTerminateProcess / abort_process (the game process ended)
  graphics / window / audio - HEURISTIC: there is no explicit "D3D11 device created" line,
           so we look for d3d11/dxgi/winemetal loads and DXMT present-chain lines.
"""
import re, argparse
from collections import Counter, OrderedDict

# Known crash site: SHGetKnownFolderPath(FOLDERID_LocalAppData) returned NULL because the
# Wine profile had no AppData\Local (Dark Souls Remastered 1.3, see docs/bugs-and-fixes.md #4).
APPDATA_CRASH = 0x140c9942c
LOCALAPPDATA_GUID = "f1b32785-6fba-4fcf-9d55-7b8e7f157091"
EXE_LO, EXE_HI = 0x140000000, 0x150000000   # typical fixed-base x64 game image window

R = {
    "ts": re.compile(r"^\[(\d\d:\d\d:\d\d\.\d+)\]"),
    "run": re.compile(r"\[INFO\] Custom exe: (.*)"),
    "cfg": re.compile(r"\[INFO\] madeira\.cfg: (.*)"),
    "env": re.compile(r"\[madeira-env\] \S+ ([^=\s]+)=(.*)"),
    "img": re.compile(r"\[jit-pool\] image (0x[0-9a-f]+)\+(0x[0-9a-f]+) \(([^)]+)\)"),
    "mod": re.compile(r"\bLoad module (\S+)"),
    "exc": re.compile(r"\[exc\] \S+ code=([0-9a-fA-F]+) addr=([0-9A-Fa-f]+)"),
    "gx": re.compile(r"\[guest-exact\].*?rip=(0x[0-9a-f]+)(?: x86=([0-9a-f ]+))?"),
    "gs": re.compile(r"\[guest-state\]\s+(.*)"),
    "rtcs409": re.compile(r"\[rtcs\] pre: code=c0000409 addr=([0-9A-Fa-f]+)"),
    "term": re.compile(r"NtTerminateProcess\(.*exit_code=(0x[0-9a-f]+)"),
    "abort": re.compile(r"abort_process: status=(0x[0-9a-f]+)"),
    "live": re.compile(r"^\[x86_live\]\s+(.*)"),
}
D3D_MODS = ("d3d11.dll", "dxgi.dll", "winemetal.dll", "d3dcompiler_47.dll")
D3D_HINT = re.compile(r"swapchain|CreateSwapChain|\[fence\]|\[bc-census\]|MetalFX|D3D11CreateDevice|"
                      r"\[api-census\]|EnterFullscreen|ResizeBuffers|\bPresent\b", re.I)
WND_HINT = re.compile(r"CreateWindow|NtUserCreateWindowEx|\[wnd[^\]]*\]|ShowWindow|\bhwnd\b", re.I)
AUD_MODS = ("fmodex64.dll", "fmod_event64.dll", "xaudio2_7.dll", "xaudio2_9.dll", "dsound.dll",
            "mmdevapi.dll", "winecoreaudio.drv", "x3daudio1_7.dll")
AUD_HINT = re.compile(r"xaudio|dsound|mmdevapi|coreaudio|IAudioClient|\[audio[^\]]*\]", re.I)

# periodic statistics lines that are never "the last meaningful line"
NOISE = re.compile(r"^(\[[\d:.]+\] )?\[(xp|xp-t|xp-api|waiters|footprint|alert-ring|phys-map|rip-profile|"
                   r"holes<64G|malloc-zones|thread-sample)\]|^\[waiters\]|^\S*\)? P=\d")
LINE_OK = re.compile(r"^(\[|[0-9a-f]{4}:|[EDIW] \d+ |no-teb:|ml\d+)")


def read_lines(path):
    return open(path, "rb").read().decode("utf-8", "replace").splitlines()


def split_runs(lines):
    starts = [i for i, l in enumerate(lines) if R["run"].search(l)]
    if not starts:
        return [(0, len(lines))]
    # lines before the first "Custom exe" (app start, cfg summary) belong to the first run
    bounds = [0] + starts[1:] + [len(lines)]
    return list(zip(bounds[:-1], bounds[1:]))


def hx(s):
    return int(s, 16)


def analyze(lines, a, b, label):
    L = lines[a:b]
    out = []; p = out.append
    ts = [m.group(1) for l in L for m in [R["ts"].match(l)] if m]
    exe = next((m.group(1) for l in L for m in [R["run"].search(l)] if m), "?")
    p(f"== {label}: lines {a+1}-{b}, time {ts[0] if ts else '?'} ... {ts[-1] if ts else '?'}")
    p(f"exe: {exe}")
    cfg = [m.group(1) for l in L for m in [R["cfg"].search(l)] if m]
    if cfg: p(f"madeira.cfg (as Madeira saw it): {cfg[-1]}")
    env = OrderedDict((m.group(1), m.group(2).strip()) for l in L for m in [R["env"].search(l)] if m)
    p("accepted env: " + (", ".join(f"{k}={v}" for k, v in env.items()) if env else "NO [madeira-env] lines"))

    imgs = [(m.group(3), hx(m.group(1)), hx(m.group(2))) for l in L for m in [R["img"].search(l)] if m]
    mods = [m.group(1) for l in L for m in [R["mod"].search(l)] if m]
    if not mods:  # some logs have no "Load module" lines - fall back to image order
        mods = [name for name, _, _ in imgs]
    p("")
    p(f"modules loaded: {len(mods)}; last: {mods[-1] if mods else '-'}")
    if mods: p("  last 6: " + " ".join(mods[-6:]))
    lm = {x.lower() for x in mods}

    exc = [(m.group(1).lower(), hx(m.group(2))) for l in L for m in [R["exc"].search(l)] if m]
    cnt = Counter(exc)
    p("")
    p(f"first-chance exceptions: {len(exc)}, distinct: {len(cnt)}")
    for (c, ad), n in cnt.most_common(8):
        where = "game image" if EXE_LO <= ad < EXE_HI else ""
        p(f"  {c} @0x{ad:x} x{n} {where}")
    hit_appdata = any(ad == APPDATA_CRASH for _, ad in exc) or any("140c9942c" in l.lower() for l in L)
    if hit_appdata:
        p("WARNING: fault @0x140c9942c = missing AppData\\Local: the game got an empty LocalAppData path")

    # known-folder lookups (visible only with WINEDEBUG ...,trace+shell)
    sh = [l.strip() for l in L if ":shell:" in l]
    la = [l for l in sh if LOCALAPPDATA_GUID in l.lower()]
    fails = [l for l in sh if "Failed to get folder path" in l]
    finals = [l for l in sh if "Final path is" in l or "output path is" in l]
    if sh:
        p(f"shell32 (trace+shell): {len(sh)} lines, LocalAppData lookups {len(la)}, "
          f"'Failed to get folder path' {len(fails)}")
        for l in (fails[:3] + [x for x in finals if "appdata" in x.lower()][:3]):
            p("  " + l[:170])
    else:
        p("shell32: no lines (no WINEDEBUG=...,trace+shell in the cfg, or shell32 was never reached)")

    # guest-exact + registers
    gx = []
    for i, l in enumerate(L):
        m = R["gx"].search(l)
        if m:
            regs = []
            for l2 in L[i+1:i+8]:
                g = R["gs"].search(l2)
                if g: regs.append(g.group(1).strip())
                elif regs: break
            gx.append((i, hx(m.group(1)), (m.group(2) or "").strip(), regs))
    f409 = [hx(m.group(1)) for l in L for m in [R["rtcs409"].search(l)] if m]
    term = [m.group(1) for l in L for m in [R["term"].search(l)] if m]
    abrt = [m.group(1) for l in L for m in [R["abort"].search(l)] if m]
    p(f"c0000409 (fastfail): {'YES @' + ', '.join(sorted({hex(x) for x in f409})) if f409 else 'no'}")
    c5 = sorted({ad for c, ad in exc if c == "c0000005"})
    if c5: p("c0000005 addresses: " + ", ".join(hex(x) for x in c5[:10]) + (" ..." if len(c5) > 10 else ""))
    if gx:
        _, rip, x86, regs = gx[-1]
        p(f"registers at the fault (rip=0x{rip:x}{', x86: ' + x86[:47] if x86 else ''}):")
        for r_ in regs: p("  " + r_)
    live = [m.group(1) for l in L for m in [R["live"].search(l)] if m]
    if live: p("last [x86_live]: " + " | ".join(live[-2:]))

    # graphics, window, audio (heuristic)
    p("")
    d3 = [x for x in D3D_MODS if x in lm]
    dh = [l.strip()[:140] for l in L if D3D_HINT.search(l) and "FNA3D" not in l]
    p(f"graphics: modules {', '.join(d3) if d3 else 'NOT loaded'}; device/present hints: "
      f"{len(dh)}" + (f" (first: {dh[0]})" if dh else " - none found"))
    wh = [l.strip()[:140] for l in L if WND_HINT.search(l)]
    p(f"window: user32/win32u {'loaded' if {'user32.dll', 'win32u.dll'} <= lm else 'not loaded'}; "
      f"window-creation hints: {len(wh)}" + (f" (first: {wh[0]})" if wh else " - none found"))
    au = [x for x in AUD_MODS if x in lm]
    ah = [l.strip()[:140] for l in L if AUD_HINT.search(l) and "AudioSession - RootQueue" not in l]
    p(f"audio: modules {', '.join(au) if au else 'none'}; audio-output hints: {len(ah)}"
      + (f" (first: {ah[0]})" if ah else " - none found"))

    # how it ended
    p("")
    if term or abrt:
        p(f"END: game process terminated, code {(term or abrt)[-1]}"
          + (" (fastfail - the process was killed by a handler after a fault)" if (term or abrt)[-1] == "0xc0000409" else ""))
    else:
        p("END: no process termination in the log - the game is hung/running, or the app was closed earlier")
        last = [l.strip() for l in L if LINE_OK.match(l) and not NOISE.search(l)]
        if last: p("  last meaningful line: " + last[-1][:170])
    verdict = []
    if hit_appdata: verdict.append("crashed at 0x140c9942c - no AppData\\Local (check the Wine profile: scripts/device.py profile fix)")
    elif f409: verdict.append("fastfail")
    elif c5 and (term or abrt): verdict.append(f"crashed (c0000005 @{hex(c5[-1])})")
    if d3 and not (term or abrt): verdict.append("graphics loaded, no end - look at the screen")
    p("VERDICT: " + ("; ".join(verdict) + "; " if verdict else "") + f"last module {mods[-1] if mods else '-'}")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log"); ap.add_argument("--run", type=int)
    ap.add_argument("--all", action="store_true")
    o = ap.parse_args()
    lines = read_lines(o.log)
    runs = split_runs(lines)
    sel = list(range(len(runs))) if o.all else [(o.run - 1) if o.run else len(runs) - 1]
    print(f"{o.log}: {len(lines)} lines, runs in file: {len(runs)}")
    for i in sel:
        a, b = runs[i]
        print(analyze(lines, a, b, f"run {i+1}/{len(runs)}"))


if __name__ == "__main__":
    main()
