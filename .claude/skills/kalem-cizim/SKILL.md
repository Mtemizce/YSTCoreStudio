---
name: kalem-cizim
description: Kendi kendine çizilen kalem/eskiz tarzı video sahnesi üretir (parşömen, kara kalem ya da mavi teknik çizim; kâğıt üstünde kalemle kademeli çizilen plan, makine, nesne, diyagram). Kaynaktaki DWG/SVG çizimi kod yazmadan ara sahneye çevirir; başka konular için Paper.js sahnesi yazılır. "kalem çizimi", "kara kalem", "eskiz kendini çizsin", "DWG çizimini ara sahne yap", "çizerek anlat", "el çizimi animasyon", "defter/Leonardo tarzı çizim" dendiğinde kullan.
---

# Kalem çizimi: kendini çizen eskiz sahnesi

> Kaynak: github.com/leodavincs/kalem (MIT, © 2026 Leo): kalem çizim görünümü, şablon sahne (Leonardo ornitopter eskizi) ve yakalama sürücüsü. Lisans `sistem/kit/kalem/LICENSE-kalem.txt`, yazı tipleri OFL (`sistem/kit/kalem/ortak/font/OFL-*.txt`), Paper.js 0.16.0 (MIT). DWG/SVG dönüştürücü (`sistem/araclar/kalem_cizim.py`) ve genel çizim sayfası bu depoya özgüdür.
> **YEREL KURAL (YSTCore):** video `projeler/<ad>/kaynak/video/` altına yazılır ve Kurgu zaman çizelgesine normal video katmanı olarak girer. Yakalama başsız tarayıcıyı kurulumun Remotion `chrome-headless-shell`'inden alır; ağ, hesap, API anahtarı gerekmez. Yakalama sunucusu yalnızca `/ortak/`, `/node_modules/paper/` ve sahnenin kendi klasörünü sunar (yol kaçışı 404, testli).

## İki yol

### A. Kaynaktaki DWG / SVG çizimi → ara sahne (kod yazdırmadan, önerilen)

Kullanıcı panelde proje kartından **"🎞 Ara sahne ekle"** ile ya da yeni proje formundaki **Ara sahne** galerisinden stil seçer (parşömen / kara kalem / mavi teknik; önizleme görselleriyle). Yeni proje formundan seçildiyse `uretim.json` → `ara_sahne.stil` ve brief'te "ARA SAHNE İSTENDİ" notu olur: sen çalıştırırsın:

```
python sistem/araclar/kalem_cizim.py projeler/<ad>/kaynak/belge/<cizim.dwg|.svg> -o projeler/<ad>/kaynak/video/ara-sahne.mp4 --stil karakalem --sure 8
```

