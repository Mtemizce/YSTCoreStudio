#!/usr/bin/env python3
"""Konuşma/yazı tarzı analizi: kimlik/ornekler/ içindeki GERÇEK yazılarından ve ses kayıtlarından cümle kurma tarzını çıkarır.

Neden: "samimi ama profesyonel" gibi beyanlar herkesin yazdığı sözlerdir; gerçek cümlelerin ise ritmi, hitabı, dolgu sözcükleri,
soru/ünlem alışkanlığı ve sık kelimeleri kişiye özeldir. Sistem (senarist ajan) bunu beyanla birlikte okur.

  python sistem/araclar/ses_profili.py                    kimlik/ornekler/* + PROFIL §4/§17 cevapları → kimlik/ses_profili.md
  python sistem/araclar/ses_profili.py --dosya <yol> ...  yalnızca verilen dosyalar

Girdiler: .md .txt (yazı: caption, mesaj, e-posta…), ses/video (.mp3 .wav .m4a .ogg .flac .mp4 .mov: yerelde yazıya çevrilir,
sesin hiçbir yere gönderilmez; ilk kullanımda Whisper modeli bir kez iner). Çıktı yereldir ve yalnızca yazı istatistiği + örnek cümle içerir.
Güvenilirlik: 300 kelimenin altı "zayıf", 1000+ "iyi". Kaynağı belli etmeyen (sana ait olmayan) metin koyma: profilin kendi sesin olmalı.
"""
import argparse
import collections
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ORNEK = ROOT / "kimlik" / "ornekler"
CIKTI = ROOT / "kimlik" / "ses_profili.md"
PROFIL = ROOT / "kimlik" / "PROFIL.md"
YAZI = {".md", ".txt"}
SES = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".mp4", ".mov", ".mkv", ".aac"}
DURAK = set("ve bir bu şu o da de ki mi mı mu mü için ile ama ya çok daha gibi en ne var yok ben sen biz siz onlar ise ya da değil olan olarak kadar sonra önce her bütün şey".split())
DOLGU = ["yani", "işte", "şey", "falan", "hani", "valla", "aslında", "mesela", "tamam mı", "bak", "açıkçası", "herhalde", "bence", "kısacası"]


def kucuk(s: str) -> str:
    return s.replace("İ", "i").replace("I", "ı").lower()


def metin_temizle(t: str) -> str:
    t = re.sub(r"^---.*?---\s*", "", t, flags=re.S)         # frontmatter
    t = re.sub(r"```.*?```", " ", t, flags=re.S)
    t = re.sub(r"<!--.*?-->", " ", t, flags=re.S)
    t = re.sub(r"^\s{0,3}#{1,6}\s+.*$", " ", t, flags=re.M)  # başlıklar
    t = re.sub(r"[*_`>\[\]()]|https?://\S+", " ", t)
    return t


