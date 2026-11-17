#!/usr/bin/env python3
"""Mekân gezisi (kodla, üretken model yok): GERÇEK mekân fotoğraflarından "içeride geziyormuş" hissi veren kamera hareketi (derinlikli parallax),
isteğe bağlı sunucu penceresi (kişi videosu/fotoğrafı köşede) ve "dijital sunum" etiketi. Düşük donanımda çalışır (numpy + ffmpeg).
B planının yerel katmanıdır: kişi çekime gidemediğinde mekân görüntüleri GERÇEK kalır, sunucu pencere olarak eklenir.

  python sistem/araclar/mekan_gezisi.py derinlik <foto> [-o derinlik.png] [--sahte]
  python sistem/araclar/mekan_gezisi.py klip <foto> -o klip.mp4 [--sure 5] [--hareket ileri|sol|sag|yukari] [--dikey] [--sahte-derinlik]
  python sistem/araclar/mekan_gezisi.py gezi <foto1> <foto2> ... -o gezi.mp4 [--sure 4] [--dikey] [--ses ses.wav] [--sunucu kisi.mp4|kisi.png] [--etiket "Dijital sunum"] [--sahte-derinlik]

Derinlik: Depth Anything V2 SMALL (Apache-2.0; model kartı) 'transformers' ile; ağırlık ilk kullanımda indirilir (~100 MB) ve sistem/ortam/modeller/hf altında durur.
transformers kurulu değilse ya da --sahte-derinlik verilirse yaklaşık derinlik kullanılır (alt = yakın, üst = uzak; iç mekân fotoğrafları için makul bir varsayım, daha az inandırıcı).
Hareket gerçek 3B değildir: kısa mesafeli (5 sn) bir kamera kayması/ilerlemesi; fotoğrafta olmayan şey uydurulmaz.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NW = 0x08000000 if os.name == "nt" else 0
MODEL = "depth-anything/Depth-Anything-V2-Small-hf"
_boru = {}


def ffmpeg() -> str:
    from shutil import which
    f = which("ffmpeg")
    if not f:
        raise RuntimeError("ffmpeg bulunamadı (kurulum Kurgu'nun kendi indiricisiyle getirir)")
    return f


# ------------------------------------------------------------------ derinlik
def sahte_derinlik(w: int, h: int):
    """Model yokken: alt = yakın (1), üst = uzak (0); ortada hafif odak. Yaklaşık, ama parallax'a yön verir."""
    import numpy as np
    y = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    x = np.linspace(-1.0, 1.0, w, dtype=np.float32)[None, :]
    d = 0.15 + 0.7 * y + 0.15 * (1 - np.abs(x))
    return np.clip(d, 0, 1)


def derinlik_modeli_var() -> bool:
    import importlib.util
    return importlib.util.find_spec("transformers") is not None and importlib.util.find_spec("torch") is not None


def derinlik(foto: str | Path, cikti: str | Path | None = None, sahte: bool = False):
    """Fotoğraf için derinlik haritası (float32 0..1, 1 = yakın). cikti verilirse 8 bit PNG olarak yazılır."""
    import numpy as np
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(foto)).convert("RGB")
    if sahte or not derinlik_modeli_var():
        d = sahte_derinlik(*im.size)
        kaynak = "yaklaşık"
    else:
        os.environ.setdefault("HF_HOME", str(ROOT / "sistem" / "ortam" / "modeller" / "hf"))
        os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
        if "boru" not in _boru:
            import torch
            from transformers import pipeline
            _boru["boru"] = pipeline("depth-estimation", model=MODEL, device=0 if torch.cuda.is_available() else -1)
        kucuk = im.copy()
        kucuk.thumbnail((1024, 1024))
        r = _boru["boru"](kucuk)["depth"]  # PIL, büyük = yakın (göreli)
        d = np.asarray(r.resize(im.size, Image.BICUBIC), dtype=np.float32)
        d = (d - d.min()) / max(1e-6, float(d.max() - d.min()))
        kaynak = "Depth Anything V2 Small"
    if cikti:
        Image.fromarray((d * 255).astype("uint8")).save(cikti)
    return d, kaynak


# ------------------------------------------------------------------ parallax klip
def _ease(t: float) -> float:
    return t * t * (3 - 2 * t)


