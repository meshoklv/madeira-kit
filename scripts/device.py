#!/usr/bin/env python3
"""Files inside the Madeira app container on a USB-connected iPhone (pymobiledevice3, AFC house_arrest).

Usage:  python3 scripts/device.py <command> [args]     (DEVICE_UDID and BUNDLE_ID come from config.env)
  info                     model, free/total space on the phone
  ls <path>                list a folder (paths are relative to the container root: /Documents/...)
  exists <path>            exit code 0/1
  get <path> <local>       copy a file from the phone
  put <local> <path>       copy a file to the phone (overwrites)
  mv <from> <to>           rename on the phone (target is overwritten)
  rotate <path>            <path> -> <path>.prev (if present), so the next run writes a fresh log
  profile [fix]            Wine profile: do drive_c/users/<user>/AppData/{Local,LocalLow,Roaming} exist? fix = create them

USB only (connection_type="USB"). The phone must be unlocked to read Documents/logs.
"""
import asyncio, inspect, os, sys, warnings
warnings.filterwarnings("ignore")
from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.services.house_arrest import HouseArrestService

UDID = os.environ.get("DEVICE_UDID", "")
BID = os.environ.get("BUNDLE_ID", "")
if not UDID or not BID:
    sys.exit("set DEVICE_UDID and BUNDLE_ID (source scripts/config.env first)")


async def w(x):
    return await x if inspect.isawaitable(x) else x


async def connect():
    ld = await w(create_using_usbmux(serial=UDID, connection_type="USB"))
    return ld, await w(HouseArrestService.create(ld, BID, documents_only=False))


async def exists(afc, p):
    try:
        return bool(await w(afc.exists(p)))
    except Exception:
        return False


async def rm_if(afc, p):
    if await exists(afc, p):
        await w(afc.rm(p))


async def main(argv):
    if not argv:
        print(__doc__); return 2
    cmd, a = argv[0], argv[1:]
    ld, afc = await connect()
    if cmd == "info":
        di = await w(afc.get_device_info())
        free, tot = int(di.get("FSFreeBytes", 0)), int(di.get("FSTotalBytes", 0))
        print(f"model={di.get('Model')} free={free/2**30:.1f}GB total={tot/2**30:.1f}GB")
        print(f"FREE_GB={free/2**30:.1f}")
    elif cmd == "ls":
        for n in sorted(await w(afc.listdir(a[0]))):
            if n in (".", ".."): continue
            try:
                st = await w(afc.stat(a[0].rstrip("/") + "/" + n)); sz = st.get("st_size", "?"); t = st.get("st_ifmt", "")
            except Exception:
                sz, t = "?", "?"
            print(f"{t:8} {sz:>12} {n}")
    elif cmd == "exists":
        return 0 if await exists(afc, a[0]) else 1
    elif cmd == "get":
        d = await w(afc.get_file_contents(a[0]))
        open(os.path.expanduser(a[1]), "wb").write(d); print(f"got {len(d)} bytes {a[0]}")
    elif cmd == "put":
        data = open(os.path.expanduser(a[0]), "rb").read()
        await w(afc.set_file_contents(a[1], data)); print(f"put {len(data)} bytes -> {a[1]}")
    elif cmd == "mv":
        await rm_if(afc, a[1]); await w(afc.rename(a[0], a[1])); print(f"mv {a[0]} -> {a[1]}")
    elif cmd == "rotate":
        if await exists(afc, a[0]):
            await rm_if(afc, a[0] + ".prev"); await w(afc.rename(a[0], a[0] + ".prev")); print(f"rotated {a[0]} -> .prev")
        else:
            print(f"nothing to rotate: {a[0]}")
    elif cmd == "profile":
        return await profile(afc, fix=(a[:1] == ["fix"]))
    else:
        print(__doc__); return 2
    return 0


PREFIX = "/Documents/wine"
LEAVES = ("AppData/Local", "AppData/LocalLow", "AppData/Roaming", "Documents")


async def profile(afc, fix):
    """Wine profile check: does drive_c/users/<user>/AppData/Local exist, and what does user.reg say about it.
    A missing AppData skeleton crashes some games at startup."""
    import re
    users_dir = f"{PREFIX}/drive_c/users"
    users = [u for u in await w(afc.listdir(users_dir)) if u not in (".", "..", "Public")]
    print(f"users: {', '.join(users) or '-'}")
    reg_users, reg = set(), b""
    try:
        reg = await w(afc.get_file_contents(f"{PREFIX}/user.reg"))
        txt = reg.decode("utf-8", "replace")
        for line in txt.splitlines():
            if re.search(r'"Local AppData"|"LocalAppData"|"Personal"=', line):
                print("user.reg:", line.strip()[:150])
        reg_users = {m.lower() for m in re.findall(r'C:\\\\users\\\\([^\\"]+)\\\\', txt)}
        if "usersmadeira" in txt.lower():
            print("FAIL user.reg: malformed path form C:\\usersmadeira is still present")
    except Exception as e:
        print(f"user.reg not readable: {e}")
    print(f"users mentioned in user.reg: {', '.join(sorted(reg_users)) or '-'}")
    marker = await exists(afc, f"{PREFIX}/.madeira-profile-repaired-ml667")
    print(f"profile-repair marker: {'present' if marker else 'MISSING'}")
    want = sorted(({u.lower() for u in users} | reg_users | {"madeira", "mobile"}) - {"public"})
    missing = []
    for u in want:
        real = next((x for x in users if x.lower() == u), u)
        for leaf in LEAVES:
            p = f"{users_dir}/{real}/{leaf}"
            if not await exists(afc, p):
                missing.append(p)
    for p in missing:
        if fix:
            await w(afc.makedirs(p)); print(f"created: {p}")
        else:
            print(f"missing: {p}")
    ok = not missing or fix
    print(f"APPDATA={'ok' if not missing else ('fixed' if fix else 'missing')}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])) or 0)
