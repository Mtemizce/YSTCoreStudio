---
name: sosyal-surumler
description: "Bitmiş ya da planlanan bir videodan TikTok, Instagram Reels ve YouTube Shorts sürümlerini üretir: platforma özgü kompozisyon (dikey yeniden kurgu, hook, güvenli alan, altyazı), süre, ses seviyesi, kapak karesi, açıklama/etiket metni. Yeniden çerçeveleme değil YENİDEN KOMPOZİSYON esastır. \"reels yap\", \"tiktok için kes\", \"shorts\", \"dikey sürüm\", \"platformlara uyarla\" ve /sosyal isteklerinde kullan."
---

# Sosyal sürümler (TikTok · Reels · Shorts)

## Temel ilke: kırpma değil **yeniden kompozisyon**
16:9 filmi 9:16'ya kırpmak ya da bulanık zemine yapıştırmak, ekranın ortasında küçük bir şerit bırakır; bu açıkça "slop" görünümüdür (`sistem/araclar/platform_cikti.py --mod blur` ile üretilir). Doğru yol:
1. **Aynı malzemeden**, dikey için **yeniden kurgula**: yeni hikâye akışı (hook önde), yeni sahneler (kit `useFormat()` ile format-bilinçli), yeni altyazı, yeni süre.
2. **Kalite sınıfına göre düzen** (envanter): düşük çözünürlüklü yatay fotoğraf → tam genişlik **bant** (~1× ölçek, keskin kalır); yüksek çözünürlüklü (≥ ~1900 px yükseklik) → **tam ekran** dikey (özne odağı `focus`). Yatay fotoğrafı tam ekran kırpmak = ~4× büyütme = bulanık.
3. Ham **video** kaynağı varsa (konuşan kafa vb.): `platform_cikti.py --mod kirp --x <özne konumu>` ya da `blur` yalnızca geçici/yedek; konuşma yüzünün üstü alt arayüze girmemeli.
Örnek yaklaşım: yerel dikey kompozisyon, sesin parça zamanlarına bağlı sahneler, kelime-vurgulu altyazı (`sistem/kit/src/Captions.tsx`).

## Dolu kadraj ve hook (kullanıcı geri bildirimi, uygulandı)
- **Alt boşluk yok:** dikeyde ana fotoğraflar üst/alt yarım paneller (her biri 1080×960; düşük çözünürlük ~1× ölçekte keskin kalır) olarak tüm ekranı doldurur; yüksek çözünürlük tam ekran; kapanış kartı bile arka planda koyulaştırılmış fotoğraf taşır. Altyazı alt arayüzün üstünde (y≈%64) **koyu yumuşak bant** üzerinde.
- **Hook = 4 kelimelik büyük başlık**, rengi anlam taşır ("ÖNCE ŞANTİYE, SONRA HİKÂYE": şantiye sönük + üstü çizili, hikâye altın), kelimeler **seste söylendiği anda** iner; başlık kelimeleri sonra etiketlere geri döner (cohesion). Altyazı hook'ta susar (başlık altyazıdır).
- Dikey sürüm aynı proje klasöründe kendi Kurgu projesi olarak açılır (`projeler/<ad>/reels/`, `tiktok/`, `shorts/`: `python sistem/araclar/yeni_proje.py <ad> --format reels`); bitince render `projeler/<ad>/cikti/` altına kopyalanır.

