# Compatibility report

Self-reported results from one device, one tester. Not a guarantee for your phone.

**Device / software:** iPhone Air, iOS 27.2 beta; Madeira = upstream main (`279fd0f`) plus the pull requests listed in [upstream.md](upstream.md); JIT via StikDebug.
**Game files:** the author's own legally owned copies. Nothing is distributed here.

| Title | Status (2026-10-21) | Notes |
|---|---|---|
| Dark Souls Remastered (PC) | **Playable** | Title screen, loading an existing character, in-game, settings menu, on-screen Xbox controller. FPS and heat in this title were not measured. Without upstream PR #385 the game crashes at start (`c0000005` in `steamclient64`). |
| Dark Souls III (Steam via Madeira Dock) | **Launches, ~20 FPS stock in combat** | 60 FPS on cutscenes. Stock settings: heavy scenes ~17-20 FPS. With the experimental [H2 package](../configs/ds3-h2-experimental.cfg) (patched DLLs): median **36.7 FPS** (p10 28.8) in heavy scenes for the first minutes of a 12-minute run, **32-34 FPS** after the phone heats up (P cores 1.31 GHz). Earlier G1 package: 21.5 FPS median over a 26-minute run without freezes. Gamepad and save handling in DS3 were not exhaustively tested. |

## How the DS3 numbers moved (heavy scenes, median)

| Step | FPS | What changed |
|---|---|---|
| baseline (C2 set) | ~17-20 | pool split, no image copy, orphan-lock stamped |
| G1 | 21.5 | + lean diagnostics, in-process sync, x64 critical-section fast path, hot-SMC write windows |
| H2 | 36.7 | + DXMT buffer/command-list reuse, TLS fast path, lean SRW, thread QoS by name |

The H2 figure is the **sum** of several changes; the individual contribution of each was not measured (each upstream PR says so). After heat-up the GPU is the bottleneck (about 88% busy). Details, graphs-in-text and what was rejected (MetalFX: worse; `pool-low`: worse; same-bytes SMC skip: 93% of writes change bytes) are in [`perf/`](perf).

## Not measured / not tested

- Gamepad, multiplayer and long sessions in DS3.
- Other iPhone models, other iOS versions.
- The on-device behaviour of `MADEIRA_TLS_X64` in isolation (it was only enabled together with other keys).
