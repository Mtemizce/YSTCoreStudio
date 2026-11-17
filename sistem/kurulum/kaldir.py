#!/usr/bin/env python3
"""Stüdyoyu bilgisayardan kaldırma yardımcısı: neyin nerede olduğunu gösterir, istersen klasör DIŞINDA kalmış stüdyo artıklarını siler.

  python sistem/kurulum/kaldir.py              yalnızca listeler (hiçbir şey silmez)
  python sistem/kurulum/kaldir.py --sil        stüdyoya ÖZGÜ klasör dışı artıkları siler (her biri için sorar; --evet sormadan)

KURAL: stüdyonun indirdiği her şey kendi klasöründedir (sistem/ortam, node_modules, projeler, kimlik...). Tamamen kaldırmak için paneli kapatıp
klasörü silmek yeter. Aşağıdaki "klasör dışı" konumlar yalnızca ŞUNLAR içindir:
  - eski sürümlerle ya da stüdyo dışında (kendi terminalinde) çalıştırılan araçlarla oluşmuş artıklar (ör. modellerin ortak Hugging Face önbelleğine inmiş olması),
  - HyperFrames gibi üçüncü taraf araçların sabit kodlu önbellekleri (stüdyo bunları klasörüne yönlendirir; yönlendirilemeyenler burada listelenir).
Bu betik stüdyo klasörünün KENDİSİNİ silmez, Python/Node/Git/Claude Code gibi senin kurduğun programlara ve pip/npm ortak önbelleklerine dokunmaz.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# (id, açıklama, yol, tür): tür "ozgu" = yalnızca stüdyo kullanır, --sil siler · "paylasilan" = başka programlar da kullanabilir: yalnızca listelenir
def konumlar(ev: Path, yerel: Path | None) -> list[tuple[str, str, Path, str]]:
    hf = ev / ".cache" / "huggingface" / "hub"
    k: list[tuple[str, str, Path, str]] = [
        ("hf-pocket", "Pocket TTS Turkish modeli (eski ortak önbellekte)", hf / "models--wite-tech--pocket-tts-turkish", "ozgu"),
        ("hf-whisper", "faster-whisper small modeli (eski ortak önbellekte)", hf / "models--Systran--faster-whisper-small", "ozgu"),
        ("hf-ema", "EMA Lightning modeli (eski ortak önbellekte)", hf / "models--canberkkkkkk--ema-lightning", "ozgu"),
        ("hyperframes", "HyperFrames Chrome önbelleği (aracın sabit kodlu yolu)", ev / ".cache" / "hyperframes", "ozgu"),
        ("ema-onbellek", "EMA parti boyutu önbelleği", ev / ".cache" / "ema_lightning", "ozgu"),
        ("ezdxf", "ezdxf yazı tipi önbelleği (DWG/DXF)", ev / ".cache" / "ezdxf", "paylasilan"),
        ("hf-diger", "Hugging Face ortak önbelleği (başka modeller de olabilir)", ev / ".cache" / "huggingface", "paylasilan"),
    ]
    if yerel:
        k.append(("kurgu-veri", "Kurgu verisi (ffmpeg, modeller): stüdyo dışında çalıştırılan `kurgu` komutundan; Kurgu'yu ayrıca kendi başına kullanıyorsan paylaşılır", yerel / "Kurgu", "paylasilan"))
    return k


def boyut(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    t = 0
    for d, _ds, fs in os.walk(p):
        for f in fs:
            try:
                t += os.path.getsize(os.path.join(d, f))
            except OSError:
                pass
    return t


def tara(ev: Path | None = None, yerel: Path | None = None) -> list[dict]:
    ev = ev or Path.home()
    if yerel is None and os.environ.get("LOCALAPPDATA"):
        yerel = Path(os.environ["LOCALAPPDATA"])
    out = []
    for kid, ac, yol, tur in konumlar(ev, yerel):
        if yol.exists():
            out.append({"id": kid, "aciklama": ac, "yol": str(yol), "boyut": boyut(yol), "tur": tur})
    # hf-diger paylaşılan üst klasör: özgü olanlar silindikten sonra kalanı gösterir; çifte saymamak için özgüleri düş
    return out


def sil(ogeler: list[dict], sor=input) -> list[str]:
    silinen = []
    for o in ogeler:
        if o["tur"] != "ozgu":
            continue
        if sor is not None and sor(f"Silinsin mi? {o['yol']} ({o['boyut'] / 1e6:.0f} MB) [e/H] ").strip().lower() not in ("e", "evet", "y", "yes"):
            continue
        p = Path(o["yol"])
        try:
            shutil.rmtree(p) if p.is_dir() else p.unlink()
            silinen.append(o["yol"])
        except OSError as e:
            print(f"  silinemedi: {p} ({e})")
    return silinen


def calisiyor_mu() -> bool:
    try:
        import json
        import socket
        d = json.loads((ROOT / "sistem" / "ortam" / "yerel" / "panel.json").read_text(encoding="utf-8"))
        with socket.socket() as s:
            s.settimeout(0.3)
            return s.connect_ex(("127.0.0.1", int(d.get("port", 0)))) == 0
    except Exception:  # noqa: BLE001
        return False


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ic = sum(boyut(ROOT / x) for x in ("sistem/ortam", "node_modules", "kurgu") if (ROOT / x).exists())
    print(f"Stüdyo klasörü: {ROOT}")
    print(f"  kurulumun getirdikleri (silinince geri gelir, hepsi bu klasörde): ≈{ic / 1e9:.2f} GB  (sistem/ortam, node_modules, kurgu)")
    print("  Tamamen kaldırmak için: paneli kapat (Başlat.cmd durdur) ve bu klasörü sil. Projelerin ve kimliğin (projeler/, kimlik/) de bu klasörde olduğunu unutma: yedeğini al.\n")
    if calisiyor_mu():
        print("  UYARI: panel çalışıyor; silmeden önce kapat (Başlat.cmd durdur ya da panelde Kapat).\n")
    ogeler = tara()
    ozgu = [o for o in ogeler if o["tur"] == "ozgu"]
    if not ogeler:
        print("Klasör dışında stüdyoya ait bir artık bulunamadı: her şey klasörün içinde.")
        return 0
    print("Klasör DIŞINDA bulunanlar:")
    for o in ogeler:
        etiket = "stüdyoya özgü" if o["tur"] == "ozgu" else "başka programlarla paylaşılabilir (dokunulmaz)"
        print(f"  [{etiket}] {o['aciklama']}\n      {o['yol']}  ({o['boyut'] / 1e6:.0f} MB)")
    if "--sil" not in sys.argv:
        print(f"\nStüdyoya özgü olanları silmek için: python sistem/kurulum/kaldir.py --sil   ({len(ozgu)} öğe, her biri için sorulur; --evet sormaz)")
        return 0
    s = sil(ozgu, None if "--evet" in sys.argv else input)
    print(f"\n{len(s)} öğe silindi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
