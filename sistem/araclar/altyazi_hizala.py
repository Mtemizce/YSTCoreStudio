#!/usr/bin/env python3
"""Sentetik (TTS) anlatım için altyazı: METİN senaryodan, ZAMAN parça sınırlarından (+ isteğe bağlı konuşma→yazı doğrulaması).

Neden: konuşma tanıma özel adları bozar ("Örnek Mimarlık" -> "Zayıma olum imarlık"); biz doğru metni zaten biliyoruz.

  python altyazi_hizala.py <voice_studio rapor.json> --satir <id> [--alim 1] [--stt yazi_cikar.json] [--kayma 0.0] -o kelimeler.json

Her parça için aralık: voice_studio'nun parça [başlangıç, başlangıç+süre]; --stt verilirse o aralığa düşen tanınmış kelimelerin ilk-son zamanına daraltılır
(sessiz uç boşluklar atılır). Parçadaki senaryo kelimeleri aralığa harf sayısıyla orantılı dağıtılır. Çıktı: [{baslangic, bitis, kelime}] (Captions.tsx / platform_cikti.py).
--kayma: tüm zamanlara eklenecek sn (ses katmanının projedeki başlangıcı).
"""
import argparse
import json


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("rapor")
    ap.add_argument("--satir", required=True)
    ap.add_argument("--alim", type=int, default=1)
    ap.add_argument("--stt")
    ap.add_argument("--kayma", type=float, default=0.0)
    ap.add_argument("-o", "--cikti", required=True)
    a = ap.parse_args()
    rep = json.load(open(a.rapor, encoding="utf-8"))[a.satir][a.alim - 1]
    stt = json.load(open(a.stt, encoding="utf-8"))["kelimeler"] if a.stt else []
    out = []
    for p in rep["parcalar"]:
        t0, t1 = p["baslangic"], p["baslangic"] + p["sure"]
        inside = [w for w in stt if t0 - 0.25 <= w["baslangic"] <= t1 + 0.05]
        if inside:
            t0 = max(t0, min(w["baslangic"] for w in inside) - 0.02)
            t1 = min(t1 + 0.1, max(w["bitis"] for w in inside) + 0.05)
        words = p["metin"].split()
        weights = [max(2, len([c for c in w if c.isalnum()])) for w in words]
        total = float(sum(weights))
        cur = t0
        for w, wt in zip(words, weights):
            d = (t1 - t0) * wt / total
            out.append({"baslangic": round(cur + a.kayma, 3), "bitis": round(cur + d + a.kayma, 3), "kelime": w})
            cur += d
    json.dump(out, open(a.cikti, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(out)} kelime -> {a.cikti}")


if __name__ == "__main__":
    main()
