# Upstream contributions

All work in this kit that touches the emulation stack was sent upstream rather than forked. Account: [@meshoklv](https://github.com/meshoklv). The author is credited in Madeira's Settings > Credits for the controller and crash-guard fixes.

Write-up and discussion: [Madeira issue #56](https://github.com/willfaust/Madeira/issues/56).

## Merged

| PR | What it does |
|---|---|
| [wine #18](https://github.com/willfaust/wine/pull/18) | ntdll ARM64EC: leave the syscall callback on the `[exec-req]` return path |
| [wine #19](https://github.com/willfaust/wine/pull/19) | ntdll: load the builtin XInput even when the game ships its own copy |
| [Madeira #148](https://github.com/willfaust/Madeira/pull/148) | ntdll: count only back-to-back identical fault redeliveries per thread |
| [Madeira #149](https://github.com/willfaust/Madeira/pull/149) | win32u iOS: make a process's main window foreground while it polls XInput |
| [Madeira #150](https://github.com/willfaust/Madeira/pull/150) | Touch controls: a touch that misses the controls is no mouse while a controller layout is shown |

## Open (state checked 2026-10-22)

| PR | What it does | Patch copy |
|---|---|---|
| [Madeira #385](https://github.com/willfaust/Madeira/pull/385) | Give a narrowed image base a low name; `VirtualQuery` reports only allocatable memory as free | [`madeira-385-image-low-alias.patch`](../patches/open/madeira-385-image-low-alias.patch) |
| [Madeira #387](https://github.com/willfaust/Madeira/pull/387) | Library: recommended settings for Dark Souls: Remastered and Dark Souls III | - |
| [Madeira #389](https://github.com/willfaust/Madeira/pull/389) | Madeira Dock: replace Steam discovery values left by a client that is gone | - |
| [Madeira #401](https://github.com/willfaust/Madeira/pull/401) | `MADEIRA_THREAD_QOS`: opt-in QoS class per guest thread by thread name | - |
| [wine #50](https://github.com/willfaust/wine/pull/50) | opt-in x64 fast paths for critical sections and `TlsGetValue` (`MADEIRA_CS_X64`, `MADEIRA_TLS_X64`) | [`wine-cs-x64-fastpath.patch`](../patches/open/wine-cs-x64-fastpath.patch) |
| [wine #51](https://github.com/willfaust/wine/pull/51) | opt-in `MADEIRA_SYNC_LEAN`: drop the SRW history ring and WaitOnAddress counters | [`wine-g1next-sync-lean.patch`](../patches/open/wine-g1next-sync-lean.patch) |
| [dxmt #40](https://github.com/willfaust/dxmt/pull/40) | d3d11: report a resolved `MipLevels` for an "all mips" SRV (fixes a DS3 black-screen crash) | - |
| [dxmt #41](https://github.com/willfaust/dxmt/pull/41) | backport of 3Shain/dxmt `aadf0fb`: advance the GS/TS draw-argument marshal loops (fixes a DS3 freeze) | - |
| [dxmt #42](https://github.com/willfaust/dxmt/pull/42) | opt-in `DXMT_CMDLIST_KEEP_BLOCK` | [`dxmt-g1next-dyn-keep.patch`](../patches/open/dxmt-g1next-dyn-keep.patch) (together with #43) |
| [dxmt #43](https://github.com/willfaust/dxmt/pull/43) | opt-in `DXMT_DYN_KEEP` | (same patch) |
| [FEX #24](https://github.com/willfaust/FEX/pull/24) | hot SMC write windows, `FEX_HOT_SMC_PAGES=2`, off by default | [`fex-hot-smc-pages.patch`](../patches/open/fex-hot-smc-pages.patch) + [`fex-hot-smc-v2.patch`](../patches/open/fex-hot-smc-v2.patch) |

`patches/merged/` holds reference copies of the merged changes (named by PR number); always prefer the upstream tree. Licensing of the patches follows the project they patch (see [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)).

`patches/open/ds3-dynbuf.patch` is a reference copy of a small experiment that makes `MADEIRA_LOCK_ORPHAN=stamped` the default; it is not tracked by a PR in the table above.
