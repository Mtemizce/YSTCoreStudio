# YSTCoreStudio: video stüdyosu (yerel), giriş noktası

Bu klasör, kullanıcının **varsayılan olarak tamamen yerelde** çalışan video stüdyosudur. Harici program (After Effects, Premiere, Resolve…), hesap ve telemetri yoktur. Ücretli bulut servisleri (ElevenLabs, Gemini/OpenAI görsel, HeyGen MCP…) yalnızca kullanıcı **açıkça etkinleştirirse** kullanılır (aşağıda YEREL KURAL).
Yığın: **Kurgu** (zaman çizelgesi + editör, `kurgu/`) · **Remotion** (React sahneleri) · **HyperFrames** (HTML+GSAP sahneleri) · **ffmpeg** · **EMA Lightning** (yerel Türkçe TTS, `sistem/tts/` adaptörü) · **Real-ESRGAN** (foto iyileştirme) · **faster-whisper** (yerel konuşma→yazı) · **LibreDWG** (DWG→görsel).

## Kullanıcı ne yapar?
`Başlat.cmd` çift tıkla → tarayıcıda **stüdyo paneli**: tek ekranlı **Yeni video** (prompt: yazarak ya da 🎤 konuşarak; seslendirme + sağlayıcı; görseli üret + karakter tarifi; süre; platformlar; marka kiti + intro/outro/filigran/iletişim; arşivden bul; kaynak yükle) → **Üret** → Claude penceresi `/video` akışını başlatır, taslak hazır olunca panel **taslak hazır** der → **Kurgu'da aç** (saniye bazlı not) → **Onaylıyorum** → `/final` (final render + platform sürümleri). **Ayarlar** sekmesi: ajan model/effort (genel ve proje bazlı), bağlayıcılar, MCP, marka kitleri.
Sistem: `kimlik/PROFIL.md` (kim olduğu) + `kimlik/MARKA.md` (kilitli görsel kimlik) + brief + kaynakları analiz eder → ana film (16:9) → TikTok / Reels / Shorts dikey sürümleri.

## Klasör düzeni (kök dizin bilerek sade)
```
Başlat.cmd, README.md      başlatıcı (sessiz: sistem analizi + gerekirse kurulum sihirbazı + panel; "Başlat.cmd claude" = elle Claude) ve kullanım
kimlik/                    PROFIL.md (beyan) + MARKA.md (görsel kimlik) + ornekler/ (gerçek yazı/ses örnekleri) + ses_profili.md (ölçülen tarz) + zevk.md (A/B testi) + ogrenilenler.md (proje sonrası kurallar)
projeler/<ad>/             her video bir proje
   kaynak/{foto,video,ses,belge}   kullanıcının orijinalleri (dokunulmaz)
   hazir/                          kaynaklardan türeyenler: envanter + kontak sayfası, belge çıktıları (DWG→PNG, PDF→PNG+md, Word→md, Excel→csv)
   ana/  reels/  tiktok/  shorts/  her biri bir Kurgu projesi (project.json, media/, remotion/, ses/, cikti/ = o biçimin render'ı)
   cikti/                          TESLİM: bitmiş videolar + kapaklar + paylaşım metinleri
   brief.md                        yaratıcı özet
kurgu/                     Kurgu (kurulumla gelir; kendi deposu + yama; elle düzenleme: sistem/yama/kurgu/ ve eklenti sistem/yama/kurgu_ek/ altında, bkz. sistem/kurulum/kurgu_yama.py)
sistem/                    stüdyonun makinesi
   araclar/ kit/ sablon/ tts/ varlik/ kurulum/ yama/ panel/
   ortam/                  kurulumun ürettikleri (venv, modeller, kurgu-ayar, yerel önbellek): git'e girmez
GİZLİ (Gezgin'de "Gizli öğeleri göster" ile görünür; teknik zorunluluk): .claude/ (ajanlar, komutlar, skill'ler, bu dosya) · .mcp.json · node_modules/ + package.json (Remotion paketleri; Node, paketleri üst klasörlerde arar) · .git*
```
Kurulumla gelenler (depoda YOK): `kurgu/`, `node_modules/`, `sistem/ortam/`, `sistem/araclar/dis/` (LibreDWG), `sistem/kit/sfx`, `sistem/kit/referans`, üçüncü taraf skill'ler. `python sistem/kurulum/kurulum.py --kontrol` durumu söyler.

