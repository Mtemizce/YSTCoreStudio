import json, os, shutil, sys, time
from pathlib import Path
H = Path(__file__).parent
STATE = H / "state.json"; DRIVE = H / "drive"
a = sys.argv[1:]
st = json.loads(STATE.read_text()) if STATE.exists() else {"remotes": {}}
def local(spec):
    n, _, p = spec.partition(":")
    return DRIVE / p.strip("/") if p else DRIVE
if a[0] == "version": print("rclone v1.99.0-fake")
elif a[0] == "listremotes":
    for k, v in st["remotes"].items(): print(k + ":" + ((" " + v) if "--long" in a else ""))
elif a[0] == "config" and a[1] == "create":
    print("2026/01/01 NOTICE: If your browser doesn't open automatically go to the following link: http://127.0.0.1:53682/auth?state=fake123", flush=True)
    time.sleep(1.5)
    if (H / "reddet").exists(): sys.exit(1)
    st["remotes"][a[2]] = a[3]; STATE.write_text(json.dumps(st)); print("[%s] ok" % a[2])
elif a[0] == "config" and a[1] == "delete":
    st["remotes"].pop(a[2], None); STATE.write_text(json.dumps(st))
elif a[0] == "lsjson":
    d = local(a[1]); out = []
    if "--dirs-only" in a:
        out = [{"Path": p.name, "IsDir": True} for p in sorted(d.iterdir()) if p.is_dir()]
    else:
        for p in sorted(d.rglob("*")):
            if p.is_file(): out.append({"Path": p.relative_to(d).as_posix(), "Size": p.stat().st_size, "ModTime": "2022-06-%02dT10:11:12.123456789Z" % (1 + len(out) % 27), "IsDir": False})
    print(json.dumps(out))
elif a[0] == "copyto":
    src = local(a[1]); dst = Path(a[2]); (H / "indirilen.log").open("a").write(a[1] + "\n")
    if not src.is_file(): print("not found", file=sys.stderr); sys.exit(3)
    dst.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(src, dst)
else:
    sys.exit(9)
