# Third-party notices

This repository contains no third-party binaries and no game files. It references, and ships patches against, the following projects. Each patch file is a derivative work of the project it targets and is offered under **that project's** license, not the repository's MIT license.

| Project | License | Used for |
|---|---|---|
| [willfaust/Madeira](https://github.com/willfaust/Madeira) | GPL-3.0 | The iOS app these tools sign/install; `patches/*/madeira-*.patch` |
| [willfaust/wine](https://github.com/willfaust/wine) (Wine) | LGPL-2.1-or-later | `patches/*/wine-*.patch` |
| [willfaust/FEX](https://github.com/willfaust/FEX) (FEX-Emu) | MIT | `patches/open/fex-*.patch` |
| [willfaust/dxmt](https://github.com/willfaust/dxmt) (DXMT) | MIT (fork); see upstream 3Shain/dxmt | `patches/open/dxmt-*.patch` |
| [StikDebug](https://github.com/StikDebug/StikDebug) | AGPL-3.0 | Only referenced as the suggested JIT enabler |
| [pymobiledevice3](https://github.com/doronz88/pymobiledevice3) | GPL-3.0 | Imported by `scripts/device.py` at run time; not bundled |

Dark Souls, Dark Souls Remastered and Dark Souls III are trademarks of their respective owners (FromSoftware / Bandai Namco). This project is not affiliated with or endorsed by them, Apple, or the Madeira authors. Games are named only to describe compatibility results.
