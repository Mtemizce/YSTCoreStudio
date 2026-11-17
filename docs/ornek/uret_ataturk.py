#!/usr/bin/env python3
"""Örnek video: kara kalemle çizilen portre, gerçeğe dönüşüm, dalgalanan bayrak, Gençliğe Hitabe ve özgün 1933 kaydı.

Bu betik, orkestratörün (Claude Code) bu örnek için yazdığı tek seferlik koddur: bir stüdyo özelliği DEĞİL, "videoyu kod olarak yazan ajan" yaklaşımının örneğidir.
HİÇBİR ŞEY İNTERNETTEN ALINMAZ: her girdi projenin `kaynak/` klasöründedir (kullanıcı panelde "Kaynaklar"a yükler):

  kaynak/foto/portre-1930.jpg                   portre
  kaynak/belge/turk-bayragi.svg                 bayrak (SVG yolları stüdyonun kendi ayrıştırıcısıyla çizilir)
  kaynak/belge/genclige-hitabe.md               anlatım metni (her boş olmayan satır bir cümle grubu)
  kaynak/ses/onuncu-yil-nutku-1933.ogg          özgün kayıt; --kayit-bas / --kayit-son saniyeleri arasındaki bölüm kullanılır (195,30-214,45 sn)

Kullanılan yerel araçlar: EMA Lightning (anlatım sesi), kalem_cizim.py (çizim girişi), ffmpeg, PyTorch (kareler GPU varsa GPU'da).
Stüdyoda YERLEŞİK OLMAYAN tek araç: portrenin arka planını ayırmak için `rembg` (pip install rembg onnxruntime). Kendi modelini ilk çalışmada bir kez indirir;
bunu istemiyorsan hazır bir kesim PNG'sini `hazir/ornek/kesim.png` olarak koy, betik onu kullanır.

  python docs/ornek/uret_ataturk.py projeler/genclige-hitabe [--kisa 6] [--kayit-bas 195.30 --kayit-son 214.45]

Altyazı: anlatım cümleleri (metin dosyasından) ve 1933 kaydındaki iki cümle (resmî metin) zamanlanıp videoya gömülür; ayrıca cikti/ana.srt yazılır.
Çıktı: projeler/<ad>/cikti/ana.mp4 + ana.srt (ara dosyalar hazir/ornek/ altında).
"""
from __future__ import annotations

import argparse
import math
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sistem" / "araclar"))
W, H, FPS, SR = 1920, 1080, 30, 48000


def kayit_oku(yol):
    import numpy as np
    with wave.open(str(yol)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def yaz_wav(yol, ses):
    import numpy as np
    with wave.open(str(yol), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(ses, -1, 1) * 32767).astype(np.int16).tobytes())


# ------------------------------------------------------------------------------------------------ hazırlık
def yildiz_mi(pts):
    """Kendini kesen 5 köşeli yıldız yolu (pentagram). SVG bunu 'sıfırdan farklı' kuralıyla doldurur, PIL çift-tek kuralıyla ortasını boş bırakır:
    bu yüzden 10 köşeli içi dolu yıldıza çevrilir. Yıldız değilse None."""
    if len(pts) >= 2 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) != 5:
        return None
    cx, cy = sum(x for x, _ in pts) / 5, sum(y for _, y in pts) / 5
    r = [math.hypot(x - cx, y - cy) for x, y in pts]
    if max(r) - min(r) > 0.02 * max(r):
        return None
    out = []
    ac = sorted(math.atan2(y - cy, x - cx) for x, y in pts)
    R = sum(r) / 5
    ic = R * math.sin(math.radians(18)) / math.sin(math.radians(126))      # düzgün yıldızın iç köşe yarıçapı
    for i, t in enumerate(ac):
        t2 = ac[(i + 1) % 5] + (2 * math.pi if i == 4 else 0)
        out.append((cx + R * math.cos(t), cy + R * math.sin(t)))
        out.append((cx + ic * math.cos((t + t2) / 2), cy + ic * math.sin((t + t2) / 2)))
    return out


