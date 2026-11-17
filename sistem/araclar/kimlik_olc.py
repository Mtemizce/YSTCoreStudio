#!/usr/bin/env python3
"""kimlik/PROFIL.md doluluk ölçümü: hangi alanlar dolu, hangileri video kalitesini doğrudan etkileyen eksikler?

  python sistem/araclar/kimlik_olc.py            okunur özet
  python sistem/araclar/kimlik_olc.py --json     panel/başka araçlar için

Önem: KRİTİK = boşsa üretim jenerik/yanlış çıkar (ton, örnek cümle, mesaj, kitle, çağrı, izinler);
      ÖNEMLİ = sonucu belirgin iyileştirir; İYİ = olsa güzel.
Ölçüt "dolu": alanın etiketinden sonra boş olmayan metin / işaretli kutu / numaralı satırda içerik var.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROFIL = ROOT / "kimlik" / "PROFIL.md"
K, O, I = "KRİTİK", "ÖNEMLİ", "İYİ"

# (kod, açıklama, önem, düzenli ifade: eşleşiyorsa DOLU; grup 1 boş olmayan içerik)
KONTROLLER = [
    ("1", "Bir cümlede ben", K, r"## 1\.[^\n]*\n(?:<!--[^>]*-->[ \t]*\n)?-[ \t]*([^\s<][^\n]*)"),
    ("2.ad", "Adım / marka adım", O, r"Adım / marka adım:[ \t]*(\S[^\n]*)"),
    ("2.yuz", "Yüzüm/sesim videoda olacak mı", O, r"\[\*\][^\n]*(?:evet|hayır|duruma göre)[^\n]*\n[^\n]*kaydedeceğim|\[\*\]"),
    ("3.sifat", "5 sıfat (beni böyle tanımlarlar)", O, r"5 sıfat[^\n]*:[ \t]*(\S[^\n]*)"),
    ("3.enerji", "Enerji ve resmiyet", O, r"Enerji[^\n]*:[ \t]*(\d+)"),
    ("3.sinir", "Beni sinirlendiren video türleri/klişeler", O, r"sinirlendiren[^\n]*:[ \t]*(\S[^\n]*)"),
    ("3.tek", "İzleyici hangi tek şeyi hatırlasın", K, r"hatırlasın\?[ \t]*(\S[^\n]*)"),
    ("4.cumle", "3-5 gerçek örnek cümle (en değerli alan)", K, r"örnek cümle[^\n]*:\s*\n\s*1\.[ \t]*(\S[^\n]*)"),
    ("4.ifade", "Sık kullandığım ifadeler", O, r"Sık kullandığım ifadeler[^\n]*:[ \t]*(\S[^\n]*)"),
    ("4.yasak", "Asla kullanmayacağım kelimeler", K, r"Asla kullanmayacağım[^\n]*:[ \t]*(\S[^\n]*)"),
    ("5.fikir", "3 ana fikir", K, r"3 ana fikir[^\n]*:\s*\n\s*1\.[ \t]*(\S[^\n]*)"),
    ("5.kanit", "Ana fikirlerin kanıtı (gerçek proje/rakam/izinli örnek)", O, r"\*\*kanıtı\*\*[^\n]*:[ \t]*(\S[^\n]*)|kanıtı[^\n]*\)[ \t]*:[ \t]*(\S[^\n]*)"),
    ("5.asla", "Asla söylemem/ima etmem", O, r"\*\*Asla\*\* söylemem[^\n]*:[ \t]*(\S[^\n]*)"),
    ("6.kim", "Kim izliyor (hedef kitle)", K, r"Kim izliyor[^\n]*\?[ \t]*(\S[^\n]*)"),
    ("6.ne", "Ne arıyor, neden beni izlesin", O, r"neden beni izlesin\?[ \t]*(\S[^\n]*)"),
    ("6.nerede", "Nerede izliyor (telefon/sesli-sessiz)", I, r"Nerede izliyor[^\n]*\?[ \t]*(\S[^\n]*)"),
    ("7.hedef", "Birincil hedef", O, r"Birincil hedef:[^\n]*\[\*\]"),
    ("7.cagri", "Çağrı cümlesi (kendi sözlerinle)", K, r"Çağrı cümlesi[^\n]*:[ \t]*(\S[^\n]*)"),
    ("7.iletisim", "İletişim bilgisi (videoda görünecekse)", O, r"İletişim bilgisi[^\n]*:[ \t]*(\S[^\n]*)"),
    ("8.ref", "Beğendiğim 3 marka/video ve neden", K, r"Beğendiğim \*\*3 marka[^\n]*:\s*\n\s*1\.[ \t]*(\S[^\n]*)"),
    ("8.gitmeyen", "Hoşuma gitmeyen görünümler", O, r"\*\*gitmeyen\*\* görünümler[^\n]*:[ \t]*(\S[^\n]*)"),
    ("8.renk", "Renk eğilimi / marka renkleri", O, r"Renk eğilimim[^\n]*:[ \t]*(\S[^\n]*)"),
    ("9.muzik", "Müzik havası (tür, tempo, his)", O, r"Müzik havası[^\n]*:[ \t]*(\S[^\n]*)"),
    ("10.hesap", "Platform hesapları", I, r"\|[ \t]*(?:Instagram|TikTok|YouTube)[^|\n]*\|[ \t]*([^|\s][^|\n]*)\|"),
    ("11.kisi", "Yayın izni olmayan kişi/fotoğraflar", K, r"Görüntüsü kullanılmayacak[^\n]*:[ \t]*(\S[^\n]*)"),
    ("11.cocuk", "Çocuk görüntüsü politikası", K, r"Çocuk görüntüsü politikası:[^\n]*\[\*\]"),
    ("11.musteri", "Müşteri adı/lokasyon gösterme kuralı", K, r"Müşteri adı/lokasyon[^\n]*:[ \t]*(\S[^\n]*)"),
    ("11.filigran", "Filigran/logo kuralı", O, r"Filigran / logo kuralı:[ \t]*(\S[^\n]*)"),
    ("12.baglam", "Şu an üzerinde çalıştığım şeyler", I, r"## 12\.[^\n]*\n\s*-[ \t]*(\S[^\n]*)"),
    ("13.duygu", "Hissettirmek istediğim 3 duygu", K, r"## 13\.[^\n]*\n(?:<!--[^>]*-->[ \t]*\n)?1\.[ \t]*([^\s<][^\n]*)"),
    ("14.arsiv", "Arşiv ve işlerim: iş türleri, yıllar, imza projeler", K, r"## 14\.[\s\S]*?İş türleri[^\n]*:[ \t]*(\S[^\n]*)"),
    ("14.yayin", "Arşivden hangi işler gösterilebilir / hangileri gösterilmez", K, r"Gösterilebilecek[^\n]*:[ \t]*(\S[^\n]*)"),
    ("15.gercek", "Doğrulanmış gerçekler tablosu (rakam/yıl/ödül kaynağı)", K, r"## 15\.[^#]*?\|---\|---\|---\|[ \t]*\n\|[ \t]*([^|\s][^|\n]*)\|"),
    ("16.telaffuz", "Telaffuz sözlüğü (marka/özel adların okunuşu)", K, r"\):[ \t]*[^\n→]*→[ \t]*(\S[^\n]*)"),
    ("16.onay", "Çalışma tercihi: sistem seni ne kadar sorsun", O, r"Sistem seni ne kadar sorsun\?[^\n]*\[\*\]"),
    ("17.gurur", "Anlatı sorusu 1: en gurur duyduğun iş", K, r"\n1\. En gurur[^\n]*\):[ \t]*(\S[^\n]*)"),
    ("17.otuz", "Anlatı sorusu 2: 30 saniyede ne yapıyorsun", K, r"30 saniyede cevabın:[ \t]*(\S[^\n]*)"),
]


def olc(metin: str) -> dict:
    sonuc = []
    for kod, ad, onem, rx in KONTROLLER:
        m = re.search(rx, metin, re.S)
        dolu = bool(m) and (not m.groups() or any(g and g.strip() and not g.strip().startswith(("<!--", "-->")) for g in m.groups()) or "[*]" in m.group(0))
        sonuc.append({"kod": kod, "alan": ad, "onem": onem, "dolu": dolu})
    toplam = len(sonuc)
    dolu_n = sum(1 for s in sonuc if s["dolu"])
    kritik = [s for s in sonuc if s["onem"] == K]
    return {
        "dolu": dolu_n, "toplam": toplam, "yuzde": round(100 * dolu_n / toplam),
        "kritik_dolu": sum(1 for s in kritik if s["dolu"]), "kritik_toplam": len(kritik),
        "kritik_yuzde": round(100 * sum(1 for s in kritik if s["dolu"]) / len(kritik)),
        "eksik": [s for s in sonuc if not s["dolu"]],
        "alanlar": sonuc,
    }


def katmanlar() -> dict:
    """Beyanın ötesindeki kanıt katmanları: gerçek örnekler, zevk testi, öğrenilenler."""
    kd = ROOT / "kimlik"
    ornek = [f for f in (kd / "ornekler").glob("*") if f.is_file() and f.name != ".gitkeep"] if (kd / "ornekler").is_dir() else []
    return {
        "ornekler": len(ornek), "ornekler_yeterli": len(ornek) >= 3,
        "ses_profili": (kd / "ses_profili.md").is_file(),
        "zevk": (kd / "zevk.md").is_file(),
        "ogrenilenler": (kd / "ogrenilenler.md").is_file(),
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    metin = PROFIL.read_text(encoding="utf-8") if PROFIL.exists() else ""
    r = olc(metin)
    r["katmanlar"] = katmanlar()
    if "--json" in sys.argv:
        print(json.dumps(r, ensure_ascii=False))
        return 0
    print(f"Kimlik doluluğu: %{r['yuzde']} ({r['dolu']}/{r['toplam']}) · KRİTİK alanlar: %{r['kritik_yuzde']} ({r['kritik_dolu']}/{r['kritik_toplam']})")
    for onem in (K, O, I):
        liste = [s for s in r["eksik"] if s["onem"] == onem]
        if liste:
            print(f"\n{onem} eksikler ({len(liste)}):")
            for s in liste:
                print(f"  - [{s['kod']}] {s['alan']}")
    k = r["katmanlar"]
    print("\nKanıt katmanları (beyanın ötesi):")
    print(f"  - gerçek örnek malzeme (kimlik/ornekler, en az 3): {k['ornekler']} dosya" + ("" if k["ornekler_yeterli"] else "  ← EKSİK"))
    print(f"  - ses profili analizi (kimlik/ses_profili.md): " + ("var" if k["ses_profili"] else "yok (sistem/araclar/ses_profili.py)"))
    print(f"  - zevk testi (kimlik/zevk.md): " + ("var" if k["zevk"] else "yok (panel → Kimlik → Zevk testi)"))
    print(f"  - öğrenilenler (kimlik/ogrenilenler.md): " + ("var" if k["ogrenilenler"] else "henüz yok (ilk proje sonrası oluşur)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
