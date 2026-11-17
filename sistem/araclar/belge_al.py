"""Belge alımı: DWG / Word (.docx) / Excel (.xlsx) → video için kullanılabilir dosyalar. Tamamen yerel.

Kullanım:
  python sistem/araclar/belge_al.py <dosya veya klasör> -o <proje>/media/belge

Çıktı:
  .dwg  → <ad>_koyu.png, <ad>_acik.png (çizim görseli; marka koyu zemin/altın çizgi ve beyaz zemin)
  .docx → <ad>.md (başlıklar + paragraflar + tablolar) ve <ad>_gorseller/ (içindeki resimler)
  .xlsx → <ad>__<sayfa>.csv ve <ad>.md (ilk satırlar önizleme)
  .pdf  → <ad>_s01.png … (ilk 24 sayfa görseli) ve <ad>.md (sayfa sayfa metin; taranmış PDF'te metin boş olur → not düşülür)
  diğer → atlanır ve nedeni yazılır (foto/video zaten medya_envanteri.py ile alınır)
Her şey sonunda  belgeler.md  dosyasında özetlenir (senarist ajan bunu okur).

Bağımlılık: Python standart kütüphanesi + (PDF için) pypdfium2/pypdf (.venv'de kurulu) + (DWG için) araclar/dis/libredwg (GPL, yerel) + node `sharp` (node_modules).
Not: DWG çizimi "tahmini" bir görseldir: ölçü/ölçek iddiası için orijinal çizim esastır.
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
STUDIO = HERE.parents[1]   # depo kökü (sistem/araclar → kök)
DWG2SVG = HERE / "dis" / "libredwg" / "dwg2SVG.exe"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def guvenli_ad(p: Path) -> str:
    return re.sub(r"[^\w\-]+", "_", p.stem, flags=re.UNICODE).strip("_")[:60] or "belge"


# ----------------------------------------------------------------- DWG
def dwg_al(p: Path, cikti: Path) -> list[str]:
    if not DWG2SVG.exists():
        return [f"ATLANDI {p.name}: {DWG2SVG} yok"]
    ad = guvenli_ad(p)
    r = subprocess.run([str(DWG2SVG), str(p)], capture_output=True, timeout=180)
    svg = r.stdout.decode("utf-8", "replace")
    yollar = re.findall(r'<path id="dwg-object-\d+" d="([^"]+)"', svg)
    if not yollar:
        return [f"ATLANDI {p.name}: dwg2SVG çizim nesnesi üretmedi (bazı DWG sürümleri desteklenmez)"]
    sayilar = [(float(a), float(b)) for d in yollar for a, b in re.findall(r"(-?\d+\.?\d*),(-?\d+\.?\d*)", d)]
    xs = sorted(n[0] for n in sayilar)
    ys = sorted(n[1] for n in sayilar)

    def yuzde(a, q):
        return a[min(len(a) - 1, max(0, int(len(a) * q)))]

    # uç değerler (kaçak nesneler) görünümü bozar: %1-%99 aralığı
    x0, x1, y0, y1 = yuzde(xs, .01), yuzde(xs, .99), yuzde(ys, .01), yuzde(ys, .99)
    px, py = (x1 - x0) * .04, (y1 - y0) * .04
    x0, x1, y0, y1 = x0 - px, x1 + px, y0 - py, y1 + py
    w, h = x1 - x0, y1 - y0
    # yoğun bölge: izole nokta/kaçak nesneleri at, planların bulunduğu kutuya yakınlaş
    G = 48
    hucre: dict[tuple[int, int], int] = {}
    for a, b in sayilar:
        k = (min(G - 1, max(0, int((a - x0) / w * G))), min(G - 1, max(0, int((b - y0) / h * G))))
        hucre[k] = hucre.get(k, 0) + 1
    # bitişik dolu hücreleri kümele (2 hücre boşluk köprülenir), en çok nokta taşıyan kümeye yakınlaş
    esik = max(hucre.values()) * 0.02
    dolu = {k for k, v in hucre.items() if v >= esik}
    kalan, kumeler = set(dolu), []
    while kalan:
        bas = kalan.pop()
        kume, sira = {bas}, [bas]
        while sira:
            ci, cj = sira.pop()
            for di in range(-2, 3):
                for dj in range(-2, 3):
                    n = (ci + di, cj + dj)
                    if n in kalan:
                        kalan.discard(n)
                        kume.add(n)
                        sira.append(n)
        kumeler.append(kume)
    gorunumler = [("tum", x0, x1, y0, y1)]
    if kumeler:
        en = max(kumeler, key=lambda c: sum(hucre[k] for k in c))
        cx0 = x0 + min(k[0] for k in en) / G * w
        cx1 = x0 + (max(k[0] for k in en) + 1) / G * w
        cy0 = y0 + min(k[1] for k in en) / G * h
        cy1 = y0 + (max(k[1] for k in en) + 1) / G * h
        mx, my = (cx1 - cx0) * .05, (cy1 - cy0) * .05
        if (cx1 - cx0) < w * 0.85 or (cy1 - cy0) < h * 0.85:
            gorunumler.append(("yakin", cx0 - mx, cx1 + mx, cy0 - my, cy1 + my))
    cikti.mkdir(parents=True, exist_ok=True)
    satirlar = []
    for gad, gx0, gx1, gy0, gy1 in gorunumler:
      gw, gh = gx1 - gx0, gy1 - gy0
      kalinlik = max(gw, gh) / 1400.0
      for ek0, bg, fg in (("koyu", "#0e1013", "#e6cc86"), ("acik", "#ffffff", "#222222")):
        ek = ek0 if gad == "tum" else f"yakin_{ek0}"
        # Siyah/beyaz çizgiler tema rengine; renkli (katman) çizgiler olduğu gibi. Yeni LibreDWG 'non-scaling-stroke' yazar
        # ama rasterleştirici bunu uygulamaz: kalınlık çizim ölçeğine göre (kullanıcı birimi) verilir.
        kalin = f"{kalinlik:.3f}"
        govde = re.sub(r"stroke:(?:black|white|#000000|#000|#ffffff|#fff)", f"stroke:{fg}", svg)
        govde = govde.replace(";vector-effect:non-scaling-stroke", "")
        govde = re.sub(r"stroke-width:[0-9.]+(?:px)?", f"stroke-width:{kalin}px", govde)
        govde = govde.replace("<defs", f"<style>text,tspan{{fill:{fg} !important;stroke:none !important}}</style><defs", 1) if "<defs" in govde else govde
        if "<!-- *Model_Space -->" in govde:
            ic = govde[govde.index("<!-- *Model_Space -->"):govde.rindex("</svg>")]
        else:
            ic = govde[govde.index(">", govde.index("<svg")) + 1:govde.rindex("</svg>")]
        # Sabitlenen LibreDWG sürümü SVG'yi zaten y-aşağı (ekran yönü) yazar: çevirme YOK (çevirmek yazıyı aynalar).
        out = (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="2400" '
               f'height="{round(2400 * gh / gw)}" viewBox="{gx0} {gy0} {gw} {gh}"><rect x="{gx0}" y="{gy0}" width="{gw}" '
               f'height="{gh}" fill="{bg}"/>{ic}</svg>')
        svg_yol = cikti / f"{ad}_{ek}.svg"
        png_yol = cikti / f"{ad}_{ek}.png"
        svg_yol.write_text(out, encoding="utf-8")
        node = ("const s=require(process.argv[1]);s(process.argv[2],{density:72}).png().toFile(process.argv[3])"
                ".then(()=>process.exit(0)).catch(e=>{console.error(e.message);process.exit(1)})")
        rr = subprocess.run(["node", "-e", node, str(STUDIO / "node_modules" / "sharp"), str(svg_yol), str(png_yol)],
                            capture_output=True, text=True, timeout=180)
        if not os.environ.get("BELGE_SVG_TUT"):  # hata ayıklama: ara SVG dosyasını sakla
            svg_yol.unlink(missing_ok=True)
        if rr.returncode != 0:
            satirlar.append(f"HATA {p.name} ({ek}): {rr.stderr.strip()[:200]}")
        else:
            satirlar.append(f"DWG → {png_yol.relative_to(cikti.parent)}  ({len(yollar)} çizim nesnesi; boyut 2400x{round(2400 * gh / gw)})")
    satirlar.append("  UYARI: görsel tahminidir; çizim ölçeği/ölçü iddiası için orijinal DWG esastır. İnce çizgili plan ince detay okutmaz: tam ekran değil, kırpılmış bölge/yakın plan kullan. Oda yazılarında Türkçe karakterler bozuk çıkabilir (eski DWG kod sayfası): yazıyı çizimden değil belgeden/kullanıcıdan al.")
    return satirlar


# ----------------------------------------------------------------- DOCX
def _par_metin(par) -> str:
    return "".join(t.text or "" for t in par.iter(f"{W}t"))


def docx_al(p: Path, cikti: Path) -> list[str]:
    ad = guvenli_ad(p)
    cikti.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(p) as z:
        kok = ET.fromstring(z.read("word/document.xml"))
        govde = kok.find(f"{W}body")
        md = [f"# {p.name}", ""]
        tablo_say = par_say = 0
        for el in govde:
            if el.tag == f"{W}p":
                metin = _par_metin(el).strip()
                if not metin:
                    continue
                stil = el.find(f"{W}pPr/{W}pStyle")
                sv = (stil.get(f"{W}val") if stil is not None else "") or ""
                m = re.match(r"(?i)(?:heading|başlık|baslik)\s*(\d)", sv)
                md.append(("#" * (int(m.group(1)) + 1) + " " + metin) if m else metin)
                md.append("")
                par_say += 1
            elif el.tag == f"{W}tbl":
                satirlar = []
                for tr in el.iter(f"{W}tr"):
                    satirlar.append([" ".join(_par_metin(pp) for pp in tc.iter(f"{W}p")).strip().replace("|", "/")
                                     for tc in tr.findall(f"{W}tc")])
                if satirlar:
                    n = max(len(r) for r in satirlar)
                    satirlar = [r + [""] * (n - len(r)) for r in satirlar]
                    md.append("| " + " | ".join(satirlar[0]) + " |")
                    md.append("|" + "---|" * n)
                    for r in satirlar[1:]:
                        md.append("| " + " | ".join(r) + " |")
                    md.append("")
                    tablo_say += 1
        (cikti / f"{ad}.md").write_text("\n".join(md), encoding="utf-8")
        gorseller = [n for n in z.namelist() if n.startswith("word/media/")]
        if gorseller:
            gk = cikti / f"{ad}_gorseller"
            gk.mkdir(exist_ok=True)
            for n in gorseller:
                (gk / Path(n).name).write_bytes(z.read(n))
    ek = f", {len(gorseller)} gömülü görsel → {ad}_gorseller/" if gorseller else ""
    return [f"DOCX → {ad}.md  ({par_say} paragraf, {tablo_say} tablo{ek})"]


# ----------------------------------------------------------------- XLSX
def _sutun(ref: str) -> int:
    harf = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for c in harf:
        n = n * 26 + ord(c) - 64
    return n - 1


def xlsx_al(p: Path, cikti: Path) -> list[str]:
    ad = guvenli_ad(p)
    cikti.mkdir(parents=True, exist_ok=True)
    cikis = []
    md = [f"# {p.name}", ""]
    with zipfile.ZipFile(p) as z:
        ortak = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(f"{S}si"):
                ortak.append("".join(t.text or "" for t in si.iter(f"{S}t")))
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rel = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        hedef = {r.get("Id"): r.get("Target") for r in rel}
        RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        for sh in wb.iter(f"{S}sheet"):
            yol = hedef.get(sh.get(RID), "")
            yol = yol.lstrip("/")
            yol = yol if yol.startswith("xl/") else "xl/" + yol
            if yol not in z.namelist():
                continue
            satirlar = []
            for row in ET.fromstring(z.read(yol)).iter(f"{S}row"):
                r = []
                for c in row.findall(f"{S}c"):
                    i = _sutun(c.get("r"))
                    r += [""] * (i + 1 - len(r))
                    t = c.get("t")
                    v = c.find(f"{S}v")
                    if t == "s" and v is not None:
                        r[i] = ortak[int(v.text)]
                    elif t == "inlineStr":
                        r[i] = "".join(x.text or "" for x in c.iter(f"{S}t"))
                    elif v is not None:
                        r[i] = v.text or ""
                satirlar.append(r)
            ad_sayfa = re.sub(r"[^\w\-]+", "_", sh.get("name"), flags=re.UNICODE)
            csv_yol = cikti / f"{ad}__{ad_sayfa}.csv"
            with open(csv_yol, "w", newline="", encoding="utf-8-sig") as f:
                csv.writer(f).writerows(satirlar)
            md.append(f"## {sh.get('name')} ({len(satirlar)} satır)")
            for r in satirlar[:15]:
                md.append("- " + " | ".join(x for x in r))
            md.append("")
            cikis.append(f"XLSX → {csv_yol.name}  ({len(satirlar)} satır)")
    (cikti / f"{ad}_tablo.md").write_text("\n".join(md), encoding="utf-8")  # aynı adlı .docx özetini ezmesin
    note = "  NOT: formül hücrelerinde dosyada kayıtlı SON hesaplanmış değer okunur (Excel'de yeniden hesaplanmaz)."
    return cikis + [note] if cikis else [f"ATLANDI {p.name}: sayfa bulunamadı"]


# ----------------------------------------------------------------- PDF
def pdf_al(p: Path, cikti: Path, en_cok: int = 24) -> list[str]:
    try:
        import pypdfium2 as pdfium
        from pypdf import PdfReader
    except ImportError:
        return [f"ATLANDI {p.name}: pypdfium2/pypdf kurulu değil (Başlat.cmd kurulumu bunları getirir)"]
    ad = guvenli_ad(p)
    cikti.mkdir(parents=True, exist_ok=True)
    pdf = pdfium.PdfDocument(str(p))
    n = len(pdf)
    okuyucu = PdfReader(str(p))
    md = [f"# {p.name}", f"({n} sayfa)", ""]
    metinli = 0
    for i in range(min(n, en_cok)):
        sayfa = pdf[i]
        # 2x ölçek ≈ 144 dpi: video karesi için yeterli; daha büyük sayfalar 3000 px ile sınırlı
        olcek = min(2.0, 3000 / max(sayfa.get_size()))
        sayfa.render(scale=olcek).to_pil().convert("RGB").save(cikti / f"{ad}_s{i + 1:02d}.png")
        try:
            t = (okuyucu.pages[i].extract_text() or "").strip()
        except Exception:
            t = ""
        if t:
            metinli += 1
        md += [f"## Sayfa {i + 1}", t or "_(metin yok)_", ""]
    (cikti / f"{ad}.md").write_text("\n".join(md), encoding="utf-8")
    pdf.close()
    sonuc = [f"PDF → {ad}_s01.png…  ({min(n, en_cok)}/{n} sayfa görseli), metin: {ad}.md ({metinli} sayfada metin)"]
    if metinli == 0:
        sonuc.append("  NOT: metin çıkmadı; PDF taranmış (resim) olabilir. Sistemde OCR yok: sayfa görselini gözle oku.")
    return sonuc


MEDYA = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".mkv", ".mp3", ".wav", ".m4a", ".heic", ".gif"}


def metin_al(p: Path, cikti: Path) -> list[str]:
    """Düz metin (.txt .md .srt .csv): kodlamayı çöz, <ad>.md olarak aktar (senarist okur). 400 KB üstü kesilir."""
    ham = p.read_bytes()[:400_000]
    for kod in ("utf-8-sig", "cp1254", "latin-1"):
        try:
            metin = ham.decode(kod)
            break
        except UnicodeDecodeError:
            continue
    cikti.mkdir(parents=True, exist_ok=True)
    ad = guvenli_ad(p)
    (cikti / f"{ad}.md").write_text("# " + p.name + "\n\n" + metin.strip() + "\n", encoding="utf-8")
    return [f"METİN → {ad}.md  ({len(metin)} karakter, kodlama {kod})"]


def isle(p: Path, cikti: Path) -> list[str]:
    e = p.suffix.lower()
    try:
        if e == ".dwg":
            return dwg_al(p, cikti)
        if e == ".docx":
            return docx_al(p, cikti)
        if e == ".xlsx":
            return xlsx_al(p, cikti)
        if e == ".pdf":
            return pdf_al(p, cikti)
        if e in {".txt", ".md", ".srt", ".csv"}:
            return metin_al(p, cikti)
    except Exception as ex:  # tek dosya hatası tüm alımı durdurmasın
        return [f"HATA {p.name}: {type(ex).__name__}: {ex}"]
    if e in MEDYA:
        return []  # foto/video/ses: medya_envanteri.py
    if e in {".doc", ".xls"}:
        return [f"ATLANDI {p.name}: eski ikili biçim; Word/Excel'de '.docx/.xlsx olarak kaydet' de, tekrar ver"]
    if e == ".dxf":
        return [f"ATLANDI {p.name}: DXF desteği yok; .dwg ver ya da ekle"]
    return [f"ATLANDI {p.name}: desteklenmeyen biçim ({e})"]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows cp1254 konsolu "→" yazamaz
    ap =argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("girdi")
    ap.add_argument("-o", "--cikti", required=True)
    a = ap.parse_args()
    girdi, cikti = Path(a.girdi), Path(a.cikti)
    dosyalar = sorted(x for x in girdi.rglob("*") if x.is_file()) if girdi.is_dir() else [girdi]
    rapor = []
    for f in dosyalar:
        rapor += isle(f, cikti)
    cikti.mkdir(parents=True, exist_ok=True)
    (cikti / "belgeler.md").write_text("# Alınan belgeler\n\n" + "\n".join(f"- {s}" for s in rapor) + "\n", encoding="utf-8")
    print("\n".join(rapor) or "belge türünde dosya yok (foto/video: medya_envanteri.py)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
