# Bugs found while bringing Dark Souls Remastered up on Madeira

Field notes, 27 Sep - 19 Oct 2026. Each row: what you see, the cause we measured, the fix, where the fix lives now.
Reference copies of the patches are in [`../patches/`](../patches); the upstream pull requests are authoritative.

| # | Symptom | Cause | Fix | Where it lives |
|---|---|---|---|---|
| 1 | Crash `c0000018` at start | A fixed-base exe below 64 MB did not get the `0x140000000` window | exe-window rule | upstream (Madeira #111) |
| 2 | Crash `0x141e5e7cd` after the first writes of the game's anti-tamper code | `InSyscallCallback` leak: the `[exec-req]` branch returned without `leave_syscall_callback()` | one line in `signal_arm64ec.c` | **wine #18 merged** |
| 3 | `c0000005` in `steamclient64` (+0x7a01) | The Steam client module narrows an `HMODULE` to 32 bits; iOS cannot map below the 4 GB floor, so the module lives at a high address | image low-alias + `VirtualQuery` clip | **Madeira #385 open** |
| 4 | Crash `0x140c9942c` (known-folder lookup) | Wine profile `C:\users\<user>` had no `AppData` | create the folders (`device.py profile fix`) | upstream (#112, #321) |
| 5 | Gamepad: game does not see it | The game folder's own `xinput1_3.dll` was loaded instead of the builtin | loader prefers the builtin XInput | **wine #19 merged** |
| 6 | Gamepad: seen but ignored | Game window not foreground (nothing activates it on iOS) | win32u makes the main window active while it polls XInput | **Madeira #149 merged** |
| 7 | Touches that miss a button act as mouse clicks | - | no touch-as-mouse while a controller layout is shown | **Madeira #150 merged** |
| 8 | Process killed ~35 s into the settings menu | The `ml461` watchdog counted handled self-modifying-code writes cumulatively; 7 keys cycling per frame reached 2000 | count only back-to-back identical faults per thread | **Madeira #148 merged** |

## Lessons

- Verify what is **actually loaded** (image sizes and bases in the log) instead of trusting the config file.
- Keep return-address and key-chain diagnostics around; they found the gamepad gap quickly.
- One change, one run, one log. Analyse with `tools/analyze-log.py`.
- A clean build beats a mixed one: a build that mixed old and new parts crashed in `signal_set_full_context`; a clean CI build did not.