def bayrak_png(svg_yol, hedef, w=3600, h=2400):
    """SVG'deki dolu yolları (kırmızı zemin, beyaz hilal ve yıldız) stüdyonun yol ayrıştırıcısıyla çokgene çevirip çizer."""
    from PIL import Image, ImageDraw
    import kalem_cizim as K
    svg = Path(svg_yol).read_text(encoding="utf-8")
    vb = [float(x) for x in re.search(r'viewBox="([^"]+)"', svg).group(1).split()]
    im = Image.new("RGB", (w, h), (0, 0, 0))
    d = ImageDraw.Draw(im)
    for m in re.finditer(r"<path\b([^>]*)>", svg):
        oz = m.group(1)
        fill = re.search(r'fill="(#[0-9a-fA-F]{3,6})"', oz)
        yol = re.search(r'\bd="([^"]+)"', oz)
        if not (fill and yol):
            continue
        for cizgi in K.yol_duzlestir(yol.group(1)):
            pts = [((x - vb[0]) / vb[2] * w, (y - vb[1]) / vb[3] * h) for x, y in cizgi]
            if len(pts) >= 3:
                d.polygon(yildiz_mi(pts) or pts, fill=fill.group(1))
    im.save(hedef)


def kesim_png(foto, hedef, en=1400):
    """Portrenin arka planını ayırır (rembg). Hazır `kesim.png` varsa onu kullanır."""
    if hedef.is_file():
        return
    try:
        from PIL import Image
        from rembg import new_session, remove
    except ImportError:
        sys.exit("rembg kurulu değil: `pip install rembg onnxruntime` ya da hazir/ornek/kesim.png dosyasını kendin koy.")
    im = Image.open(foto).convert("RGB")
    im = im.resize((en, round(im.height * en / im.width)), Image.LANCZOS)
    remove(im, session=new_session("isnet-general-use")).save(hedef)


def anlatim(metin_md, hedef_wav, ara):
    """Metindeki her satırı EMA Lightning ile (yerel, hız 0,9) okutup duraklarla birleştirir. (toplam sn, [(başlangıç sn, süre sn, metin)]) döndürür."""
    import numpy as np
    from ema_lightning import EMA
    satirlar = [s.strip() for s in Path(metin_md).read_text(encoding="utf-8").splitlines() if s.strip() and not s.startswith("#")]
    ema = EMA()
    parca, zaman, konum = [], [], 0
    for i, c in enumerate(satirlar):
        y = ara / f"h{i:02d}.wav"
        ema.say(c, path=str(y), speed=0.9, seed=7, sample_rate=SR)
        k = kayit_oku(y)
        zaman.append((konum / SR, len(k) / SR, c))
        parca.append(k)
        konum += len(k)
        if i < len(satirlar) - 1:
            parca.append(np.zeros(int(SR * 0.7), dtype=np.float32))
            konum += int(SR * 0.7)
    yaz_wav(hedef_wav, np.concatenate(parca))
    return sum(len(p) for p in parca) / SR, zaman


def altyazi_parcala(metin, en=62):
    """Uzun cümleyi virgül/noktalı virgül sınırlarında (olmazsa boşlukta) en çok `en` karakterlik parçalara böler."""
    kaba = [x.strip() for x in re.split(r"(?<=[,;:!?.])\s+", metin) if x.strip()]
    out, cur = [], ""
    for x in kaba:
        if cur and len(cur) + 1 + len(x) > en:
            out.append(cur)
            cur = x
        else:
            cur = f"{cur} {x}".strip()
    if cur:
        out.append(cur)
    son = []
    for x in out:      # hâlâ uzun olan tek parçayı boşluktan böl
        while len(x) > en + 14:
            k = x.rfind(" ", 0, en)
            son.append(x[:k])
            x = x[k + 1:]
        son.append(x)
    return son