def _ornekle(src, xs, ys):
    """Çift doğrusal örnekleme (numpy). src: HxWx3 float32; xs, ys: çıktı boyutunda kaynak koordinatları."""
    import numpy as np
    h, w = src.shape[:2]
    xs = np.clip(xs, 0, w - 1.001)
    ys = np.clip(ys, 0, h - 1.001)
    x0, y0 = xs.astype(np.int32), ys.astype(np.int32)
    fx, fy = (xs - x0)[..., None], (ys - y0)[..., None]
    a = src[y0, x0] * (1 - fx) + src[y0, x0 + 1] * fx
    b = src[y0 + 1, x0] * (1 - fx) + src[y0 + 1, x0 + 1] * fx
    return a * (1 - fy) + b * fy


def klip(foto: str | Path, cikti: str | Path, sure: float = 5.0, fps: int = 30, boyut: tuple[int, int] = (1920, 1080), hareket: str = "ileri",
         genlik: float = 0.03, sahte: bool = False, derinlik_png: str | Path | None = None, yazdir=print) -> dict:
    """Tek fotoğraftan derinlikli kamera hareketi (mp4, ses yok). hareket: ileri | sol | sag | yukari."""
    import numpy as np
    from PIL import Image, ImageOps
    W, H = boyut
    im = ImageOps.exif_transpose(Image.open(foto)).convert("RGB")
    if derinlik_png and Path(derinlik_png).is_file():
        d = np.asarray(Image.open(derinlik_png).convert("L"), dtype=np.float32) / 255.0
        d = np.asarray(Image.fromarray((d * 255).astype("uint8")).resize(im.size, Image.BICUBIC), dtype=np.float32) / 255.0
        kaynak = "dosyadan"
    else:
        d, kaynak = derinlik(foto, None, sahte)
    # hedef orana kırp (merkezden), sonra hareket payı için biraz büyüt
    oran = W / H
    if im.width / im.height > oran:
        nw = int(im.height * oran)
        kutu = ((im.width - nw) // 2, 0, (im.width - nw) // 2 + nw, im.height)
    else:
        nh = int(im.width / oran)
        kutu = (0, (im.height - nh) // 2, im.width, (im.height - nh) // 2 + nh)
    im = im.crop(kutu)
    d = np.asarray(Image.fromarray((d * 255).astype("uint8")).crop(kutu).resize(im.size, Image.BICUBIC), dtype=np.float32) / 255.0
    pay = 1.25  # kaynak, çıktıdan geniş çözünürlükte tutulur (hareket bilinear örneklenir)
    sw, sh = int(W * pay), int(H * pay)
    src = np.asarray(im.resize((sw, sh), Image.LANCZOS), dtype=np.float32)
    dep = np.asarray(Image.fromarray((d * 255).astype("uint8")).resize((W, H), Image.BICUBIC), dtype=np.float32) / 255.0
    gx, gy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    cx, cy = W / 2.0, H / 2.0
    n = max(2, int(sure * fps))
    cmd = [ffmpeg(), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
           "-preset", "veryfast", str(cikti)]
    Path(cikti).parent.mkdir(parents=True, exist_ok=True)
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, creationflags=NW)
    ofs = (pay - 1) / 2 * W, (pay - 1) / 2 * H  # kaynakta çıktı penceresinin başlangıcı
    for i in range(n):
        t = _ease(i / (n - 1))
        yakin = dep - 0.5  # -0.5 uzak .. +0.5 yakın
        if hareket == "ileri":  # kameranın ilerlemesi: yakın nesneler daha çok büyür
            olcek = 1.0 + t * (0.10 + 0.22 * (dep ** 1.2))
            sx = cx + (gx - cx) / olcek
            sy = cy + (gy - cy) / olcek
        else:
            kay = t * genlik * W
            yon = {"sol": 1.0, "sag": -1.0}.get(hareket, 0.0)
            sx = gx + yon * kay * (yakin * 2.0) + 0.0
            sy = gy + (kay * (yakin * 2.0) if hareket == "yukari" else 0.0)
            olcek = 1.0 + 0.04 * t  # kenar boşluğunu gizleyen hafif yakınlaşma
            sx = cx + (sx - cx) / olcek
            sy = cy + (sy - cy) / olcek
        kare = _ornekle(src, (sx * pay) , (sy * pay))
        p.stdin.write(np.clip(kare, 0, 255).astype("uint8").tobytes())
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError("ffmpeg kodlaması başarısız")
    yazdir(f"klip tamam: {cikti} ({n} kare, derinlik: {kaynak})")
    return {"dosya": str(cikti), "kare": n, "derinlik": kaynak, "hareket": hareket}


# ------------------------------------------------------------------ birleştirme, sunucu penceresi, etiket
def _calistir(cmd: list) -> None:
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=NW)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg: " + (r.stderr or "")[-400:])