## Komutlar
- `/video <tarif | projeler/<ad>>`: uçtan uca üretim (skill: `video-yonetmen`). Panelden açılan proje için brief/kaynaklar hazırdır.
- `/final projeler/<ad>`: panelde **Onaylıyorum** sonrası final render, eleştirmen, platform sürümleri, teslim (durum: `sistem/araclar/durum.py`)
- `/b-plani projeler/<ad>`: **B planı (acil durum)**: kişi çekime gidemedi; gerçek mekân görüntüleri + dijital sunucu (yerel/kodla; isteğe bağlı üretken ikiz). Panelde Yeni video → "B planı" ya da proje kartı → B planı
- `/arsiv-analiz [yıl] [proje]`: arşiv fotoğraflarını bir kez anlamlandırıp veritabanına yazar (`sistem/arsiv/analiz.py`); sonraki videolar taramasız bu veriden seçer
- `/sosyal <proje> [platformlar]`: bitmiş projeden platform sürümleri (skill: `sosyal-surumler`)
- `/profil`: `kimlik/PROFIL.md` analizi, eksik soruları sor, ton özeti (skill: `kisilik-ve-ton`)
- `/saglik`: ortam + ajan + skill sağlık kontrolü (`sistem/araclar/saglik.py`)

## Ajanlar (`.claude/agents/`, her çağrıda `model:` açık)
`senarist` · `redaktor` · `sahne-yapimcisi` (sahne başına paralel) · `ses-yonetmeni` · `gorsel-iyilestirici` · `gorsel-uretici` (bulut, isteğe bağlı) · `arsiv-analisti` · `sosyal-kesici` · **`elestirmen` (bağımsız; üretici kendini puanlamaz)**. Model ve effort **kullanıcı ayarıdır** (panel → Ayarlar; `sistem/ayar/`): her Agent çağrısında `python sistem/ayar/ayar.py ajan <ajan> <proje>` çıktısı açıkça verilir, varsayılanlar `sistem/ayar/varsayilan.json`'dadır.
Ana oturum yönetmen/orkestratördür: plan yazar, ajanları yönlendirir, sonucu sentezler. Ajan raporu bir **iddiadır**: kareye/ölçüme bak. Ajanların çalışıp çalışmadığı: `sistem/araclar/saglik.py` (statik), `--canli` (her ajanı gerçekten çağırır), `--proje <ad>` (üretim izleri: hangi aşama dosya bıraktı). Ajan/skill/komut dosyalarında `description` değerinde `: ` varsa değeri çift tırnağa al (aksi halde Claude tanımı sessizce reddeder).

