#!/usr/bin/env python3
"""Seslendirme stüdyosu: motor adaptörleri (tts/) + parçalı yönlendirme + ton adayı seçimi + ses işleme + doğal bitiş.

Motorlar `tts/` klasöründeki adaptörlerdir (ema = EMA Lightning, tek ses, hız+seed; pocket-tr = Pocket TTS Turkish: hazır sesler, duygu, rızalı klonlama, atıflı). Yeni bir açık kaynak motor
eklemek için bkz. tts/__init__.py. Motor planda `"motor": "ema"` ile seçilir; satır/parça başına ezilebilir.

  python voice_studio.py plan.json -o cikti_klasoru [--takes 3] [--aday 5] [--no-fx] [--sr 48000]

plan.json:
  {"motor": "ema",
   "satirlar": [
     {"id": "reels", "kuyruk": 0.55, "son_fade_ms": 70,    // bitiş: son hecenin sönmesi + oda kuyruğu (sn)
      "parcalar": [
        {"metin": "Önce şantiye, sonra hikâye.", "hiz": 1.0, "sonra": 0.5},
        {"metin": "Mekânı, hikâyeye çeviriyoruz.", "hiz": 0.92, "sonra": 0.0}]}]}
  hiz   0.5-2 (1 normal). Vurgulanacak ifade: ayrı parça, hiz 0.88-0.95, öncesinde 0.2-0.35 sn duraklama.
  sonra bu parçadan sonraki sessizlik (sn): virgül 0.15-0.25, nokta 0.4-0.6, sahne arası 0.7+.
  ses/duygu/klon/sozluk: yalnızca bunları destekleyen motorlarda anlamlıdır (EMA'da yok sayılır, uyarı verilir).
  seed  parça başına alım sabitler.
  bitis parça başına cümle sonu niyeti: "dus" (bildirim, varsayılan; '.' ile biten) | "acik" (soru; '?' ile biten) | "serbest" ('…').
        `--aday 5`: parça başına 5 alım (farklı seed) üretilir, bitiş tonu hedefe (+ canlılığa) en yakın olan seçilir; seçim rapor.json'da (secim).
Çıktı: <id>_take<N>.wav (ham), <id>_take<N>_fx.wav (işlenmiş), rapor.json (parça başlangıçları, süre, LUFS, motor/seed/seçim).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import wave

SR = 48000
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), *[".."] * 4))
sys.path.insert(0, os.path.join(ROOT, "sistem"))  # tts/ paketi sistem/ altında
# Konuşma zinciri: rumble kes, sıcaklık, netlik, sibilans, hafif sıkıştırma, küçük oda, seviye
FX = ("highpass=f=70,"
      "equalizer=f=190:t=q:w=1.0:g=1.5,"
      "equalizer=f=3200:t=q:w=1.2:g=2.0,"
      "deesser=i=0.4:m=0.5:f=0.5,"
      "acompressor=threshold=-21dB:ratio=3:attack=8:release=140:makeup=3,"
      "aecho=in_gain=0.92:out_gain=0.92:delays=19|41:decays=0.18|0.10,"
      "loudnorm=I=-16:TP=-1.5:LRA=7")


def ffmpeg():
    p = shutil.which("ffmpeg")
    if not p:
        try:
            import media_tools
            p = media_tools.ffmpeg()
        except Exception:
            pass
    if not p:
        sys.exit("ffmpeg bulunamadı")
    return p


def read_wav(path):
    import numpy as np
    with wave.open(path) as w:
        sr, n, ch = w.getframerate(), w.getnframes(), w.getnchannels()
        raw = w.readframes(n)
    a = np.frombuffer(raw, dtype="<i2").astype("float32") / 32768.0
    return (a.reshape(-1, ch).mean(axis=1) if ch > 1 else a), sr


def write_wav(path, arr, sr):
    import numpy as np
    pcm = (np.clip(arr, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def convert(src, dst, sr):
    """Örnekleme hızı + tek kanal + 16 bit (hız motor tarafında uygulanmıştır)."""
    cmd = [ffmpeg(), "-v", "error", "-y", "-i", src, "-ar", str(sr), "-ac", "1", "-c:a", "pcm_s16le", dst]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("ffmpeg dönüştürme hatası: " + (r.stderr.strip().splitlines() or ["?"])[-1])


def measure(path):
    r = subprocess.run([ffmpeg(), "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    t = r.stderr
    lufs = re.findall(r"I:\s+(-?[\d.]+) LUFS", t)
    peak = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", t)
    return {"lufs": float(lufs[-1]) if lufs else None, "peak_db": float(peak[-1]) if peak else None}


def apply_fx(src, dst, chain):
    r = subprocess.run([ffmpeg(), "-v", "error", "-y", "-i", src, "-af", chain, "-ar", str(SR), dst], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("ffmpeg ses zinciri hata verdi: " + (r.stderr.strip().splitlines() or ["?"])[-1])


def bitis_olc(wav):
    """Parçanın cümle sonu tonu: son ~0.45 sn sesli bölge ile parça ortasının perde farkı (yarım ton; negatif = düşer) ve perde değişkenliği."""
    try:
        import numpy as np
        import parselmouth
    except ImportError:
        return None
    snd = parselmouth.Sound(wav)
    pitch = snd.to_pitch(time_step=0.01, pitch_floor=70, pitch_ceiling=420)
    f0 = pitch.selected_array["frequency"]
    t = pitch.xs()
    v = f0 > 0
    if v.sum() < 12:
        return None
    st = 12 * np.log2(f0[v] / 100.0)
    tv = t[v]
    end = float(tv[-1])
    last = st[tv >= end - 0.45]
    mid = st[(tv >= tv[0] + (end - tv[0]) * 0.25) & (tv <= tv[0] + (end - tv[0]) * 0.75)]
    if len(last) < 3 or len(mid) < 3:
        return None
    return {"dusus": float(np.median(last) - np.median(mid)), "std": float(np.std(st))}


def hedef_bitis(p):
    """Parça cümle sonu niyeti: dus (bildirim, varsayılan) | acik (soru) | serbest (yalnızca canlılık). Plan'da "bitis" ile ezilir."""
    if p.get("bitis"):
        return p["bitis"]
    s = p["metin"].strip()
    return "acik" if s.endswith("?") else "serbest" if s.endswith("…") else "dus"