def _sure(dosya: str | Path) -> float:
    from shutil import which
    r = subprocess.run([which("ffprobe") or "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(dosya)], capture_output=True, text=True, creationflags=NW)
    return float(r.stdout.strip() or 0)


def birlestir(klipler: list[str], cikti: str, gecis: float = 0.5, fps: int = 30) -> str:
    """Klipleri çapraz geçişle (xfade) tek videoya birleştirir."""
    if len(klipler) == 1:
        Path(cikti).write_bytes(Path(klipler[0]).read_bytes())
        return cikti
    sureler = [_sure(k) for k in klipler]
    girdi, filt, onceki, ofset = [], [], "[0:v]", 0.0
    for i, k in enumerate(klipler):
        girdi += ["-i", k]
    for i in range(1, len(klipler)):
        ofset += sureler[i - 1] - gecis
        son = f"[v{i}]"
        filt.append(f"{onceki}[{i}:v]xfade=transition=fade:duration={gecis}:offset={ofset:.3f}{son}")
        onceki = son
    _calistir([ffmpeg(), "-v", "error", "-y", *girdi, "-filter_complex", ";".join(filt), "-map", onceki, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-r", str(fps), cikti])
    return cikti


def _yuvarlak_maske(w: int, h: int, yaricap: int, yol: Path) -> None:
    from PIL import Image, ImageDraw
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], radius=yaricap, fill=255)
    m.save(yol)


def sunucu_penceresi(arka: str, sunucu: str, cikti: str, konum: str = "sag-alt", genislik: float = 0.26, ses: str | None = None, boyut: tuple[int, int] = (1920, 1080)) -> str:
    """Kişi videosu/fotoğrafını köşeye yuvarlak köşeli pencere olarak koyar; ses verilirse arka videonun sesi o olur (süre arka videoya göre kırpılır)."""
    W, H = boyut
    pw = int(W * genislik) // 2 * 2
    kisi_foto = Path(sunucu).suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
    ph = int(pw * (4 / 3 if H > W else 3 / 4)) // 2 * 2 if kisi_foto else int(pw * 9 / 16) // 2 * 2
    kenar = int(W * 0.03)
    x = kenar if "sol" in konum else W - pw - kenar
    y = kenar if "ust" in konum else H - ph - kenar - (int(H * 0.04) if H > W else 0)
    with tempfile.TemporaryDirectory() as td:
        maske = Path(td) / "m.png"
        _yuvarlak_maske(pw, ph, max(12, pw // 12), maske)
        girdi = ["-i", arka] + (["-loop", "1"] if kisi_foto else []) + ["-i", sunucu, "-i", str(maske)]
        if ses:
            girdi += ["-i", ses]
        filt = (f"[1:v]scale={pw}:{ph}:force_original_aspect_ratio=increase,crop={pw}:{ph},format=rgba[p];[2:v]scale={pw}:{ph},format=gray[m];"
                f"[p][m]alphamerge[pa];[0:v][pa]overlay={x}:{y}:shortest=1[v]")
        harita = ["-map", "[v]"] + (["-map", "3:a"] if ses else (["-map", "1:a?"] if not kisi_foto else []))
        _calistir([ffmpeg(), "-v", "error", "-y", *girdi, "-filter_complex", filt, *harita, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "aac", "-shortest", cikti])
    return cikti


def etiket_ekle(video: str, cikti: str, metin: str = "Dijital sunum", boyut: tuple[int, int] = (1920, 1080)) -> str:
    """Köşeye küçük, okunur bir etiket (örn. 'Dijital sunum · yapay zekâ ile oluşturuldu'). Kullanıcı seçer; varsayılan eklenmez."""
    from PIL import Image, ImageDraw, ImageFont
    W, H = boyut
    punto = max(18, int(H * 0.022))
    font = None
    for ad in ("sistem/kit/fonts/Inter-Medium.ttf", "sistem/kit/fonts/Inter-SemiBold.ttf"):
        if (ROOT / ad).is_file():
            font = ImageFont.truetype(str(ROOT / ad), punto)
            break
    if font is None:
        for ad in ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
            if Path(ad).is_file():
                font = ImageFont.truetype(ad, punto)
                break
    font = font or ImageFont.load_default()
    kutu = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textbbox((0, 0), metin, font=font)
    tw, th = kutu[2] - kutu[0], kutu[3] - kutu[1]
    pad = int(punto * 0.6)
    img = Image.new("RGBA", (tw + 2 * pad, th + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, img.width - 1, img.height - 1], radius=pad, fill=(0, 0, 0, 150))
    d.text((pad - kutu[0], pad - kutu[1]), metin, font=font, fill=(255, 255, 255, 235))
    with tempfile.TemporaryDirectory() as td:
        png = Path(td) / "e.png"
        img.save(png)
        _calistir([ffmpeg(), "-v", "error", "-y", "-i", video, "-i", str(png), "-filter_complex", f"[0:v][1:v]overlay={int(W * 0.03)}:{int(H * 0.03)}[v]", "-map", "[v]", "-map", "0:a?",
                   "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "copy", cikti])
    return cikti


def gezi(fotolar: list[str], cikti: str, sure: float = 4.0, dikey: bool = False, ses: str | None = None, sunucu: str | None = None, etiket: str | None = None,
         sahte: bool = False, fps: int = 30, yazdir=print) -> dict:
    """Fotoğraf dizisinden tek mekân gezisi videosu. Hareketler dönüşümlü (ileri, sol, ileri, sag…) olur."""
    boyut = (1080, 1920) if dikey else (1920, 1080)
    hareketler = ["ileri", "sol", "ileri", "sag", "yukari"]
    with tempfile.TemporaryDirectory() as td:
        klipler = []
        for i, f in enumerate(fotolar):
            k = str(Path(td) / f"k{i}.mp4")
            klip(f, k, sure, fps, boyut, hareketler[i % len(hareketler)], sahte=sahte, yazdir=yazdir)
            klipler.append(k)
        mevcut = str(Path(td) / "birlesik.mp4")
        birlestir(klipler, mevcut, 0.5, fps)
        if sunucu:
            ara = str(Path(td) / "sunuculu.mp4")
            sunucu_penceresi(mevcut, sunucu, ara, boyut=boyut)
            mevcut = ara
        if etiket:
            ara = str(Path(td) / "etiketli.mp4")
            etiket_ekle(mevcut, ara, etiket, boyut)
            mevcut = ara
        if ses:  # anlatım sesi: görüntü sesin süresine göre değil, kısa olan bitince biter
            ara = str(Path(td) / "sesli.mp4")
            _calistir([ffmpeg(), "-v", "error", "-y", "-i", mevcut, "-i", ses, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-shortest", ara])
            mevcut = ara
        Path(cikti).parent.mkdir(parents=True, exist_ok=True)
        Path(cikti).write_bytes(Path(mevcut).read_bytes())
    return {"dosya": str(cikti), "fotograf": len(fotolar), "sure": round(_sure(cikti), 1), "dikey": dikey, "sunucu": bool(sunucu), "etiket": etiket}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="k", required=True)
    d = sp.add_parser("derinlik")
    d.add_argument("foto")
    d.add_argument("-o", "--cikti")
    d.add_argument("--sahte", action="store_true")
    k = sp.add_parser("klip")
    k.add_argument("foto")
    k.add_argument("-o", "--cikti", required=True)
    k.add_argument("--sure", type=float, default=5.0)
    k.add_argument("--hareket", default="ileri", choices=["ileri", "sol", "sag", "yukari"])
    k.add_argument("--dikey", action="store_true")
    k.add_argument("--sahte-derinlik", action="store_true")
    g = sp.add_parser("gezi")
    g.add_argument("fotolar", nargs="+")
    g.add_argument("-o", "--cikti", required=True)
    g.add_argument("--sure", type=float, default=4.0)
    g.add_argument("--dikey", action="store_true")
    g.add_argument("--ses")
    g.add_argument("--sunucu")
    g.add_argument("--etiket")
    g.add_argument("--sahte-derinlik", action="store_true")
    a = ap.parse_args()
    try:
        if a.k == "derinlik":
            _, kay = derinlik(a.foto, a.cikti, a.sahte)
            print(f"derinlik: {kay}" + (f" → {a.cikti}" if a.cikti else ""))
        elif a.k == "klip":
            print(klip(a.foto, a.cikti, a.sure, 30, (1080, 1920) if a.dikey else (1920, 1080), a.hareket, sahte=a.sahte_derinlik))
        else:
            print(gezi(a.fotolar, a.cikti, a.sure, a.dikey, a.ses, a.sunucu, a.etiket, a.sahte_derinlik))
    except (RuntimeError, OSError) as e:
        print("HATA:", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
