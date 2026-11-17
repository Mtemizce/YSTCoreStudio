---
name: kaba-kurgu
description: "Kullanıcının ham videosunu (konuşan kafa, ekran kaydı, çekim) konuşma yazısına dayanarak kaba kurguya çevirir: önce hatalı alım/yeniden başlama (flub) önerisi (insan onaylı), sonra sessizlik kesme; hepsi yerel (faster-whisper + ffmpeg). Ham video geldiğinde, \"sessizlikleri kes\", \"tekrarları at\", \"konuşmayı kısalt\", altyazı için yazıya dökme gerektiğinde kullan."
---

# Kaba kurgu (konuşma yazısı tabanlı)

Uyarlama: avenoxai/avenoxskills `avenox-roughcut` (MIT). macOS/mlx-whisper/auto-editor yerine **Windows yerel yığın**: `faster-whisper` + `ffmpeg`. Dışarı hiçbir şey gitmez; model ağırlığı HF'den bir kez iner.

İki tür kesim: **sessizlik** (mekanik) ve **flub/yeniden alım** (anlamsal). Anlamsal kesim **insan onaylı**: ajan onaysız içerik keserse eninde sonunda gerçek bir noktayı atar.

## Sıra (zaman koordinatı için önemli)
Flub zamanları HAM koordinattadır; sessizlik kesimi zaman çizelgesini kaydırır → **önce flub, sonra sessizlik**.

### 1. Yazıya dök
```
python sistem/araclar/yazi_cikar.py projeler/<ad>/kaynak/video/ham.mp4 -o projeler/<ad>/hazir/transkript/ham.json --srt
```
Kelime zamanlı JSON + SRT. Türkçe özel adlar bozulabilir: `--duzeltme duzeltme.json` ({"yanlış":"doğru"}). GPU çalışmazsa CPU int8'e geçer (45 sn ≈ 17 sn). Model: `small` varsayılan; zor ses için `medium` / `large-v3-turbo`.

### 2. Flub'ları bul ve **tablo olarak öner** (insan onayı)
`ham.json` cümlelerinde ara: aynı cümle başlangıcının iki kez söylenmesi · yarım kesilip baştan alınan cümle · kendi kendini düzeltme ("şunu… yerine bunu…") · boşluktan hemen önce asılı dolgu sözcük. Çıktı tablosu: `mm:ss.s – mm:ss.s | metin | neden | KESİLSİN mi?`. **Onay gelmeden kesme.**

### 3. Kes: flub (ffmpeg `select`) sonra sessizlik
Flub: tutulacak aralıkların **tümleyeni** olarak `select`/`aselect` ile kare-hassas kes:
```
KEEP="between(t,4.96,46.16)+between(t,48.98,69.42)+between(t,SON,99999)"
ffmpeg -y -i ham.mp4 -vf "select='$KEEP',setpts=N/FRAME_RATE/TB" -af "aselect='$KEEP',asetpts=N/SR/TB" -c:v libx264 -crf 18 -c:a aac -b:a 192k kesim/flubsiz.mp4
```
Sessizlik:
```
python sistem/araclar/sessizlik_kes.py kesim/flubsiz.mp4 kesim/taslak_v1.mp4 --db -30 --min 0.6 --pad 0.12   # önce --sadece-rapor
```
Notlar: `--min` bırakılan duraklama ritmini belirler (küçük = sıkı/parçalı, büyük = akıcı); `--db` mikrofon/sese göre ayarlanır (çok düşük = cümle sonlarını yer). Her kesimden sonra `yazi_cikar.py` ile **yeniden yazıya dök** (grafik/altyazı zamanları için).

### 4. Gözden geçir
Taslağı yönetmene göster (Kurgu editörü). Kesilen her noktada cümle ortası kesilmemiş mi, nefes/doğal duraklama korunmuş mu dinletip doğrula.

## Konuşmaya dayalı yerleşim
Altyazı kelime zamanı (`kelimeler[]`) → Remotion `Captions` ya da `platform_cikti.py --altyazi`. Konuşan yüz varsa grafikleri **boş güvenli alana** koy (yüzün/önemli arayüzün üstüne asla); kareyi `ffmpeg -ss` ile alıp bak.

## Tuzaklar (öğrenilmiş)
- Sessizlik eşiği tek bir ses/mikrofona ayarlıdır; başka kişi/oda için yeniden kalibre et.
- Konuşma tanıma özel adları/yer adlarını bozar; altyazıyı **doğru yazımla** düzelt (`--duzeltme`), kişi adlarını kullanıcıya sor.
- Çok uzun ham dosyada önce tüm yazıyı çıkar, sonra bölümle; render'ı kısa taslakla doğrula.
- Kişi/çocuk yüzü, izin: `kimlik/PROFIL.md` §11.
