# Performance notes (Dark Souls III on iPhone Air)

Long-form engineering notes, written in Russian while the work was happening. Numbers are from the author's device; tags in the text mark how solid a statement is: `[факт]` = measured/read in code, `[версия]` = hypothesis, `[оценка]` = estimate. English one-line summaries:

| File | Summary |
|---|---|
| [DS3-PERF-log.md](DS3-PERF-log.md) | First log analysis: where a frame goes, CPU frequency drop, recompilation storm |
| [DS3-PERF-knobs.md](DS3-PERF-knobs.md) | Every performance lever available without rebuilding (config keys, expected gain, risk) |
| [DS3-PERF-next.md](DS3-PERF-next.md) | Per-frame cost breakdown and what to try next |
| [DS3-UX-SETTINGS.md](DS3-UX-SETTINGS.md) | The safe quality-of-life config set; every line justified |
| [DS3-PROD-MODE.md](DS3-PROD-MODE.md) | Cost of diagnostics and the lean "production" config |
| [DS3-POWER.md](DS3-POWER.md) | Energy per phase, CPU clamp, what frame caps buy you |
| [DS3-CORES.md](DS3-CORES.md) | How threads map to P/E cores; thread QoS by name (Madeira #401) |
| [DS3-SMC.md](DS3-SMC.md), [DS3-SMC-PATCH.md](DS3-SMC-PATCH.md), [DS3-TRANSLATION-CACHE.md](DS3-TRANSLATION-CACHE.md), [DS3-HOT-SMC-V2.md](DS3-HOT-SMC-V2.md) | Self-modifying code of the game's anti-tamper layer vs. FEX recompilation; options analysed; hot write windows (FEX #24) |
| [DS3-CS-FASTPATH.md](DS3-CS-FASTPATH.md) | x64 fast path for critical sections and TLS (wine #50) |
| [DS3-G1-NEXT.md](DS3-G1-NEXT.md) | After the G1 package: DXMT buffer churn and the H1 package (dxmt #42/#43, wine #51) |
| [DS3-SW-TSO.md](DS3-SW-TSO.md), [DS3-HW-TSO.md](DS3-HW-TSO.md) | Software TSO cost in FEX; why hardware TSO is not available on iOS without kernel support |
| [DS3-SERVER-HITCH.md](DS3-SERVER-HITCH.md) | Wineserver traffic and periodic hitches |
| [DS3-BG-PROCS.md](DS3-BG-PROCS.md) | Steam background processes and what they cost |
| [DS3-CRASH.md](DS3-CRASH.md), [DS3-DYNBUF-CRASH.md](DS3-DYNBUF-CRASH.md), [DS3-FREEZE.md](DS3-FREEZE.md) | Crash and freeze post-mortems (dxmt #40, #41, dynamic-buffer crash) |
| [DS3-MADEIRA-HISTORY.md](DS3-MADEIRA-HISTORY.md) | What the Madeira developers already tried for heavy games and what applies to DS3 |
| [DS3-OTHERS-30FPS.md](DS3-OTHERS-30FPS.md) | Web research: who else reports 30+ FPS on iPhone/iPad/Android and how |

Reproduce the numbers: `tools/ds3perf/parse.py` -> `phases.py` / `bins.py` / `threads.py` on a Madeira log.