## Skill'ler (`.claude/skills/`)
Yerel (bu stüdyo için yazıldı): `video-yonetmen` · `kisilik-ve-ton` · `marka-kilidi` · `kaba-kurgu` · `sosyal-surumler` · `hook-ve-kapak` · `kurgu-video-studio` (teknik zanaat: geçişler, efektler, görsel iyileştirme, seslendirme, ses tasarımı, Kurgu boru hattı).
Üçüncü taraf (kurulumda KENDİ depolarından çekilir, bizim yama üzerine uygulanır; `.claude/skills/THIRD_PARTY_NOTICES.md`): `remotion-best-practices` · `hyperframes`, `hyperframes-cli` · `business-motion-film` · `hyperframes-video-director` (yalnızca belgeler) · `frontend-design` (Anthropic) · `kalem-cizim` (kalem, MIT; DWG/SVG çizimini kalemle çizilen ara sahne videosuna çevirir: `python sistem/araclar/kalem_cizim.py <çizim> -o <mp4> --stil parsomen|karakalem|teknik`; panelde proje kartı *Ara sahne ekle* ve yeni proje formunda stil galerisi; yeni proje formundan seçildiyse `uretim.json` → `ara_sahne.stil` ve brief'te "ARA SAHNE İSTENDİ" notu olur, sen çalıştırırsın) · `referans` (kalem, MIT; `/referans <video>`: videoyu sahnelere bölüp her sahne için video istemi çıkarır, çıktı `referanslar/<ad>/`; betikleri okundu, depoda tutulur). Sahne bazlı araç seçimi: `kurgu-video-studio/references/sahne-motoru-secimi.md`.

## YEREL KURAL (sert)
- **Ücretli/bulut çağrıları tek arayüzden:** `python sistem/baglayici/yetenek.py cagir --yetenek <gorsel-uret|gorsel-duzenle|video-uret|avatar-video|tts|…> --girdi '{...}' --cikti <yol> [--proje <ad>] [--onay]` (sıradaki hazır sağlayıcıyı kendisi seçer, yedek zincirini, bütçe tavanını ve izni uygular; çıkış kodu 7 = bütçe). Hangi servisin/modelin kullanılacağına SEN karar verme (model adı da elle yazılmaz: kullanıcı servisin kendi listesinden seçer, `python sistem/baglayici/kesif.py liste <sağlayıcı>`): kullanıcının Ayarlar'da tanımladığı sıra geçerlidir; sağlayıcı yoksa kullanıcıya söyle. `yetenek.py liste` hazır olanları gösterir.
- **Üretimde internetten materyal yok:** foto, video, ses, müzik, logo, metin ya da "referans" için internette ARAMA ve İNDİRME yapma (bu klasörde `WebSearch` ve `WebFetch` `.claude/settings.json` ile engelli; kabuk/Python ile aynı işi dolaşarak yapma). Girdi yalnızca: `projeler/<ad>/kaynak/` (kullanıcının verdikleri), kullanıcının arşivi (yerel/harici disk, salt okunur) ve stüdyonun yerel araçları (kodla sahne, EMA/Pocket TTS, Real-ESRGAN, kalemle çizim, panelden indirilen CC0 müzik ve ses efektleri). Bir kaynak eksikse **kullanıcıya sor** ya da yerelde (kodla) üret; "internetten bulurum" deme, uydurma. Kurulumdaki model/paket indirmesi bundan ayrıdır.
- Telemetri/hesap **yok**: `npx hyperframes auth|cloud|publish|share|events|feedback|billing|media-use|skills …` yasak (`.claude/settings.json` ile de engelli). Model ağırlığı indirmeleri yalnızca kurulumda, yalnızca dosya.
- **Ücretli bulut servisleri VARSAYILAN KAPALI, yalnızca isteğe bağlı** : bağlayıcı **etkin** + **API anahtarı** (yalnızca `sistem/ortam/baglayici/`, git'e girmez, panelde geri gösterilmez) + projede **bulut izni** (`ayar.json`) üçü birlikte gerekir; ağa yalnızca `python sistem/baglayici/uret.py …` ile çık, anahtara doğrudan dokunma. Her çağrı `projeler/<ad>/bulut_gunlugu.md`'ye yazılır. Kaynak fotoğraflar buluta gönderilmez (ayar açmadıkça). İzin ya da anahtar yoksa sessizce yerele düşme: eksiği söyle. Ses (konuşma/dikte) hiçbir zaman buluta gitmez: yerel faster-whisper.
- Orijinal kaynaklara (`projeler/<ad>/kaynak/`) **dokunma**; kopya üzerinde çalış.
- İndirilmiş çalıştırılabilir (.exe) dosyaları kullanıcı onayı olmadan çalıştırma. Kurgu kullanıcı config'inde (`sistem/ortam/kurgu-ayar/config.json`) güven/izin (`render_trusted_roots`, `render_adaptors`) değişikliği **kullanıcı kararıdır**: ajan yapmaz.
- Headless "Gönder" uyanma modu yalnızca `kurgu notes|frame|strip|rerender|detect|probe` + `mcp__kurgu__*` kullanır (python/npm/ffmpeg yok): üretim işleri interaktif oturumda.
- Atıf gerektiren lisanslı (CC-BY vb.) motoru yalnızca kullanıcı onayladıysa ekle (Pocket TTS Turkish onaylandı: atıf README + panel + ATIF.txt). Yeni TTS motoru = `sistem/tts/` adaptörü; lisansı kontrol et.

## Sert içerik kuralları
Doğrulanmamış iddia yok (yıl, adet, ödül, telefon, "en iyi") · uydurma müşteri/yorum yok · logo/maskot uydurma yok · kişi/çocuk izinleri `kimlik/PROFIL.md` §11 · filigran silinmez · okunur yazı/logo yapay zekâyla yeniden çizilmez · AI iyileştirilmiş görüntü kanıt gibi sunulmaz · müzik lisansı kaydedilir.

## Araçlar (`sistem/araclar/`)
`yeni_proje.py` (proje + kaynak kopyalama + hazırlık + sihirbaz cevapları) · `guncelleme.py` (GitHub güncellemesi: yedek + çek + yerleştir + onar) · `kurgu_gomulu.py` (Kurgu'yu panel içinde iframe'de açar) · `yerel_gorsel.py` (isteğe bağlı Z-Image-Turbo, sd.cpp) · `bulut_disk.py` (rclone: Drive/OneDrive/Dropbox arşiv kaynağı, salt okunur, önbellekli) · `ajan_cagir.py` (bir ajan rolünü seçili CLI ortamında çalıştırır) · `mekan_gezisi.py` (kodla derinlikli mekân gezisi + sunucu penceresi + etiket) · `karakter.py` (dijital ikiz: rızalı karakter paketi) · `seri.py` (dizi/sezon/bölüm + süreklilik bağlamı) · `ses_temizle.py` (gürültü/boşluk/seviye) · `klon_olc.py` (ses klonlama örneği kalite ölçütleri ve klon denemesi; engellemez, bilgi verir) · `sistem/testler/` (testler + `calistir.py`) · `depolama.py` (rclone + storage.to; yazma/paylaşma açık onaylı) · `konum.py` (kök/yol çözümleme, taşıma denetimi) · `profil.py` (ayar/anahtar/kimlik/arşiv dizini dışa-içe aktarma; şifreli tek JSON) · `arsiv.py`, `analiz.py`, `iyilestir.py` (`sistem/arsiv/`) · `sistem/kurulum/` (`baslat.py`, `onkosul.py`, `sihirbaz.py`, `onar.py`, `kurulum.py`) · `kimlik_olc.py` · `ses_profili.py` · `sfx_bul.py` · `medya_envanteri.py` · `belge_al.py` (DWG/PDF/Word/Excel alımı) · `yazi_cikar.py` · `altyazi_hizala.py` · `sessizlik_kes.py` · `platform_cikti.py` · `kalite_olc.py` · `ses_olc.py` (perde/sönüş ölçümü) · `skill_tara.py` (güvenlik tarayıcısı) · `saglik.py`. Python: `sistem/ortam/venv/Scripts/python.exe` (Başlat.cmd PATH'e ekler; `PYTHONUTF8=1`).

## Ses
Yerel Türkçe motorlar: **EMA Lightning** (`ema`, varsayılan): kontrol = `hiz` + `seed`, duygu/ses seçimi yok. **Pocket TTS Turkish** (`pocket-tr`, CC-BY-4.0 atıflı): `ses` (female_1..3, male_1..3), `duygu` (mutlu, üzgün, kızgın, şaşkın, sakin) ve SES KLONLAMA: plan'da `"klon": "klon/ornek.wav"` (proje klasörüne göre yol). Kullanıcı panelde "Sesimi klonla"yı seçip uyarıyı kabul ettiyse `uretim.json` → `seslendirme` içinde `klon: true` (+ `klon_yol`, `klon_onay` zamanı) olur ve örnek ses projeye `klon/ornek.wav` diye kopyalanır: seslendirme planına `"motor": "pocket-tr", "klon": "klon/ornek.wav"` koy; onay panelde alındı, kullanıcıya tekrar sorma. Örnek ses 3-10 sn temiz tek kişi olmalı. `voice_studio.py` (`.claude/skills/kurgu-video-studio/scripts/`) parçalı yönlendirme, `--aday 5` ile cümle sonu tonu seçimi, ses işleme, doğal bitiş (sönüş + kuyruk) yapar. **Sesi dinleyemezsin**: kullanıcı dinler. Yeni motor eklemek: `sistem/tts/__init__.py` başındaki yönergeler.
Müzik/SFX/model kaydı: `sistem/varlik/varliklar.db` (SQLite; `python sistem/varlik/varlik.py liste|durum|indir|ekle`). İndirdiğin her müzik/ses `ekle` ile kaydedilmeli (URL + lisans): başka bilgisayardaki kurulum onu otomatik indirir.

## Kimlik katmanları (kullanıcıyı anlamak: beyan tek başına yetmez)
1. **Beyan** `kimlik/PROFIL.md` (§15 doğrulanmış gerçekler, §16 telaffuz ve çalışma tercihi, §17 anlatı soruları dahil) · 2. **Kanıt** `kimlik/ornekler/` + `ses_profili.md` (`sistem/araclar/ses_profili.py`: gerçek yazı/ses → ritim, hitap, dolgu sözcük, örnek cümleler) · 3. **Zevk** `zevk.md` (panel → Kimlik → Zevk testi: aynı mesaj iki üslup + müzik dinle) · 4. **Öğrenme** `ogrenilenler.md` (her proje sonrası kural, kullanıcı onayıyla).
Çelişkide: kullanıcının sözü > ölçüm > beyan. Doluluk: `python sistem/araclar/kimlik_olc.py`. Eksik katmanı yönetmene bir kez söyle, varsayımla ilerle ve işaretle.

## Orkestrasyon (SEN yönetmensin)
Ağır üretimi alt ajanlara ver, **her teslimi kendin doğrula**, kararı sen al; her devri `projeler/<ad>/calisma_gunlugu.md`'ye işle. Görev paketi, doğrulama listesi, paralellik, durma kuralları ve öğrenme döngüsü: `.claude/skills/video-yonetmen/orkestrasyon.md`. `saglik.py --proje <ad>` günlük ve çıktı izlerini kontrol eder.

## Taşınabilirlik kuralı (sert)
**Tek klasör:** stüdyonun indirdiği ya da önbelleğe aldığı hiçbir şey klasör dışına (AppData, `~/.cache`, Belgeler) yazılmaz; silmek için klasörü silmek yeter. Yeni bir araç/model indiriyorsan önbellek yolunu `sistem/araclar/yol.py` → `kapsama()` ortam değişkenlerine bağla (ya da aracın kendi `--cache-dir`/`*_HOME` ayarını klasöre ver) ve `sistem/testler/test_kapsama.py` ile doğrula. Kaldırma/artık listesi: `python sistem/kurulum/kaldir.py`.
Klasör her an başka bir yola/bilgisayara kopyalanabilir. **Hiçbir yere mutlak yol yazma**: veritabanı, proje dosyaları, ayar ve rapor dosyalarında yalnızca **göreli yol** (stüdyo köküne ya da arşiv köküne göre). Arşiv dosyası = (`kok_id`, göreli `yol`); mutlak yol yalnızca çalışırken `arsiv.mutlak(c, kok_id, yol)` / `konum.py` ile çözülür. Betiklerde kökü `Path(__file__).resolve().parents[…]` ile bul; `C:\Users\…` yazma. Taşıma onarımı `sistem/kurulum/onar.py`, yol çözümleme ve denetim `sistem/araclar/konum.py` (`python sistem/araclar/konum.py durum|denetle`).

## Arşiv (harici disk, ~1 TB)
`python sistem/arsiv/arsiv.py ayarla <yol> [--ad arsiv]` (çok arşiv: farklı ad; `kokler` ile bağlantı durumu) → `tara` (yalnızca OKUR; dizin `sistem/ortam/arsiv/`, git'e girmez; artımlı, kesilirse devam eder; disk başka harfle takılırsa birim seri no ile bulunur) → `projeler --yil 2013-2016 --kelime "villa cephe"` / `ara`. Seçim projeye **kopyalanır** (`kaynak/arsiv_secim.json` ile izlenir; fotoğrafın iyileştirilmiş sürümü varsa o kopyalanır). Düşük puanlı fotoğrafı iyileştirmek için kullanıcıya panelde Arşiv → "Düşük puanlı fotoğrafları iyileştir"i göster ya da `python sistem/arsiv/iyilestir.py adaylar|calistir` (model: Ayarlar → İşler ve modeller; bulut modeli yalnızca kullanıcı o işlem için onay verirse, fotoğraf servise gider). Panel: Yeni proje → Kaynak → "Arşivden seç". Tarih önceliği: EXIF > dosya adı > klasör yılı > değişiklik tarihi. Arşive ASLA yazma/silme/taşıma.

**Kategoriler:** Resim (`foto`) · Video · Müzik (`ses`: müzik, kayıt, ses efekti) · Dosya (`belge`: çizim, PDF, Word, Excel…). `--tur` Türkçe adları da kabul eder (`resim|muzik|dosya|video`). Kullanıcı kendi müzik/ses/resim/video/dosya klasörünü **ayrı bir arşiv** olarak ekleyebilir (panel → Ayarlar → Arşiv, ya da `arsiv.py ayarla <klasör> --ad muzik` + `tara`); panelde Arşiv kütüphanesi kategorilere göre listeler, müziği dinletir, adını prompt'a ekler.
**Prompt'ta adı geçen dosya (SEN yaparsın):** kullanıcı "şu müziği kullan", `arka planda "Tarkan - Şımarık" çalsın`, "kapak.png'yi koy" gibi bir ad verirse tahmin etme, kit müziğine düşme: `python sistem/arsiv/arsiv.py bul "<ad>" --tur muzik --kopyala projeler/<ad>` (resim/video/dosya için `--tur resim|video|dosya`). Çıkış 0 = tek net eşleşme projeye kopyalandı (`kaynak/ses/…`; kayıt `kaynak/arsiv_secim.json` → `kullanici_dosyalari`); 3 = belirsiz ya da yok: adayları kullanıcıya göster ve sor (`--id` ile seç), uydurma. Dosya kullanıcının kendisinindir (lisans/telif onun sorumluluğunda); arşive yazılmaz. Dosya adı farklıysa başlık/sanatçı etiketlerinden de bulunur.

## Ses ve müzik kütüphanesi
`sistem/varlik/varliklar.db` (kaynak, sha256/commit, lisans): **320 CC0 ses efekti** (`sistem/kit/sfx-wyzowl`, `sistem/araclar/sfx_bul.py`) + **atıfsız müzik** (`sistem/kit/muzik`) + Pixabay efektleri. **İsteğe bağlıdır:** kurulumla gelmez, kendiliğinden de inmez; kullanıcı panelde (pano önerisi ya da Ayarlar → Sistem → Müzik ve ses efektleri) **İndir** derse iner (`python sistem/araclar/arka_indirme.py ses`). Önce kullanıcının kendi arşivi ve prompt'ta verdiği adlar (yukarıdaki `arsiv.py bul`); kit yalnızca onlar yoksa. Kit yoksa müzik/ses efekti varmış gibi davranma: kullanıcıya söyle ve indirmesini öner (ya da müziksiz/sfx'siz ilerle). Kullanım ve seçim: `.claude/skills/kurgu-video-studio/references/ses-kutuphanesi.md`. Atıf gerektiren hiçbir şey alınmaz.

## Shader geçişleri ("özel efekt")
227 hazır geçiş (`gl-transitions`) Remotion'da `gecis('FilmDissolve')` ile; seçim ve marka kuralı: `.claude/skills/kurgu-video-studio/references/gl-gecisler.md`. Kontrolü geçişin ortasında `remotion still` ile yap.

## Üçüncü taraf skill/repo alma politikası
1) Çin menşeli/CJK ağırlıklı depolara yaklaşma . 2) `python sistem/araclar/skill_tara.py <klasör>` ile tara (prompt-injection, gizli Unicode, riskli komut, kimlik/ayar erişimi, CJK oranı) ve **dosyaları oku**. 3) Bulut/hesap/telemetri/`curl|bash` içerenleri alma. 4) Üçüncü taraf BETİK çalıştırma (sistem de engeller): oku, gerekirse kendi kodunla yeniden yaz. 5) Yalnızca belge/talimat olarak al, YEREL KURAL başlığı ekle, `sistem/kurulum/dis_kaynaklar.json` + `sistem/yama/` ile kaydet (`sistem/kurulum/yama_cikar.py`), `THIRD_PARTY_NOTICES.md`'ye işle. 6) Stüdyo kurallarıyla (`kimlik/MARKA.md`) çelişen önerileri "geçersiz" işaretle.

