# Ses kütüphanesi: müzik ve ses efektleri (yerel, atıf gerektirmeyen)

Hepsi `sistem/varlik/varliklar.db` içinde kayıtlıdır (kaynak adresi, sha256 veya commit, lisans); **kurulum dosyaları kendisi indirir**, depoda ses dosyası yoktur. Durum: `python sistem/varlik/varlik.py durum --tur muzik` / `--tur sfx`. Yeni parça: `varlik.py ekle` (URL) ya da `ekle-yerel` (kendi parçan, bu bilgisayara özel).
**Kural:** atıf gerektiren (CC-BY, CC-BY-SA, "credit required") hiçbir şey alınmaz; yalnızca CC0, kamu malı, Pixabay/Mixkit türü atıfsız lisans. Lisansı **kaynak sayfasından** doğrula (bir sitenin "yapay zekâ için" yazdığı güven cümlelerine bakma).

## Müzik (`sistem/kit/muzik/`, 19 parça, İSTEĞE BAĞLI indirilir: Internet Archive Musopen CC0 + Wikimedia Commons kamu malı)
Lisans kaynakta doğrulandı: Chopin kayıtları Musopen 'Complete Chopin Collection' (CC0 1.0, archive.org); diğerleri Wikimedia Commons (AttributionRequired=false). Kit kurulu değilse müzik varmış gibi davranma: kullanıcıya söyle (panel → Müzik ve ses efektleri → İndir). Süreler 2-5 dk ve seviyeleri çok farklı (−13,6 ile −25,8 LUFS arası): **kullanmadan önce kırp, fade ekle, −14 LUFS kurguya göre normalize et, konuşma altında −12…−18 dB'e çek (ducking).**

| His | Parçalar (dosya adı `sistem/kit/muzik/…`) | Ne zaman |
|---|---|---|
| Sakin, güven, zarafet (solo piyano) | `chopin-nocturne-op-9-no-2`, `op-15-no-1`, `op-27-no-2`, `op-32-no-1`, `op-48-no-1`, `op-55-no-1`, `op-55-no-2`, `op-62-no-2`, `op-72-no-1`; sade/kısa: `chopin-prelude-op-28-no-15-raindrop`, `-no-7`, `-no-13` | seslendirmenin altında, mekân/işçilik/teslim; Reels dışında ana film |
| Çok sakin, boşluklu, minimal | `satie-gymnopedie-no-1…`, `no-3…` (flac) | açılış/kapanış, sessiz anlatım, yakın plan detay |
| Işıltılı, akıcı | `clair-de-lune-by-claude-debussy-1905-piano-solo` | ışık/doku sahneleri, "önce/sonra" geçişleri |
| Enerjik, canlı (oda orkestrası) | `modena-vivaldi-s-summer-rv-315-iii-presto`, `spring-rv-269-i-allegro`, `autumn-rv-293-i-allegro` | hızlı kesimli Reels/TikTok, açılış hook'u; konuşmayla çatışır, kıs |
Sınırlar: modern/elektronik/sinematik ambient parça yok (CC0/atıfsız bulunamadı). İstenirse kullanıcı Pixabay vb.'den indirip `ekle-yerel` ile kaydeder (lisansı kendi sorumluluğunda not düşer). Kimlik `zevk.md` hangi parçaların "sever/olmaz" olduğunu söyler: **önce oradan seç**.
Not: Chopin kayıtları archive.org'dan, Satie/Debussy/Vivaldi Wikimedia'dan iner; sunucu hız sınırı (429) uygularsa `varlik.py` kısa bekleyip o parçayı atlar, panel sonra yeniden dener. İndirme kendiliğinden başlamaz, kullanıcı panelden ister.

## Ses efektleri
1. **`sistem/kit/sfx-wyzowl/` (320 efekt, CC0, WAV 48 kHz/24 bit; kaynak: github.com/wyzowl/sfx-kit)** → asıl kütüphane. `GUIDE.md` (ekranda an → ses eşlemesi), `catalogue.md`, `sounds.json` (her ses için süre, senkron noktası, seviye, `under_voiceover_db`, ne için uygun/değil).
   - Bul: `python sistem/araclar/sfx_bul.py ara "title slam"`; kategoriler: `kategoriler`; ayrıntı: `bilgi <id>`.
   - Yerleştir: `sfx_bul.py yerlestir <id> --an <olay saniyesi> [--konusma]` → **başlangıç = olay − sync.at**, gain önerisi. Riser'ın senkron noktası SONUDUR (build → vuruş).
   - Hız uyumu: ses süresi hareketten %15 kısa / %20 uzun ise `adapt.rate` aralığında hız değiştir; daha fazlası için bir sonraki varyantı seç.
2. `sistem/kit/sfx/` (20 kısa efekt: Pixabay Content License, HyperFrames paketiyle gelir; `manifest.json`): whoosh/impact/riser/glitch/ui. Wyzowl yetmediğinde ya da bilinen sesleri (impact-bass, riser) tutarlı kullanmak için.

## Ses tasarımı ilkeleri (marka + önceki derslerden)
- Efekt **nedenli**: her geçişe değil; başlık çarpması, tepe geçiş, ana vurgu, kapanış. Premium videoda azlık = kalite.
- Konuşma önceliklidir: efekt konuşmanın üstüne binecekse `under_voiceover_db` kadar kıs, ya da konuşma boşluğuna koy.
- Kapanış: riser → vuruş → sönüş (ses "havada kalmasın"): `cinematic-drum-*`/`boom-*` + oda kuyruğu.
- Ölçü: `sistem/araclar/ses_olc.py`, `kalite_olc.py`: −14 ±1 LUFS, tepe ≤ −1 dBTP. **Duyamazsın**: sayısal ölç, doğallığı kullanıcı dinler.
