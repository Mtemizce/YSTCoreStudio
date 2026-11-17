import importlib.util, json, os, sys, subprocess
S_ = [0, 0]
def ok(c, m):
    S_[0 if c else 1] += 1
    print(("OK   " if c else "FAIL ") + m)
from pathlib import Path
R = Path(__file__).resolve().parents[2]
KUL = R / "sistem/ayar/kullanici.json"; Y = KUL.read_bytes() if KUL.exists() else None
# sahte codex komutu: test makinesinde Codex CLI kurulu olmasa da "kurulu" sayılsın (gemini ise bilerek yok sayılır)
import tempfile
SAHTE = Path(tempfile.mkdtemp(prefix="yst-codex-"))
if os.name == "nt":
    (SAHTE / "codex.cmd").write_text("@echo off\r\n", encoding="utf-8")
else:
    for komut in ("codex", "x-terminal-emulator"):  # ikincisi: ekransız CI makinesinde terminal penceresi bulunamıyor hatası çıkmasın
        (SAHTE / komut).write_text("#!/bin/sh\n", encoding="utf-8"); (SAHTE / komut).chmod(0o755)
os.environ["PATH"] = str(SAHTE) + os.pathsep + os.environ["PATH"]
sys.path.insert(0, str(R / "sistem/panel"))
spec = importlib.util.spec_from_file_location("panel", R / "sistem/panel/panel.py"); P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)
UZ = ".cmd" if os.name == "nt" else ".sh"
yakalanan = []
P.subprocess.Popen = lambda *a, **k: yakalanan.append((a, k))
(R / "projeler/zz-cx").mkdir(exist_ok=True); (R / "projeler/zz-cx/brief.md").write_text("x", encoding="utf-8")
try:
    KUL.write_text(json.dumps({"ajanlar": {}, "orkestrator": {"calisma_ortami": "codex"}}), encoding="utf-8")
    P.claude_baslat("zz-cx", None)
    son = (R / f"sistem/ortam/yerel/claude_zz-cx-codex{UZ}").read_text(encoding="utf-8")
    ok("codex" in son and "claude " not in son.splitlines()[-2], "codex ortamı codex komutunu yazar")
    KUL.write_text(json.dumps({"ajanlar": {}, "orkestrator": {"calisma_ortami": "gemini-cli"}}), encoding="utf-8")
    try:
        P.claude_baslat("zz-cx", None)
    except ValueError as e:
        ok("kurulu değil" in str(e), "kurulu olmayan ortam açık hata verir")
    KUL.write_text(json.dumps({"ajanlar": {}}), encoding="utf-8")
    P.claude_baslat("zz-cx", None)
    son = (R / f"sistem/ortam/yerel/claude_zz-cx{UZ}").read_text(encoding="utf-8")
    ok("claude" in son and "/video projeler/zz-cx" in son, "varsayılan ortam Claude Code komutunu yazar")
finally:
    if Y is None:
        KUL.unlink(missing_ok=True)
    else:
        KUL.write_bytes(Y)
    import shutil; shutil.rmtree(R / "projeler/zz-cx", ignore_errors=True); shutil.rmtree(SAHTE, ignore_errors=True)
    for f in (R / "sistem/ortam/yerel").glob("claude_zz-cx*"): f.unlink()

print("SONUÇ: %d tamam, %d hata" % tuple(S_))
sys.exit(1 if S_[1] else 0)