## Öğrenilmiş dersler
- 16:9'u 9:16'ya bulanık zeminle kırpmak slop'tur: **yeniden kompozisyon**; düşük çözünürlük = bant, yüksek = tam ekran.
- Sentetik sesin altyazısı **senaryodan** (ASR özel adları bozar), zamanı parça sınırlarından.
- "Siyah/donmuş kare" bayrağı marka koyu kartında yanlış alarm verir: eşikler ayarlı (`kalite_olc.py`).
- Kapanışın "havada" duyulması çoğu zaman teknik kesilme değil YAPISALDIR: ses bir isimle bitiyor, vaatle değil; müzikal çözülme (riser → vuruş) yok; sonrası sessiz. Kapanış = vaat cümlesi + düşen ton + sönüş/oda kuyruğu + vuruş + çağrı.
- CSS `text-transform: uppercase` Türkçe "i"yi "I" yapar (HIKÂYE!): büyük harf metni doğrudan yaz ya da `toLocaleUpperCase('tr-TR')`.
- Alt boşluk/kırpma: yatay düşük çözünürlüklü fotoğraflar dikeyde üst/alt yarım panel (960 px) olarak tüm ekranı doldurur; hook = 4 kelimelik büyük başlık (anlam taşıyan renk: sönük/altın).
- Windows: bash heredoc ile uzun dosya yazmak hata verebiliyor (ve `\b` gibi kaçışları bozabiliyor): dosyaları Write ile yaz. Python'a `/c/...` yolu verme, Windows yolu kullan. Bu ortamda `cmd /c ad.cmd` için `.\ad.cmd` gerekir.
- Kurgu biçim projeleri `projeler/<ad>/<format>/` altında: Remotion kök `remotion/`; kit'e göreli yol 5 üst + `sistem/kit/src` (`../../../../../sistem/kit/src`); `yeni_proje.py` bunu kendisi ayarlar.