def sesi_yaziya(yol: Path) -> str:
    cikti = Path(tempfile.mkdtemp(prefix="ses-profili-")) / "t.json"
    r = subprocess.run([sys.executable, str(ROOT / "sistem" / "araclar" / "yazi_cikar.py"), str(yol), "-o", str(cikti), "--dil", "tr"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or not cikti.exists():
        print(f"  uyarı: {yol.name} yazıya çevrilemedi: {(r.stderr or r.stdout).strip()[-120:]}", file=sys.stderr)
        return ""
    j = json.loads(cikti.read_text(encoding="utf-8"))
    return " ".join(c["metin"] for c in j.get("cumleler", []))


def profil_cevaplari() -> str:
    """PROFIL.md'deki kullanıcı cevapları: §4 örnek cümleler ve §17 anlatı soruları (şablon soru metinleri hariç)."""
    if not PROFIL.exists():
        return ""
    t = PROFIL.read_text(encoding="utf-8")
    parcalar = []
    m = re.search(r"3-5 örnek cümle[^\n]*:\s*\n((?:\s+\d\.[^\n]*\n)+)", t)
    if m:
        parcalar += [re.sub(r"^\s+\d\.\s*", "", s) for s in m.group(1).splitlines()]
    for rx in (r"\(3-4 cümle\):[ \t]*([^\n]+)", r"30 saniyede cevabın:[ \t]*([^\n]+)"):
        mm = re.search(rx, t)
        if mm:
            parcalar.append(mm.group(1))
    return "\n".join(p for p in parcalar if p.strip())


def cumlelere_bol(t: str) -> list[str]:
    t = re.sub(r"\s+", " ", t)
    return [c.strip() for c in re.split(r"(?<=[.!?…])\s+|\n+", t) if len(c.strip().split()) >= 2]


def analiz(metin: str) -> dict:
    cumleler = cumlelere_bol(metin)
    kelimeler = re.findall(r"[a-zçğıöşüâîû']+", kucuk(metin))
    uz = [len(c.split()) for c in cumleler] or [0]
    n = max(len(kelimeler), 1)
    sayac = collections.Counter(k for k in kelimeler if len(k) > 3 and k not in DURAK)
    ilk = collections.Counter(kucuk(c.split()[0]).strip(".,!?…") for c in cumleler if c.split())
    low = kucuk(metin)
    siz = len(re.findall(r"\b(siz|sizin|size|sizi|sizce)\b|\w+(?:ınız|iniz|unuz|ünüz)\b", low))
    sen = len(re.findall(r"\b(sen|senin|sana|seni|sence)\b", low))
    biz = len(re.findall(r"\b(biz|bizim|bize|bizi)\b", low))
    ben = len(re.findall(r"\b(ben|benim|bana|beni)\b", low))
    dolgu = {d: len(re.findall(r"\b" + re.escape(d) + r"\b", low)) for d in DOLGU}
    return {
        "kelime": len(kelimeler), "cumle": len(cumleler),
        "ort_cumle": round(sum(uz) / len(uz), 1), "medyan_cumle": sorted(uz)[len(uz) // 2],
        "kisa_oran": round(sum(1 for x in uz if x <= 6) / len(uz), 2), "uzun_oran": round(sum(1 for x in uz if x >= 20) / len(uz), 2),
        "soru": round(metin.count("?") / max(len(cumleler), 1), 2), "unlem": round(metin.count("!") / max(len(cumleler), 1), 2),
        "uc_nokta": metin.count("…") + metin.count("..."),
        "emoji": len(re.findall("[\U0001F300-\U0001FAFF☀-➿]", metin)),
        "hitap": {"siz": siz, "sen": sen}, "ozne": {"biz": biz, "ben": ben},
        "dolgu": {k: v for k, v in dolgu.items() if v}, "dolgu_100": round(100 * sum(dolgu.values()) / n, 1),
        "sik": [k for k, _ in sayac.most_common(25)], "acilis": [k for k, _ in ilk.most_common(8)],
        "ornek": [c for c in cumleler if 5 <= len(c.split()) <= 24][:: max(1, len([c for c in cumleler if 5 <= len(c.split()) <= 24]) // 12)][:12],
    }


def yaz(a: dict, kaynaklar: list[str]) -> str:
    guven = "zayıf (300 kelimenin altı: daha fazla gerçek örnek ekle)" if a["kelime"] < 300 else ("orta" if a["kelime"] < 1000 else "iyi")
    hitap = "siz" if a["hitap"]["siz"] > a["hitap"]["sen"] * 1.5 else "sen" if a["hitap"]["sen"] > a["hitap"]["siz"] * 1.5 else "karışık/belirsiz"
    ozne = "kurumsal çoğul (biz)" if a["ozne"]["biz"] > a["ozne"]["ben"] * 1.5 else "tekil (ben)" if a["ozne"]["ben"] > a["ozne"]["biz"] * 1.5 else "karışık"
    ritim = "kısa ve vurucu cümleler" if a["ort_cumle"] <= 9 else "orta uzunlukta, dengeli" if a["ort_cumle"] <= 15 else "uzun, akıcı cümleler"
    s = [
        "# Ses profili (OTOMATİK üretildi: elle düzenleme, `sistem/araclar/ses_profili.py` ile yenile)",
        "",
        f"Kaynak: {', '.join(kaynaklar)} · {a['kelime']} kelime, {a['cumle']} cümle · **güvenilirlik: {guven}**",
        "",
        "## Ritim ve hitap (senarist bunu ölçüt alır)",
        f"- Cümle uzunluğu: ortalama {a['ort_cumle']} kelime, medyan {a['medyan_cumle']} → **{ritim}**; kısa (≤6 kelime) cümle oranı %{int(a['kisa_oran'] * 100)}, uzun (≥20) %{int(a['uzun_oran'] * 100)}",
        f"- Hitap: **{hitap}** (siz-izi {a['hitap']['siz']}, sen-izi {a['hitap']['sen']}) · özne: **{ozne}**",
        f"- Soru oranı %{int(a['soru'] * 100)}, ünlem oranı %{int(a['unlem'] * 100)} (yüksek ünlem = sert/abartılı okunur: MARKA ünlem yığınını yasaklar), üç nokta {a['uc_nokta']}, emoji {a['emoji']}",
        f"- Dolgu/konuşma izleri (100 kelimede {a['dolgu_100']}): {', '.join(f'{k}×{v}' for k, v in a['dolgu'].items()) or 'yok'}",
        f"- Cümleyi sık şununla açar: {', '.join(a['acilis'])}",
        f"- En sık anlamlı sözcükler: {', '.join(a['sik'])}",
        "",
        "## Gerçek örnek cümleler (ses bunlara benzemeli)",
    ] + [f"- {c}" for c in a["ornek"]] + [
        "",
        "## Kullanım kuralı",
        "Senaryodaki cümleler bu ritme ve sözcük dağarcığına yakın olmalı; burada olmayan klişe sözcük ekleme. Beyanla (PROFIL.md) çelişen bir ölçüm varsa (ör. beyan: resmi, ölçüm: gündelik) **ölçüm kazanır** ve yönetmen kullanıcıya bunu söyler.",
    ]
    return "\n".join(s) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dosya", nargs="*")
    a = ap.parse_args()
    dosyalar = [Path(x) for x in a.dosya] if a.dosya else sorted(f for f in ORNEK.glob("*") if f.is_file() and f.name != ".gitkeep")
    parcalar, kaynak = [], []
    for f in dosyalar:
        uz = f.suffix.lower()
        if uz in YAZI:
            parcalar.append(metin_temizle(f.read_text(encoding="utf-8", errors="replace")))
            kaynak.append(f.name)
        elif uz in SES:
            print(f"  yazıya çevriliyor: {f.name} (yerelde)")
            t = sesi_yaziya(f)
            if t:
                parcalar.append(t)
                kaynak.append(f.name + " (ses)")
    pc = profil_cevaplari()
    if pc:
        parcalar.append(pc)
        kaynak.append("PROFIL.md cevapları")
    metin = "\n".join(parcalar).strip()
    if len(metin.split()) < 20:
        print("Analiz için yeterli metin yok. kimlik/ornekler/ içine gerçek yazılarını (caption, mesaj) ve/veya ses kayıtlarını koy; PROFIL §4 ve §17'yi doldur.")
        return 1
    r = analiz(metin)
    CIKTI.write_text(yaz(r, kaynak), encoding="utf-8")
    print(f"yazıldı: {CIKTI}  ({r['kelime']} kelime; kaynak: {', '.join(kaynak)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
