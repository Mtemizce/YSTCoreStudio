#!/usr/bin/env python3
"""Taşıma onarımı: klasör başka bir yere (ya da başka bir bilgisayara) kopyalandığında çalışan şeyleri yeni yere bağlar.
Başlat.cmd her açılışta çağırır; hiçbir şey değişmediyse ucuz bir denetimle biter. Yalnızca standart kütüphane.

Neden gerekli: Python sanal ortamı (venv) ve bazı yapılandırma dosyaları KURULUM ANINDAKİ mutlak yolu içerir:
  - venv/pyvenv.cfg        → temel Python'un yeri (başka bilgisayarda farklı olabilir)
  - kurgu editable kurulum → kurgu/ klasörünün mutlak yolu; venv/Scripts/*.exe başlatıcıları → venv'in mutlak yolu
  - kurgu-ayar/config.json → node_modules ve kurgu başlatıcısının mutlak yolu
  - önceki oturumlardan kalan claude_*.cmd betikleri, proje dosyalarında yanlışlıkla kalmış eski kök yolu
Onarım bunların hepsini yeni konuma göre yeniden yazar. Python'un ana sürümü (3.x) değiştiyse venv yeniden kurulur (kurulum.py devam eder).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SISTEM = ROOT / "sistem"
ORTAM = SISTEM / "ortam"
YEREL = ORTAM / "yerel"
VENV = ORTAM / "venv"
VENV_PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
NW = 0x08000000 if os.name == "nt" else 0
sys.path.insert(0, str(SISTEM / "araclar"))
import konum as K  # noqa: E402


def _calistir(cmd, zaman=120, **kw):
    try:
        return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, timeout=zaman, creationflags=NW, **kw)
    except (OSError, subprocess.TimeoutExpired) as e:
        class R:  # noqa: N801
            returncode, stdout, stderr = 99, "", str(e)
        return R()


def venv_cfg() -> dict:
    d = {}
    try:
        for s in (VENV / "pyvenv.cfg").read_text(encoding="utf-8").splitlines():
            if "=" in s:
                k, v = s.split("=", 1)
                d[k.strip()] = v.strip()
    except OSError:
        pass
    return d


def venv_calisiyor() -> bool:
    if not VENV_PY.exists():
        return False
    r = _calistir([VENV_PY, "-c", "import sys, PIL; print(sys.prefix)"], 60)
    return r.returncode == 0 and os.path.normcase(os.path.abspath(r.stdout.strip())) == os.path.normcase(str(VENV))


def ayni_surum_python(surum: str):
    """venv'in oluşturulduğu ana.alt sürümde (örn. 3.12) bir sistem Python'u: (komut listesi) ya da None."""
    m = re.match(r"(\d+)\.(\d+)", surum or "")
    if not m:
        return None
    anahtar = (int(m.group(1)), int(m.group(2)))
    if sys.version_info[:2] == anahtar and sys.executable:
        return [sys.executable]
    if os.name == "nt":
        r = _calistir(["py", f"-{anahtar[0]}.{anahtar[1]}", "-c", "import sys;print(sys.executable)"], 20)
        if r.returncode == 0 and r.stdout.strip():
            return [r.stdout.strip()]
    return None


def _metin_degistir(p: Path, eski_kaliplar: list[str], yeni: str) -> bool:
    try:
        s = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    ys = s
    for k in eski_kaliplar:
        if k and k in ys:
            ys = ys.replace(k, yeni.replace("\\", "/") if ("/" in k and "\\" not in k) else (yeni.replace("\\", "\\\\") if "\\\\" in k else yeni))
    if ys != s:
        p.write_text(ys, encoding="utf-8")
        return True
    return False


def onar(yazdir=print, zorla: bool = False) -> dict:
    """{'degisti','eylemler':[...],'venv_yeniden_kur':bool,'uyarilar':[...]}"""
    damga = K.damga_oku()
    eski_kok = damga.get("kok")
    eski_makine = damga.get("makine")
    yer_degisti = bool(eski_kok) and os.path.normcase(eski_kok) != os.path.normcase(str(ROOT))
    makine_degisti = bool(eski_makine) and eski_makine != K.makine()
    degisti = yer_degisti or makine_degisti or zorla
    s = {"degisti": degisti, "eski_kok": eski_kok, "eylemler": [], "uyarilar": [], "venv_yeniden_kur": False}
    if not degisti and (VENV_PY.exists() is False or venv_calisiyor()):
        K.damga_yaz()
        try:  # bu bilgisayarın stüdyo kökü kaydı (ucuz); yoksa oluşturur
            sys.path.insert(0, str(SISTEM / "arsiv"))
            import arsiv as A
            c = A.baglan()
            K.studyo_guncelle(c)
            c.close()
        except Exception as e:  # noqa: BLE001
            s["uyarilar"].append(f"veritabanı yolu yazılamadı: {e}")
        return s
    if degisti:
        yazdir(f"  Klasör yeri değişti: {eski_kok} → {ROOT}" if yer_degisti else f"  Başka bir bilgisayar algılandı ({eski_makine} → {K.makine()})")

    # 1) venv: temel Python bulunamıyorsa pyvenv.cfg'yi yeniden yaz
    if VENV_PY.exists() and not venv_calisiyor():
        cfg = venv_cfg()
        py = ayni_surum_python(cfg.get("version", ""))
        if py:
            r = _calistir(py + ["-m", "venv", "--upgrade", str(VENV)], 180)
            if r.returncode == 0 and venv_calisiyor():
                s["eylemler"].append("venv: temel Python bu bilgisayardaki Python'a bağlandı (venv --upgrade)")
            else:
                s["venv_yeniden_kur"] = True
                s["uyarilar"].append("venv onarılamadı: " + (r.stderr or r.stdout or "")[-200:])
        else:
            s["venv_yeniden_kur"] = True
            s["uyarilar"].append(f"venv Python {cfg.get('version', '?')} ile kurulmuş; bu bilgisayarda aynı sürüm yok → ortam yeniden kurulacak")
        if s["venv_yeniden_kur"]:
            import shutil
            shutil.rmtree(VENV, ignore_errors=True)
            (YEREL / "kurulum.ok").unlink(missing_ok=True)  # kurulum.py venv'i baştan kurar (diğer adımlar atlanır/hızlıdır)
            s["eylemler"].append("venv silindi; ilk kurulum adımları yeniden çalışacak")
    # 2) editable kurgu kurulumu + başlatıcı exe'ler (venv'in mutlak yolunu içerir)
    if VENV_PY.exists() and not s["venv_yeniden_kur"]:
        sp = VENV / "Lib" / "site-packages" if os.name == "nt" else next((VENV / "lib").glob("python*/site-packages"), VENV / "lib")
        eski_kalip = [eski_kok] if (eski_kok and yer_degisti) else []
        if eski_kalip:
            n = 0
            for f in list(sp.glob("__editable__*")) + list(sp.glob("*.dist-info/direct_url.json")) + list(sp.glob("*.egg-link")):
                if f.is_file() and _metin_degistir(f, [k for e in eski_kalip for k in (e, e.replace("\\", "/"), e.replace("\\", "\\\\"))], str(ROOT)):
                    n += 1
            if n:
                s["eylemler"].append(f"editable kurulum yolları güncellendi ({n} dosya)")
        kurgu_dir = ROOT / "kurgu"
        if kurgu_dir.is_dir():
            try:   # YSTCore eklentisi (idempotent): güncelleme yeni eklenti dosyaları getirmiş olabilir
                import importlib.util
                sp_ = importlib.util.spec_from_file_location("yst_kurgu_yama", SISTEM / "kurulum" / "kurgu_yama.py")
                km_ = importlib.util.module_from_spec(sp_)
                sp_.loader.exec_module(km_)
                ry = km_.otomatik(kurgu_dir)
                if ry["durum"] == "tamam" and ry.get("eklenen"):
                    s["eylemler"].append(f"Kurgu eklentisi uygulandı ({len(ry['eklenen'])} ek)")
                elif ry["durum"] == "uygulanamadi":   # hata değil: Kurgu düz haliyle çalışır, özellikler panelden
                    s["eylemler"].append("Kurgu eklentisi bu Kurgu sürümüne uygulanamadı; Kurgu düz haliyle çalışır (özellikler panelden): " + ry["neden"].splitlines()[0][:160])
            except Exception as e_:  # noqa: BLE001
                s["eylemler"].append("Kurgu eklentisi denetlenemedi (Kurgu etkilenmez): " + str(e_)[:160])
            r = _calistir([VENV_PY, "-m", "pip", "install", "-q", "--no-deps", "--no-build-isolation", "--disable-pip-version-check", "-e", str(kurgu_dir)], 240)
            if r.returncode == 0:
                s["eylemler"].append("kurgu komutları (kurgu.exe vb.) yeni yola göre yeniden üretildi")
            else:
                s["uyarilar"].append("kurgu başlatıcıları yenilenemedi (pip): " + (r.stderr or r.stdout or "")[-180:])
    # 2b) eski (klasör dışı) Hugging Face önbelleğindeki stüdyo modelleri klasöre kopyalanır: tek klasör kuralı (eskisi yerinde kalır; kaldir.py listeler)
    try:
        sys.path.insert(0, str(SISTEM / "araclar"))
        import yol as _yol_
        t_ = _yol_.hf_tasi()
        if t_:
            s["eylemler"].append(f"{len(t_)} model eski önbellekten stüdyo klasörüne kopyalandı")
    except Exception as e_:  # noqa: BLE001
        s["uyarilar"].append("eski modeller kopyalanamadı: " + str(e_)[:160])
    # 3) Kurgu ayarı (node_modules ve kurgu yolu mutlak)
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("yst_kurulum", SISTEM / "kurulum" / "kurulum.py")
        km = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(km)
        if (ORTAM / "kurgu-ayar").exists():
            km.a_config()
            s["eylemler"].append("Kurgu ayarı (kurgu-ayar/config.json) yeni yola göre yazıldı")
    except Exception as e:  # noqa: BLE001
        s["uyarilar"].append(f"Kurgu ayarı yazılamadı: {e}")
    # 4) eski oturum betikleri, proje/ayar dosyalarındaki eski kök
    n = 0
    for f in [*YEREL.glob("claude_*.cmd"), *YEREL.glob("claude_*.sh")]:
        f.unlink(missing_ok=True)
        n += 1
    if n:
        s["eylemler"].append(f"{n} eski Claude başlatma betiği silindi (her açılışta yeniden üretilir)")
    if yer_degisti:
        d = K.denetle(eski_kok, duzelt=True)
        if d["duzeltilen"]:
            s["eylemler"].append(f"{d['duzeltilen']} proje/ayar dosyasındaki eski klasör yolu güncellendi")
    # 5) veritabanı: bu bilgisayarın stüdyo kökü
    try:
        sys.path.insert(0, str(SISTEM / "arsiv"))
        import arsiv as A
        c = A.baglan()
        g = K.studyo_guncelle(c)
        c.close()
        s["eylemler"].append("veritabanında stüdyo klasörü yolu güncellendi")
        s["studyo"] = g
    except Exception as e:  # noqa: BLE001
        s["uyarilar"].append(f"veritabanı yolu yazılamadı: {e}")
    if not s["venv_yeniden_kur"]:
        K.damga_yaz({"onarim": time.strftime("%Y-%m-%d %H:%M:%S")})
    # günlük
    try:
        YEREL.mkdir(parents=True, exist_ok=True)
        with open(YEREL / "onarim.log", "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {eski_kok} → {ROOT}\n" + "".join(f"  + {e}\n" for e in s["eylemler"]) + "".join(f"  ! {u}\n" for u in s["uyarilar"]))
    except OSError:
        pass
    for e in s["eylemler"]:
        yazdir("  + " + e)
    for u in s["uyarilar"]:
        yazdir("  ! " + u)
    return s


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    r = onar(zorla="--zorla" in sys.argv)
    print(json.dumps(r, ensure_ascii=False, indent=1) if "--json" in sys.argv else ("onarım gerekmedi" if not r["degisti"] else "onarım bitti"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