def main():
    import numpy as np
    import tts
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("plan")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--takes", type=int, default=1, help="her satır için kaç alım (farklı seed)")
    ap.add_argument("--no-fx", action="store_true")
    ap.add_argument("--sr", type=int, default=SR, choices=(48000, 24000, 16000, 8000))
    ap.add_argument("--base-seed", type=int, default=100)
    ap.add_argument("--aday", type=int, default=1, help="parça başına aday alım sayısı: cümle sonu tonu hedefe (düşen/açık) en yakın olan seçilir")
    a = ap.parse_args()
    plan = json.load(open(a.plan, encoding="utf-8"))
    default_motor = plan.get("motor", "ema")
    os.makedirs(a.out, exist_ok=True)
    report = {}
    uyarildi = set()
    kullanilan = set()  # atıf gerektiren motorlar için ATIF.txt
    work = tempfile.mkdtemp(prefix="kurgu-ses-")
    try:
        for line in plan["satirlar"]:
            for take in range(1, a.takes + 1):
                parts = line["parcalar"]
                for i, p in enumerate(parts):
                    p.setdefault("seed", a.base_seed + take * 17 + i)

                def motor_adi(p):
                    return p.get("motor", line.get("motor", default_motor))

                adetler = max(1, a.aday)
                if adetler > 1 and any(getattr(tts.al(motor_adi(p)), "ucretli", False) for p in parts):
                    istenen = int(plan.get("aday_ucretli", 1))
                    print(f"uyarı: ücretli (bulut) motor: her alım faturalanır, parça başına aday sayısı {adetler} → {istenen} "
                          f"(gerçekten istiyorsan plan.json'a \"aday_ucretli\": N yaz)", file=sys.stderr)
                    adetler = max(1, istenen)
                gruplar = {}  # motor -> işler (tek model yüklemesi)
                for i, p in enumerate(parts):
                    m = tts.al(motor_adi(p))
                    for alan in ("duygu", "ses", "klon", "sozluk"):
                        if (p.get(alan) or plan.get(alan)) and not m.desteklenen.get(alan) and (m.ad, alan) not in uyarildi:
                            uyarildi.add((m.ad, alan))
                            print(f"uyarı: '{m.ad}' motoru '{alan}' alanını desteklemiyor, yok sayıldı", file=sys.stderr)
                    for c in range(adetler):
                        q = dict(p)
                        q["seed"] = p["seed"] + 1000 * c
                        gruplar.setdefault(m.ad, []).append((f"{line['id']}_t{take}_p{i}_c{c}", q))
                wavs = {}
                for ad, isler in gruplar.items():
                    kullanilan.add(ad)
                    wavs.update(tts.al(ad).uret(isler, plan, os.path.join(work, f"{line['id']}_t{take}_{ad}"), a.sr))
                secim, secilen = {}, {}
                for i, p in enumerate(parts):
                    k = f"{line['id']}_t{take}_p{i}"
                    best = 0
                    if adetler > 1:
                        hedef = hedef_bitis(p)
                        skor = []
                        for c in range(adetler):
                            mm = bitis_olc(wavs[f"{k}_c{c}"])
                            if mm is None:
                                continue
                            d = mm["dusus"]
                            puan = (-d if hedef == "dus" else d if hedef == "acik" else 0.0) + 0.15 * mm["std"]
                            skor.append((puan, c, d, mm["std"]))
                        best = max(skor)[1] if skor else 0
                        secim[k] = {"aday": best, "seed": p["seed"] + 1000 * best, "hedef": hedef,
                                    "dusus_st": round(next((s_[2] for s_ in skor if s_[1] == best), 0.0), 2), "aday_sayisi": adetler}
                    secilen[k] = wavs[f"{k}_c{best}"]
                    p["seed"] = p["seed"] + 1000 * best
                chunks, t_total, part_times = [], 0.0, []
                for i, p in enumerate(parts):
                    speed = float(p.get("hiz", 1.0))
                    tmp = os.path.join(work, f"part_{i}.wav")
                    convert(secilen[f"{line['id']}_t{take}_p{i}"], tmp, a.sr)
                    arr, sr = read_wav(tmp)
                    gap = np.zeros(int(float(p.get("sonra", 0.0)) * sr), dtype="float32")
                    part_times.append({"metin": p["metin"], "motor": motor_adi(p), "hiz": speed,
                                       "baslangic": round(t_total, 3), "sure": round(len(arr) / sr, 3), "seed": p["seed"],
                                       "secim": secim.get(f"{line['id']}_t{take}_p{i}")})
                    t_total += (len(arr) + len(gap)) / sr
                    chunks += [arr, gap]
                audio = np.concatenate(chunks) if chunks else np.zeros(1, dtype="float32")
                # Doğal bitiş: son hecenin sönmesi (kısa fade) + oda kuyruğu için sessizlik. Sönmeden kesilen ses "havada kalır".
                fade_ms = float(line.get("son_fade_ms", 70))
                tail = float(line.get("kuyruk", 0.5))
                voiced_end = len(audio) - int(float(parts[-1].get("sonra", 0.0)) * a.sr)
                nf = int(a.sr * fade_ms / 1000)
                if 0 < nf < voiced_end:
                    audio[voiced_end - nf:voiced_end] *= np.linspace(1.0, 0.0, nf, dtype="float32")
                audio = np.concatenate([audio, np.zeros(int(tail * a.sr), dtype="float32")])
                raw = os.path.join(a.out, f'{line["id"]}_take{take}.wav')
                write_wav(raw, audio, a.sr)
                entry = {"dosya": os.path.basename(raw), "sure": round(len(audio) / a.sr, 3), "parcalar": part_times, **measure(raw)}
                if not a.no_fx:
                    fx = os.path.join(a.out, f'{line["id"]}_take{take}_fx.wav')
                    apply_fx(raw, fx, line.get("fx") or FX)
                    with wave.open(fx) as w:
                        fx_dur = round(w.getnframes() / w.getframerate(), 3)
                    entry["fx"] = {"dosya": os.path.basename(fx), "sure": fx_dur, **measure(fx)}
                report.setdefault(line["id"], []).append(entry)
                print(line["id"], f"take{take}", entry["sure"], "sn", entry.get("fx", {}).get("lufs"), "LUFS(fx)")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    json.dump(report, open(os.path.join(a.out, "rapor.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    atiflar = [m.atif for ad in sorted(kullanilan) for m in [tts.motorlar()[ad]] if getattr(m, "atif_gerekir", False) and getattr(m, "atif", "")]
    if atiflar:  # CC-BY vb. motorlar: paylaşımda kullanılacak atıf metni çıktının yanına yazılır
        nl = chr(10)
        open(os.path.join(a.out, "ATIF.txt"), "w", encoding="utf-8").write("Bu seslendirmede kullanılan açık kaynak motor(lar) için atıf:" + nl + nl.join("- " + x for x in atiflar) + nl)


if __name__ == "__main__":
    main()