## Platform çerçevesi (DOĞRULAMA DURUMU: kaynaklar birbiriyle çelişiyor; **uygulamada/yükleme ekranında kontrol et**)
| Konu | Güvenle kullanılan değer | Not |
|---|---|---|
| Tuval | 1080×1920 (9:16), H.264 MP4, AAC, 30 fps | üçü için ortak; 60 fps zorunlu değil |
| Güvenli alan (metin/özne) | sol 120 · sağ 192 · üst 288 · alt 672 px boşluk | **Konservatif birleşik kutu**; kaynaklar: Google Shorts reklam şablonu (üst 288/alt 672/sol 48/sağ 192), TikTok reklam şablonu (üst ~240/alt ~660/yan 120), Meta Reels yüzdeleri (üst %14/alt %35/yan %6 ≈ 269/672/65). Organik Shorts için resmî ayrı değer yok. Arka plan görüntü tam ekran olabilir. |
| Alt arayüz | alt ≈ 660-680 px kullanıcı adı/açıklama/ses satırı kaplar | altyazıyı ≈ %60-64 yüksekliğe koy (kare 1920: y≈1150-1230) |
| Sağ sütun | beğeni/yorum/paylaş düğmeleri | önemli yazıyı sağ kenara dayama |
| Süre (hedef) | Reels 20-35 sn · TikTok 20-35 sn · Shorts 20-45 sn | **üst sınırlar kaynaklarda çelişkili** (Shorts: 60 sn eski / 3 dk yeni; TikTok: 10 dk yaygın, hesaba göre değişir; Reels: yükleme uzun olabilir, öneri ≤ 3 dk). Hedef sayılar tasarım tercihi; sınırlar app'te doğrulanır |
| Ses | ≈ −14 LUFS, tepe ≤ −1 dBTP | yaygın uygulama (YouTube −14'e normalize eder); TikTok/Reels için resmî değer doğrulanmadı |
| Altyazı | her zaman (sessiz izleme) | yerel: kelime-vurgulu; Türkçe senaryodan |
| Kapak | Reels/TikTok profil ızgarası kırpar (3:4/ortada); Shorts kapak ayrı | kapak karesini **orta bant**ta güvenli tasarla; `ffmpeg -ss <t>` ile çıkar |
Resmî kaynaklara bak: TikTok Ads Manager güvenli alan dosyası, Meta Reels önerileri, Google Ads dikey video spesifikasyonu. Bu tablo yaş kazanır: yılda bir doğrula.

## Hook (ilk 3 sn) ve yapı (pazarlama blogu tabanlı bulgular: **sayısal iddialar doğrulanmadı**, sezgisel kural olarak kullan)
- 0-3 sn: görsel/hareket + net vaat; **ilk cümle 3 sn'yi geçmesin**. 3-5 sn: söz verilen şeyin netleşmesi. Orta: kanıt/akış. Son: kısa CTA (profil §7).
- Altyazı ilk 3 sn'de **hareket etsin** (kelime vurgusu); kapakta ve hook'ta 2-4 kelime. Açılış çekiminde "önce/sonra", "şaşırtıcı tek gerçek", rakam (yalnız doğruysa), soru. Aç/kapa döngüsü: sonu başa bağla (Shorts döngüsü).
- Ayrıntı: `hook-ve-kapak`.
- İzleyici 10-15 sn'de düşüyorsa hook çalışmış, gövde vaadi karşılamamıştır: gövdeyi kısalt.

## Platform farkları (ton; profil §10 ile)
| | TikTok | Instagram Reels | YouTube Shorts |
|---|---|---|---|
| Ritim | en hızlı, ham/samimi his, kısa cümle | cilalı görsel, estetik, kapak önemli | bilgi/değer odaklı, döngü, başlık aranabilir |
| Dil | konuşma dili | marka sesi, hafif cilalı | net, anahtar kelime başlıkta |
| Metin | kısa, çok kısa başlık + etiketler | başlık + 3-5 etiket | başlık (anahtar kelime ilk) + açıklama |
| Müzik | trend ses yerine telifsiz yerel parça (marka hesabı lisansı) | telifsiz/lisanslı | YouTube ses kütüphanesi ya da telifsiz |
Marka hesapları için ticari müzik lisansı gerekir: yalnızca lisansı kayıtlı/telifsiz parça.

## Üretim akışı
1. **Hikâye tahtası (dikey):** hook → ana fikir(ler) → kanıt → imza/CTA. Ana filmden **en güçlü 2-3 an** (hepsini sığdırma). `senarist` ajanı ile.
2. **Ses:** yeni (kısa) anlatım `voice_studio.py` ile, `plan.json` parça sınırları = sahne sınırları ("ses saattir"). Süre 15-35 sn.
3. **Zamanlama:** `rapor.json` parça başlangıçları → sahne sabitleri (`T = {...}` bkz. `Reels.tsx`).
4. **Altyazı:** METİN senaryodan, zaman parça sınırlarından: `sistem/araclar/altyazi_hizala.py` (konuşma tanıma özel adları bozar; yalnızca doğrulama için kullan). Remotion `Captions` (kit) → kelime vurgusu, cümle sonunda biter, dengeli satır.
5. **Sahne:** `sistem/kit/src` (`useFormat`, `Photo`, `Captions`…), proje `<format>/remotion/src/<Ad>.tsx`; kompozisyon 1080×1920. `still` ile kontrol.
6. **Montaj:** `projeler/<ad>/<platform>/project.json` (Kurgu 1080×1920, fps 30, `global.loudness_lufs -14`, `fade_out 0.6`), ses + müzik (`volume_db` konuşmanın ≥ 12 dB altında).
7. **Ölçüm:** `python sistem/araclar/kalite_olc.py <mp4> --platform reels|tiktok|shorts` (çözünürlük, süre, LUFS/tepe, donmuş/siyah kare). Sonra **`elestirmen`** ajanı.
8. **Kapak + metin:** `ffmpeg -ss … -frames:v 1` ya da `platform_cikti.py --kapak`; `paylasim_<platform>.md`: başlık, açıklama, etiketler (profil dili/tonu; doğrulanmamış iddia yok; CTA profil §7).
9. Üç platform çoğu kez **aynı dikey ana kurgu** + küçük farklar (kapak, metin, uzunluk, müzik lisansı) olur; yalnızca ton gerçekten farklıysa ayrı kurgu yap.

## Kalite kapısı (sosyal)
- [ ] İlk 3 sn'de açık fikir + hareket; sessiz izlenince anlaşılıyor
- [ ] Metin/özne güvenli kutuda; altyazı okunuyor (arkası karartılı), taşma yok, iki cümle karışmıyor
- [ ] Marka adı altyazıda doğru yazılmış (senaryodan)
- [ ] −14 ±1 LUFS, tepe ≤ −1 dBTP, 1080×1920, 30 fps, yuv420p
- [ ] Doğrulanmamış iddia yok; kişi/çocuk izinleri
- [ ] Kapak karesi güvenli bantta; sonun başa bağlanması düşünülmüş
- [ ] `kalite_olc.py` bayrakları açıklandı (bilerek durağan kart ise not)

## Araçlar
`sistem/araclar/medya_envanteri.py` · `yazi_cikar.py` (yerel konuşma→yazı, kelime zamanlı) · `altyazi_hizala.py` · `platform_cikti.py` (ham video için: kırp/blur/kopya + ASS altyazı + −14 LUFS + kapak) · `kalite_olc.py` · `sessizlik_kes.py` · `kurgu-video-studio/scripts/voice_studio.py`, `enhance_image.py`.
