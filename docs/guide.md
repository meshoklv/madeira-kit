# Guide: build, sign, install, configure, read the log

This is the whole loop for putting [Madeira](https://github.com/willfaust/Madeira) on your own iPhone and iterating on a game's settings.
Everything runs on **your Mac**; the phone is connected by USB. Scripts live in [`scripts/`](../scripts).

> [!IMPORTANT]
> You need **your own legally owned copy** of any game you run. Nothing in this repository helps you obtain, crack, patch or unprotect a game.

## 0. Prerequisites

| What | Notes |
|---|---|
| iPhone with a recent iOS | The author used an iPhone Air on an iOS 27.2 beta. JIT needs iOS 17.4+ for StikDebug. |
| Mac with Xcode command line tools | `codesign`, `xcrun devicectl`, `ditto`, `PlistBuddy` |
| Apple Developer account | A development certificate and a provisioning profile for **your** bundle id. The increased-memory-limit and extended-virtual-addressing entitlements need a paid membership. |
| JIT enabler | [StikDebug](https://github.com/StikDebug/StikDebug) (+ a local VPN loopback app such as LocalDevVPN). Madeira's built-in JIT helper needs a second App ID, which `sign.sh` removes. |
| `pymobiledevice3` | `pip3 install pymobiledevice3` - used by `scripts/device.py` for file access over USB. |

## 1. Get a Madeira build

Use a build from upstream, or build in your own fork on GitHub Actions (no Mac mini needed). Pitfalls the author hit while getting CI to pass, in case you do your own:

- LLVM must be built as **static libraries only**; FEX needs `TUNE_CPU=cortex-a78` (the native tune reads `/proc/cpuinfo`).
- Put `llvm-mingw` on `PATH` before Wine's `configure`; build Wine's `tools/*/all`, `include/all` and `make_xftmpl`.
- The runner's iOS SDK lacks `ri_page_wait_time_mach`; stub it in `server_ios.c`.
- DXMT shader headers for airconv have to be generated like meson does it. The **Windows-side DXMT DLLs** (`d3d11`/`dxgi`/`winemetal`) are not rebuilt by that CI; if you patch them, build them separately with llvm-mingw and swap them in (step 3).
- A cold CI run takes about 13-20 minutes with caches (LLVM for iOS, FEX for iOS, GnuTLS, native Wine tools), plus about 20 minutes for LLVM without a cache.

The result is a zip with `Madeira.app` at its top level.

## 2. Configure the kit

```bash
cp scripts/config.example.env scripts/config.env   # git-ignored
$EDITOR scripts/config.env                          # bundle id, team id, identity, profile, device ids, game folder
```

`config.env` holds only identifiers. Signing uses the certificate already in your keychain; no password is ever written anywhere.

## 3. Unpack, (optionally) swap DLLs, sign, install

```bash
scripts/unpack.sh ~/Downloads/Madeira-build.zip
# optional: put a patched DLL in (see patches/ and docs/perf/)
scripts/swap-dll.sh ./xtajit64.dll xtajit64.dll
scripts/sign.sh        # run from a logged-in GUI session (keychain access)
scripts/install.sh     # keeps app data: your game and configs survive
scripts/doctor.sh      # phone visible? app installed? >= 3 GB free? game copy present?
```

`sign.sh` rewrites the bundle id, embeds your profile, builds the entitlements, removes the JIT-helper extension, signs every dylib and framework, then the app.

## 4. Put your game on the phone

Copy **your own** game files into the app container, for example `Documents/wine/drive_c/Games/<GameName>/`, via Finder file sharing, the Files app, or `scripts/device.py put`. Steam games can be installed from inside Madeira (Madeira Dock) with your own Steam account.

## 5. Apply a config and run

```bash
scripts/apply-config.sh configs/ds1-play.cfg
```

It uploads `madeira.cfg`, reads it back and compares, creates the Wine `AppData` folders if missing (otherwise some games crash at startup), and rotates the previous log. Then:

1. Swipe Madeira away completely (otherwise the old settings stay in memory).
2. Enable JIT (StikDebug, Enable JIT for the Madeira bundle id).
3. Start the game from Madeira.

Ready-made profiles are in [`configs/`](../configs): `ds1-play.cfg`, `ds3-ux.cfg`, `ds3-h2-experimental.cfg` (needs patched builds) and an on-screen keyboard layout.

## 6. Read the log

```bash
scripts/pull-log.sh my-first-run      # phone must be unlocked; saves to $LOG_DIR and runs the analyzer
python3 tools/analyze-log.py path/to/log.txt --all
```

The analyzer reports which `env` values Madeira really accepted, the module load order, first-chance exceptions with registers, whether graphics/window/audio came up, and how the process ended. For performance runs see [`tools/ds3perf/`](../tools/ds3perf) and the notes in [`docs/perf/`](perf).

Without a cable: `xcrun devicectl device copy from --device <id> --domain-type appDataContainer --domain-identifier <bundle id> --source Documents/logs/<file> --destination /tmp/ml.txt`.
iOS crash and jetsam reports: `xcrun devicectl device info files --domain-type systemCrashLogs`.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Crash right at start in the game image, `0x140c9942c` (DSR) | Wine profile has no `AppData\Local` | `scripts/device.py profile fix` (done by `apply-config.sh`) |
| `c0000005` in `steamclient64` early | module handle narrowed to 32 bits by the Steam client library | needs Madeira PR #385 (see [upstream.md](upstream.md)) |
| Pad ignored although visible | game window never became foreground | Madeira PR #149 (merged) |
| Game takes touches as mouse clicks | controller layout shown | Madeira PR #150 (merged) |
| Process killed after ~35 s in a menu | redelivery watchdog counted writes cumulatively | Madeira PR #148 (merged) |
| New settings seem ignored | Madeira still running | swipe it away, then relaunch; check `accepted env:` in the analyzer output |
| Install fails | phone locked / not trusted / profile does not list the device | unlock, trust, regenerate the profile |

More: [bugs-and-fixes.md](bugs-and-fixes.md).