def altyazilari_kur(zaman, hit_bas, kayit_bas_sn, kayit_satirlari):
    """Anlatım satırlarını karakter oranıyla parçalara paylaştırıp mutlak zamanlı altyazı listesi yapar; 1933 kaydı için verilen (kaynak başı, sonu, metin) satırları eklenir."""
    liste = []
    for bas, sure, metin in zaman:
        parcalar = altyazi_parcala(metin)
        toplam = sum(len(x) for x in parcalar)
        t = hit_bas + bas
        for x in parcalar:
            d = sure * len(x) / toplam
            liste.append((t, t + d - 0.05, x))
            t += d
    for k_bas, k_son, metin in kayit_satirlari:
        liste.append((kayit_bas_sn + k_bas, kayit_bas_sn + k_son, metin))
    return liste


def srt_yaz(yol, liste, kayma=0.0):
    def z(t):
        t = max(0.0, t + kayma)
        return f"{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d},{int(round((t % 1) * 1000)):03d}".replace(",1000", ",999")
    Path(yol).write_text("".join(f"{i}\n{z(b)} --> {z(e)}\n{m}\n\n" for i, (b, e, m) in enumerate(liste, 1)), encoding="utf-8")


# ------------------------------------------------------------------------------------------------ kareler
class Sahne:
    """Dalgalanan bayrak (dikey yer değiştirme + eğimden gölge) üstünde kesilmiş portre; vinyet, ince gren, başlık, yavaş yaklaşma, sonda kararma."""

    def __init__(self, bayrak, kesim, toplam, kapaklar, fontdir, altyazilar=()):
        import numpy as np
        import torch
        import torch.nn.functional as F
        from PIL import Image, ImageDraw, ImageFont
        from scipy import ndimage as ndi
        self.torch, self.F, self.np = torch, F, np
        self.toplam = toplam
        self.dev = "cuda" if torch.cuda.is_available() else "cpu"
        dev = self.dev
        self.FW, self.FH, self.FX0 = 2700, 1800, -520
        self.FY0 = (H - self.FH) // 2
        b = np.asarray(Image.open(bayrak).convert("RGB").resize((self.FW, self.FH), Image.LANCZOS), dtype=np.float32)
        self.bay = torch.from_numpy(b).permute(2, 0, 1)[None].to(dev)
        kes = Image.open(kesim).convert("RGBA")
        ph = 1210
        pw = round(kes.width * ph / kes.height)
        kes = kes.resize((pw, ph), Image.LANCZOS)
        a = np.asarray(kes)[:, :, 3].astype(np.float32) / 255
        a = np.clip(ndi.gaussian_filter(ndi.grey_erosion(a, size=(3, 3)), 0.8) * 1.04, 0, 1)     # kenardaki koyu haleyi azalt
        px0, py0 = 1015, H - ph + 70
        rgb = np.zeros((H, W, 3), dtype=np.float32)
        al = np.zeros((H, W, 1), dtype=np.float32)
        h0, h1, w1 = max(0, py0), min(H, py0 + ph), min(pw, W - px0)
        rgb[h0:h1, px0:px0 + w1] = np.asarray(kes)[h0 - py0:h1 - py0, :w1, :3]
        al[h0:h1, px0:px0 + w1, 0] = a[h0 - py0:h1 - py0, :w1]
        self.p_rgb = torch.from_numpy(rgb).permute(2, 0, 1)[None].to(dev)
        self.p_a = torch.from_numpy(al).permute(2, 0, 1)[None].to(dev)
        self.xs = torch.arange(W, device=dev, dtype=torch.float32)[None, :]
        self.ys = torch.arange(H, device=dev, dtype=torch.float32)[:, None]
        self.vin = (1 - 0.34 * (((self.xs - W / 2) / (W / 2)) ** 2 + ((self.ys - H / 2) / (H / 2)) ** 2))[None, None]
        g = torch.Generator(device=dev).manual_seed(3)
        self.gren = [torch.randn(1, 1, H, W, device=dev, generator=g) * 2.2 for _ in range(8)]
        self.kapaklar = []
        for satir1, satir2, bas, son in kapaklar:
            im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            dr = ImageDraw.Draw(im)
            f1 = ImageFont.truetype(str(fontdir / "CormorantGaramond-Bold.ttf"), 54)
            f2 = ImageFont.truetype(str(fontdir / "Inter-Regular.ttf"), 24)
            x, y = 90, 70                                       # başlık sol üstte: altta altyazı var
            dr.rectangle((x - 4, y - 8, x - 1, y + 98), fill=(255, 255, 255, 235))
            dr.text((x + 24, y), satir1, font=f1, fill=(255, 255, 255, 245), stroke_width=3, stroke_fill=(0, 0, 0, 200))
            dr.text((x + 24, y + 66), satir2, font=f2, fill=(240, 240, 240, 240), stroke_width=2, stroke_fill=(0, 0, 0, 200))
            t = torch.from_numpy(np.asarray(im, dtype=np.float32)).permute(2, 0, 1)[None].to(dev)
            self.kapaklar.append((t[:, :3], t[:, 3:4] / 255.0, bas, son))
        # altyazı: yalnızca alt bantta (dar kesit) önceden çizilir; her parça ortalanır, en çok 2 satır, koyu çerçeveli beyaz yazı
        self.bant = (H - 215, H - 55)
        fa = ImageFont.truetype(str(fontdir / "Inter-Medium.ttf"), 40)
        self.altyazilar = []
        for bas, son, metin in altyazilar:
            im = Image.new("RGBA", (W, self.bant[1] - self.bant[0]), (0, 0, 0, 0))
            dr = ImageDraw.Draw(im)
            satirlar = [metin] if len(metin) <= 46 else [metin[:metin.rfind(" ", 0, len(metin) // 2 + 10)], metin[metin.rfind(" ", 0, len(metin) // 2 + 10) + 1:]]
            y0 = (im.height - len(satirlar) * 52) // 2
            for j, sat in enumerate(satirlar):
                dr.text((W / 2, y0 + j * 52 + 26), sat, font=fa, fill=(255, 255, 255, 255), anchor="mm", stroke_width=4, stroke_fill=(0, 0, 0, 230))
            t = torch.from_numpy(np.asarray(im, dtype=np.float32)).permute(2, 0, 1)[None].to(dev)
            self.altyazilar.append((t[:, :3], t[:, 3:4] / 255.0, bas, son))

    def bayrak(self, t):
        torch, F = self.torch, self.F
        gen = min(1.0, t / 3.0)
        gen = gen * gen * (3 - 2 * gen)                       # genlik ilk 3 sn'de 0'dan artar: ilk kare düz = çizilen kare
        xf = (self.xs - self.FX0) / self.FW
        faz = 2 * math.pi * (xf * 2.1 - t * 0.55)
        faz2 = 2 * math.pi * (xf * 4.3 - t * 0.9) + 1.7
        yo = (self.ys - H / 2) / (H / 2)
        d = 46 * gen * (0.25 + xf) * (torch.sin(faz + 0.9 * yo) + 0.35 * torch.sin(faz2 + 0.5 * yo))
        dd = torch.zeros_like(d)
        dd[:, 1:-1] = (d[:, 2:] - d[:, :-2]) / 2
        golge = 1.0 + torch.clamp(dd * 4.4, -0.27, 0.27) * gen
        sy = self.ys - self.FY0 - d
        sx = (self.xs - self.FX0).expand(H, W)
        grid = torch.stack([sx / (self.FW - 1) * 2 - 1, sy / (self.FH - 1) * 2 - 1], dim=-1)[None]
        return F.grid_sample(self.bay, grid, mode="bilinear", padding_mode="border", align_corners=True) * golge[None, None]

    def kare(self, t, sayac=0, temiz=False):
        from PIL import Image
        torch, F = self.torch, self.F
        f = self.bayrak(t)
        f = f * (1 - self.p_a) + self.p_rgb * self.p_a
        if temiz:                                              # çizim kaynağı: vinyetsiz, grensiz, yazısız
            return Image.fromarray(f[0].clamp(0, 255).byte().permute(1, 2, 0).cpu().numpy())
        f = f * self.vin + self.gren[sayac % 8]
        for kr, ka, bas, son in self.kapaklar:
            al = max(0.0, min(1.0, (t - bas) / 0.8)) * max(0.0, min(1.0, (son - t) / 0.8))
            if al > 0:
                f = f * (1 - ka * al) + kr * ka * al
        for kr, ka, bas, son in self.altyazilar:                # altyazı (yaklaşmadan etkilenmesin diye kadraj hareketinden önce)
            al = max(0.0, min(1.0, (t - bas) / 0.12)) * max(0.0, min(1.0, (son - t) / 0.12))
            if al > 0:
                b0, b1 = self.bant
                f[:, :, b0:b1] = f[:, :, b0:b1] * (1 - ka * al) + kr * ka * al
        z = 1.0 + 0.055 * (t / self.toplam)                    # yavaş yaklaşma
        kar = max(0.0, min(1.0, (self.toplam - t) / 2.2))      # sonda kararma
        th = torch.tensor([[1 / z, 0, 0], [0, 1 / z, 0]], device=self.dev, dtype=torch.float32)[None]
        th[0, 1, 2] = (0.62 * 2 - 1) * (1 - 1 / z)
        g = F.affine_grid(th, f.shape, align_corners=False)
        f = F.grid_sample(f, g, mode="bilinear", padding_mode="border", align_corners=False) * kar
        return Image.fromarray(f[0].clamp(0, 255).byte().permute(1, 2, 0).cpu().numpy())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("proje", help="projeler/<ad>")
    ap.add_argument("--kayit-bas", type=float, default=195.30, help="1933 kaydından alınacak bölümün başı (sn)")
    ap.add_argument("--kayit-son", type=float, default=214.45, help="bölümün sonu (sn)")
    ap.add_argument("--kisa", type=float, help="yalnızca ilk N saniyeyi üret (deneme)")
    a = ap.parse_args()
    proje = Path(a.proje).resolve()
    kaynak, hazir = proje / "kaynak", proje / "hazir" / "ornek"
    hazir.mkdir(parents=True, exist_ok=True)
    (proje / "cikti").mkdir(exist_ok=True)

    def tek(klasor, desen):
        bul = sorted((kaynak / klasor).glob(desen))
        if not bul:
            sys.exit(f"kaynak eksik: {kaynak / klasor / desen}  (panelde Kaynaklar'a yükle)")
        return bul[0]
    foto, svg = tek("foto", "portre*.jpg"), tek("belge", "turk-bayragi.svg")
    metin, kayit = tek("belge", "genclige-hitabe.md"), tek("ses", "onuncu-yil-nutku-1933.ogg")

    bayrak_png(svg, hazir / "bayrak.png")
    kesim_png(foto, hazir / "kesim.png")
    hit_wav = hazir / "hitabe.wav"
    if hit_wav.is_file() and (hazir / "hitabe_zaman.json").is_file():
        import json
        hit_sure, zaman = len(kayit_oku(hit_wav)) / SR, [tuple(x) for x in json.loads((hazir / "hitabe_zaman.json").read_text(encoding="utf-8"))]
    else:
        import json
        hit_sure, zaman = anlatim(metin, hit_wav, hazir)
        (hazir / "hitabe_zaman.json").write_text(json.dumps(zaman, ensure_ascii=False), encoding="utf-8")
    ek_wav = hazir / "kayit_secilen.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a.kayit_bas}", "-to", f"{a.kayit_son}", "-i", str(kayit), "-af",
                    "highpass=f=90,lowpass=f=6500,afftdn=nf=-30,loudnorm=I=-17:TP=-1.5:LRA=7,aresample=48000", "-ac", "1", str(ek_wav)], check=True)
    ek = kayit_oku(ek_wav)

    import numpy as np
    bas = 1.0
    hit_bas, hit_bit = bas, bas + hit_sure
    ek_bas = hit_bit + 1.6
    ek_bit = ek_bas + len(ek) / SR
    toplam = ek_bit + 2.4
    ses = np.zeros(int(toplam * SR), dtype=np.float32)
    h = kayit_oku(hit_wav)
    ses[int(hit_bas * SR):int(hit_bas * SR) + len(h)] += h * 0.95
    ses[int(ek_bas * SR):int(ek_bas * SR) + len(ek)] += ek * 0.95
    yaz_wav(hazir / "ses.wav", ses)

    # 1933 kaydındaki iki cümle: (kaynak kaydındaki başlangıç, bitiş sn) sessizlik sınırlarından ölçüldü; metin Onuncu Yıl Nutku'nun resmî metnidir
    kayit_satirlari = [(max(0.0, 195.66 - a.kayit_bas), 200.47 - a.kayit_bas, "Türk milleti çalışkandır, Türk milleti zekidir."),
                       (204.39 - a.kayit_bas, 214.44 - a.kayit_bas, "Çünkü, Türk milleti, millî birlik ve beraberlikle güçlükleri yenmesini bilmiştir.")]
    altyazilar = altyazilari_kur(zaman, hit_bas, ek_bas, kayit_satirlari)
    srt_yaz(hazir / "altyazi_klip.srt", altyazilar)
    sahne = Sahne(hazir / "bayrak.png", hazir / "kesim.png", toplam,
                  [("Gençliğe Hitabe · 1927", "Yapay zekâ ile seslendirildi (yerel Türkçe TTS)", hit_bas + 1.0, hit_bas + 9.0),
                   ("Onuncu Yıl Nutku · 29 Ekim 1933", "Özgün ses kaydı (kamu malı)", ek_bas - 0.3, ek_bas + 8.0)], ROOT / "sistem" / "kit" / "fonts", altyazilar)
    sahne.kare(0.0, 0, True).save(hazir / "cizim_kaynagi.png")
    sn = min(a.kisa, toplam) if a.kisa else toplam
    n = int(round(sn * FPS))
    klip = hazir / "klip.mp4"
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(hazir / "ses.wav"),
                          "-t", f"{n / FPS:.3f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", "-c:a", "aac", "-b:a", "192k",
                          "-af", f"afade=t=out:st={toplam - 2.2:.2f}:d=2.2", str(klip)], stdin=subprocess.PIPE)
    for i in range(n):
        p.stdin.write(sahne.kare(i / FPS, i).tobytes())
    p.stdin.close()
    p.wait()

    ara = hazir / "giris_ve_klip.mp4"
    subprocess.run([sys.executable, str(ROOT / "sistem" / "araclar" / "kalem_cizim.py"), str(klip), "-o", str(ara), "--stil", "karakalem", "--zemin", "#EFEBE0", "--sure", "11",
                    "--bekle", "2", "--detay", "0.5", "--tarama", "0.8", "--cizim-kaynagi", str(hazir / "cizim_kaynagi.png")], check=True)
    cikti = proje / "cikti" / "ana.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(ara), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:v", "libx264", "-preset", "slow", "-crf", "22", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(cikti)], check=True)
    giris_sn = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(ara)], capture_output=True, text=True).stdout) \
        - float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(klip)], capture_output=True, text=True).stdout)
    srt_yaz(proje / "cikti" / "ana.srt", altyazilar, kayma=giris_sn)      # videoda gömülü altyazının ayrı .srt kopyası (giriş süresi kadar kaydırılmış)
    print("hazır:", cikti, "ve ana.srt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