Akış: DWG → SVG (LibreDWG `dwg2SVG`, **yalnızca Windows'ta paketli**; başka sistemde çizimi SVG olarak ister) → çizgi/yay/eğri/daire düzleştirme → çizimin asıl bulunduğu kutuya yakınlaşma → 1920×1080'e oturtma → darbelere böl, önce uzun/ana çizgiler sonra ayrıntı → kalem sayfası kare kare çizer → mp4 (varsayılan 8 sn, 30 fps; ~30-60 sn sürer).

Sonra **mutlaka kontrol karelerine bak**: `ffmpeg -i <mp4> -vf "select='eq(n\,30)+eq(n\,120)+eq(n\,239)',scale=480:-1,tile=3x1" -frames:v 1 kontrol.png`. Videoyu uygun yere ara sahne olarak yerleştir (Kurgu'da video katmanı).

**Sınırlar (dürüstçe söyle):**
- Yazılar (`<text>`) ve blok eklemeleri (`<use>`) **çizilmez**; yalnız çizgi, yay, eğri, daire. Plan "tahmini bir anlatım görseli"dir; ölçü/ölçek iddiası için orijinal çizim esastır.
- Sayfa düzenli DWG'lerde (birkaç plan yan yana, uzak köşelerde nesneler, büyük daire/çerçeve) çizim sayfaya göre **küçük kalabilir**; çizimi tek plana kırpılmış bir SVG olarak istemek çok daha iyi sonuç verir.
- Çok yoğun çizimlerde (binlerce darbe) darbeler hızlı akar; süreyi uzat (`--sure 12`).

### A2. Herhangi bir resim ya da videonun ilk karesi → kalemle çiz → gerçeğe dön

Aynı hat DWG/SVG dışında **her resmi** (fotoğraf, çizim, render, video karesi) çizebilir: kenarlar çıkarılır (`kalem_resim.py`, ek bağımlılık yok), kalem onları kademeli çizer ve darbeler resmin üstünde **tam aynı hizada** durur; çizim bitince gerçek resim aynı yerde açılabilir.

```
# resmi çiz, 2 sn sonra bulanıklaşıp gerçek resme dönüşsün (çıktı: çizim + geçiş + 1,5 sn gerçek resim)
python sistem/araclar/kalem_cizim.py projeler/<ad>/kaynak/foto/<resim.jpg> -o projeler/<ad>/kaynak/video/ara-sahne.mp4 --stil karakalem --sure 8 --gecis --bekle 2
# yalnızca çizim (geçişsiz)
python sistem/araclar/kalem_cizim.py projeler/<ad>/kaynak/foto/<resim.jpg> -o ... --stil parsomen
# video girişi: videonun İLK KARESİ çizilir, --bekle sn sonra gerçeğe dönüşür ve video kesintisiz devam eder (çıktı: giriş + video, tek mp4, sesi korunur)
python sistem/araclar/kalem_cizim.py projeler/<ad>/kaynak/video/<klip.mp4> -o projeler/<ad>/kaynak/video/giris-klip.mp4 --stil karakalem --sure 6 --bekle 2
```

Panelde: proje kartı **"🎞 Ara sahne ekle"** → kaynak listesinde çizim, resim ve video birlikte gelir; resim seçilince "gerçek resme dönüşsün" kutusu ve bekleme süresi, video seçilince bekleme süresi çıkar.

Zemin rengi ve ton taraması:
```
# yeşilimsi zemin (arkada çimenlik varsa uyumlu geçiş): açık zeminde koyu, koyu zeminde açık çizgi otomatik seçilir
python sistem/araclar/kalem_cizim.py <resim.jpg> -o ... --stil karakalem --zemin "#DCE8D2" --gecis --bekle 2
# portre: konturlar sade (detay 0.5) + koyu yerler çapraz kalem taramasıyla gölgelenir (tarama 0.8, varsayılan)
python sistem/araclar/kalem_cizim.py <portre.jpg> -o ... --detay 0.5 --tarama 0.8
```
Panelde *Zemin rengi* listesi vardır (aydınlık, yeşilimsi, sıcak kâğıt, soğuk mavi-gri, karanlık, kendi rengi). Resimdeki **kırmızı gibi renkli düz yüzeyler** ton haritasında açık sayılır (değer kanalı ağırlıklı), bu yüzden bayrak gibi alanlar taranmaz, yalnızca konturlanır.

Bilmen gerekenler (dürüstçe söyle):
- Çizilen şey **kenar çizgileri ve ton taramasıdır**, renk değil: yüksek çözünürlüklü, kontrastlı resimlerde çok iyi; düşük kontrastlı/bulanık karelerde seyrek kalır (geçişle gerçek resme dönünce sorun olmaz).
- Resim 16:9 değilse tuvalde oran korunarak ortalanır; kenarlarda kâğıt görünür.
- Video girişinde video, tuvale oranı korunarak sığdırılır (kâğıt renginde dolgu); farklı oranlı videolarda yanlarda şerit olabilir.
- Geçiş için `gercek` resim sayfaya 1920 px genişliğe kadar yüklenir; bulanıklık/netlik yalnızca görsel geçiştir, gerçeği değiştirmez.

### B. Başka bir konu (el yapımı çizim): Paper.js şablon sahnesi

Çizim DWG/SVG değilse (makine, nesne, diyagram) sahneyi Paper.js ile **sen yazarsın**. Şablon: `sistem/kit/kalem/sablon/leonardo-ornitopter.html` (tam bir sahne: tüy kalem, kâğıt dokusu ve lekeleri, el yazısı notlar, kırmızı vurgu halkası, `olaylar.json` için darbe kareleri).

1. Şablonu `projeler/<ad>/kalem/sahne.html` olarak kopyala ve **oku**; kalem yardımcılarını (`cizgi`, `kiris`, `uzuv`, `cember`, `egri`, `faz`, `ilerle`, `kagitDoku`, kalem sprite'ı) olduğu gibi tut, yalnızca konuya özgü bölümü yaz: `G` geometri tablosu, `geometriKur()` içindeki `faz(...)` blokları, yazılar. Koordinatlar 1536×1024 referans düzlemindedir (`M(q)` ekrana taşır).
2. **Kara kalem varyantı:** dosyanın başındaki renkleri değiştir: `INK = "#1b1b1b"`, `SOLUK = "#5a5a5a"`, `KAGIT = "#f1efea"`, `<body style="background:#f1efea">`; kâğıt lekelerini (`kagitDoku` içindeki "foxing") azalt.
3. Önce kısa dene: `python sistem/kit/kalem/ortak/yakala.py projeler/<ad>/kalem/sahne.html projeler/<ad>/kalem/kareler --kare 24`. 60 sn sayfadan ses gelmezse sayfa yüklenmemiştir (çoğu zaman JS sözdizimi hatası; konsol `[sayfa] HATA ...` olarak basılır).
4. Tam yakala ve mp4 yap:
   ```
   python sistem/kit/kalem/ortak/yakala.py projeler/<ad>/kalem/sahne.html projeler/<ad>/kalem/kareler
   ffmpeg -y -framerate 30 -i projeler/<ad>/kalem/kareler/%04d.png -c:v libx264 -pix_fmt yuv420p -crf 16 projeler/<ad>/kaynak/video/kalem-sahne.mp4
   ```
   240 kare tipik bir bilgisayarda ~30 sn sürer; `kareler/` (≈200 MB geçici PNG) işi bitince silinir (yalnızca `NNNN.png` içeren klasörü yakalayıcı siler, başka dosya görürse durur).
5. Kontrol: ilk kare dolu (ilk darbe 0. karede başlamış), yazı/çizgi taşmıyor, son ~15 kare sakin. Çizgi sesleri için `OLAYLAR` satırındaki kareleri `sistem/araclar/sfx_bul.py` ile eşle.

Yeni bir konunun geometrisini yazmak emek ister (bir sahne ~1-2 saat model emeği) ve sonucu **görsel olarak kontrol etmeden "güzel" denmez**.

## Genel notlar

- Başsız tarayıcı bulunamazsa: kurulumu tamamla (Remotion `chrome-headless-shell` iner) ya da `CHROME=<chrome yolu>` ver.
- DWG okuma yalnızca Windows'ta çalışır; SVG ve resim kaynakları her sistemde aynı kod yoluyla çalışır.
- Üçüncü taraf motorlar (PixiJS, Three.js, Manim, "levha") bu kuruluma alınmadı; levha motoru ayrıca OpenCV ve Codex görsel üretimi ister. Bkz. `kurgu-video-studio/references/sahne-motoru-secimi.md`.
- Testler: `sistem/testler/test_kalem_cizim.py` (donanımsız), `canli_kalem_cizim.py` (tarayıcıyla).
