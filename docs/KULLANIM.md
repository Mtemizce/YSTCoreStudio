# YSTCoreStudio kullanım kılavuzu

Bu belge ayrıntılı kullanımı anlatır. Kısa tanıtım ve kurulum için [README](../README.md).

## Taşınabilirlik: klasörü başka yere ya da bilgisayara kopyala
Bu klasörü bugün `D:\Videolar\YSTCoreStudio`'dan yarın başka bir kullanıcının ya da bilgisayarın başka bir yoluna **olduğu gibi kopyalayıp** `Başlat.cmd`'yi çalıştırabilirsin; kaldığın yerden devam edersin (ayarlar, arşiv analizi, iyileştirilmiş fotoğraflar, projeler klasörün içinde olduğu için birlikte gelir).
- **Veritabanında mutlak yol yoktur.** Her kayıt *kök + göreli yol* olarak durur (`dosya.kok_id` + `dosya.yol`); çalışırken ikisi birleştirilir. Kökler `kok` tablosunda, **her bilgisayar için ayrı yolla** (`kok_yol`: bilgisayar adı, yol, disk seri no, disk etiketi) saklanır.
- **Stüdyo klasörü otomatik algılanır:** `Başlat.cmd` her açılışta yerini bulur, veritabanını günceller ve yola bağlı şeyleri onarır (Python sanal ortamı `venv`, `kurgu` komutları, Remotion/HyperFrames ayarı, eski oturum betikleri, projelerde kalmış eski yol). Python'un ana sürümü değiştiyse venv yeniden kurulur. Ayrıntı `sistem/ortam/yerel/onarim.log`.
- **Otomatik bulunamayan tek şey arşivdir** (harici disk, ağ paylaşımı, Google Drive/OneDrive eşitleme klasörü). Çözümleme sırası: ortam değişkeni (`YST_ARSIV=D:\Arsiv`) → bu bilgisayar için kayıtlı yol → başka bilgisayarın kaydı aynı yerdeyse → **aynı disk** (birim seri no; sürücü harfi değişmiş olabilir) → tüm sürücülerde aynı klasör adı → bulunamazsa panel **Ayarlar → Konumlar → Gözat** ile klasörü sorar. Yanlış klasör gösterirsen reddedilir (dizindeki dosyalardan örnek alınıp o klasörde var mı diye bakılır) ve bağlı olmayan arşivin kayıtları silinmez.
- **Çok arşiv:** istediğin kadar arşiv tanımlayabilirsin (her biri ayrı ad ve yol). **Adaptör:** her arşiv bir klasör olarak okunur: yerel/harici disk, ağ (`\\NAS\paylasim`), Google Drive for Desktop / OneDrive / Dropbox eşitleme klasörü. Bulutta-yalnızca (indirilmemiş) dosyalar taramada içerik okunmadan kaydedilir (indirme tetiklenmez) ve analiz/önizleme dışı kalır. Doğrudan Google Drive API'si (giriş/OAuth, buluta bağlanma) yoktur; Drive'ı masaüstü uygulamasıyla bağla.
- **Yeni kuruluma taşıyorsan** (klasörü kopyalamak yerine): Ayarlar → *Profili dışa/içe aktar* ya da `python sistem/araclar/profil.py disa-aktar|ice-aktar`. Tek JSON: ayarlar, **API anahtarları**, kimlik katmanları ve öğrenilenler, marka kitleri, MCP, arşiv kökleri ve dizin/analiz kayıtları. Bu senin verindir, o yüzden anahtarlar ve kişisel bilgiler de dahildir; dosya **parolayla şifrelenir** (scrypt + Fernet; parolasız dışa aktarma düz metindir). Daha yeni sürümden gelen bilinmeyen bölümler silinmez, saklanıp sonraki dışa aktarmaya geri konur. `--kuru` ile önce neyin değişeceğini görürsün.
- Projeler klasörü sabit olarak stüdyo klasörünün içindedir (`projeler/`); başka bir diske koymak istersen Windows'ta o klasörü bir *junction* ile bağlayabilirsin, ama klasörü kopyalarken junction hedefi taşınmaz.

## Tek klasör kuralı ve kaldırma
Stüdyonun indirdiği ve ürettiği **her şey stüdyo klasörünün içinde** kalır; AppData, `~/.cache`, Belgeler gibi yerlere yazılmaz. Kurulum ve panel, çalıştırdığı her sürece şu ortam değişkenlerini verir (`sistem/araclar/yol.py` → `kapsama()`; ajan terminali ve Başlat betikleri de aynısını kullanır):

| Ne | Nereye |
|---|---|
| Hugging Face modelleri (Pocket TTS, Whisper, EMA, Depth Anything, Z-Image…) | `sistem/ortam/modeller/hf/` |
| PyTorch önbelleği | `sistem/ortam/modeller/torch/` |
| Kurgu verisi (ffmpeg, modeller, yazı tipi önbelleği) ve ayarı | `sistem/ortam/yerel/veri/`, `sistem/ortam/kurgu-ayar/` |
| Genel önbellek (`XDG_CACHE_HOME`: EMA, …) ve npm önbelleği | `sistem/ortam/yerel/onbellek/` |
| pip önbelleği | kapalı (klasör şişmesin) |
| HyperFrames'in Chrome'u, yazı tipleri, geçmişi | Chrome: klasördeki Remotion Chrome'u. Geri kalanı: HyperFrames ev dizinini sabit olarak `~/.cache/hyperframes` diye kullanır; `sistem/kurulum/ev_yonlendir.cjs` ön yükleyicisi yalnızca hyperframes sürecinin ev dizinini `sistem/ortam/yerel/ev/` yapar (başka Node süreçlerine dokunmaz) |
| Python sanal ortamı, Node paketleri, Kurgu | `sistem/ortam/venv/`, `node_modules/`, `kurgu/` |

Stüdyo klasörüne **dahil olmayanlar:** Python, Node.js, Git ve Claude Code (senin kurduğun programlar), ayrıca pip/npm'in genel önbellekleri (başka projelerle ortaktır, stüdyo kendi önbelleğini klasöründe tutar).

**Kaldırmak için:** paneli kapat (`Başlat.cmd durdur` ya da panelde Kapat) ve stüdyo klasörünü sil. Projelerin ve kimliğin de bu klasörde olduğunu unutma: önce yedeğini al ya da *Profili dışa aktar*.

**Eski bir kurulumdan geliyorsan** (modeller eskiden ortak `~/.cache/huggingface` önbelleğine iniyordu): Kurulum/Onar bu modelleri klasörüne *kopyalar* (indirmeyi tekrarlamaz), eskisini yerinde bırakır. Klasör dışında kalan artıkları görmek için:

```
python sistem/kurulum/kaldir.py           # yalnızca listeler
python sistem/kurulum/kaldir.py --sil     # stüdyoya özgü artıkları siler (her biri için sorar; --evet sormaz)
```
Betik stüdyo klasörünün kendisini, senin kurduğun programları ve başka programlarla paylaşılabilecek önbellekleri (ör. ezdxf, ortak Hugging Face klasörünün geri kalanı, `%LOCALAPPDATA%\Kurgu`) silmez; onları yalnızca listeler.

## Kullanım
1. `Başlat.cmd` → panel.
2. **Yeni video** (tek ekran): ne istediğini yaz ya da **🎤 Konuşarak yaz** (ses bu bilgisayarda faster-whisper ile yazıya çevrilir, hiçbir yere gitmez); seslendirme açık/kapalı + sağlayıcı; isteğe bağlı **görseli üret** (karakter tarifi); isteğe bağlı süre; platformlar (YouTube yatay, Shorts, Reels, Story, TikTok); marka kiti (intro/outro/filigran/iletişim aç-kapa); arşivden bul ya da dosya/video/metin yükle → **Üret**.
3. Claude penceresi açılır ve `/video` akışını yürütür: ajanlar model/effort ayarına göre çalışır; sonunda panel **taslak hazır** der.
4. **Önizle** (Kurgu'da aç): izle, saniye bazlı not yaz, **Gönder**: notlar uygulanır. Seslendirme metnini proje kartındaki **Seslendirme metni**nden düzenlersin (yalnızca değişen satırın sesi yeniden üretilir). Mevcut projeye **Kaynak ekle** ile dosya/video/metin eklenir.
5. Beğendiysen **Onaylıyorum**: final render + seçilen platformların sürümleri (dikey sürümler yatayın kırpması değil, yeniden kompoze edilir). Bitmiş videolar `projeler/<ad>/cikti/` altındadır.

Sağlık kontrolü: panelde **Sağlık kontrolü** ya da `sistem\ortam\venv\Scripts\python.exe sistem\araclar\saglik.py` (`--canli` ajanları gerçekten çağırır, `--proje <ad>` üretim izlerini gösterir).

## Klasör yapısı
Kök dizin bilerek sadedir; kurulumdan sonra Gezgin'de şunları görürsün:

```
Başlat.cmd          başlatıcı
README.md           bu dosya
kimlik/             PROFIL.md (sen kimsin, nasıl konuşursun) + MARKA.md (görsel kimlik)
kurgu/              Kurgu editörü (kurulum çeker)
projeler/<ad>/      her video bir proje
   kaynak/            senin orijinal dosyaların (foto, video, ses, belge)
   hazir/             kaynaklardan türeyenler (envanter, DWG→PNG, PDF→PNG+md, Word→md, Excel→csv)
   ana/ reels/ tiktok/ shorts/   her biri bir Kurgu projesi
   cikti/             bitmiş videolar
sistem/             stüdyonun makinesi: araclar, kit, sablon, tts, varlik, kurulum, yama, panel, ortam
```
Teknik zorunluluk olan şeyler **gizli** özniteliktedir (Gezgin'de "Gizli öğeleri göster" ile görünür): `.claude/` (ajanlar, komutlar, skill'ler, Claude kılavuzu), `.mcp.json`, `node_modules/` + `package.json` (Remotion paketleri; Node paketleri üst klasörlerde arar), `.git*`.

Depoda olmayanlar (kurulum üretir): `kurgu/`, `node_modules/`, `sistem/ortam/` (Python ortamı, modeller, Kurgu ayarı, önbellek), `sistem/araclar/dis/` (LibreDWG), `sistem/kit/sfx`, `sistem/kit/referans`, üçüncü taraf skill dosyaları.

## Kimlik: sistem seni nasıl tanır?
Tek başına bir form seni anlatmaz; dört katman birlikte çalışır (`kimlik/`):
1. **Beyan**: `PROFIL.md` (kişilik, ses, kitle, mesajlar, çağrı, izinler, doğrulanmış gerçekler, telaffuz, çalışma tercihi, anlatı soruları, arşiv/işlerin) ve `MARKA.md` (kilitli görsel kimlik).
2. **Kanıt**: `ornekler/` içine gerçek yazılarını ve ses kayıtlarını (telefon kaydı olur) koyarsın; `sistem/araclar/ses_profili.py` bunları yerelde analiz edip `ses_profili.md` üretir (cümle ritmi, hitap, dolgu sözcükleri, örnek cümleler).
3. **Zevk**: panel → Kimlik → **Zevk testi**: aynı mesajın iki üslubundan hangisinin "sen" olduğunu seçersin, müzikleri dinleyip işaretlersin (`zevk.md`).
4. **Öğrenme**: her projeden sonra geri bildirimlerin `ogrenilenler.md`'ye kural olarak eklenir; sistem seni kullandıkça daha iyi tanır.
Panelin **Kimlik** kutusu doluluğu gösterir; **Claude ile kimliği tamamla** seni sırayla sorgular. Çelişkide sıra: senin sözün > ölçüm > beyan.

## Arşiv (harici disk)
Panel → **Arşiv** kartında arşivin yerini gösterir (yazar ya da **Gözat**) ve taratırsın (yalnızca okunur: arşive hiçbir şey yazılmaz, silinmez, taşınmaz; dosyalar olduğu yerde kalır). Tarama her dosyanın yılını, projesini ve türünü bu bilgisayardaki veritabanına (`sistem/ortam/arsiv/arsiv.db`) yazar; ardından **otomatik analiz** (yerel) çözünürlüğü, keskinliği, ışığı ve yinelenenleri ölçüp her dosya için **kullanılabilir / değil + puan + neden** kaydeder. **`/arsiv-analiz`** ile Claude fotoğraflara bir kez bakıp **aşama (öncesi/yapım/sonrası), konu, açıklama, etiket** yazar. Böylece "2022-2024 villa projeleri, yapım aşaması" dediğinde arşiv diskine yeniden bakılmaz: uygun dosyalar doğrudan veritabanından gelir (`python sistem/arsiv/analiz.py uygun --yil 2022-2024 --kelime villa --asama yapim`). Dosya arşivde değişirse analizi geçersiz sayılıp yenilenir. Sonra **Yeni video → Kaynaklar → arşivden bul** ile yıl aralığı, tür, anahtar kelime, klasör derinliğine göre arar, önizlemelere bakıp seçersin; seçtiklerin tarihe yayılarak örneklenir ve proje klasörüne **kopyalanır**. Konum çözümleme, çok arşiv ve taşınabilirlik için yukarıdaki *Taşınabilirlik* bölümüne bak. Komut satırı: `python sistem/arsiv/arsiv.py ayarla|kokler|durum|tara|yapi|projeler|ara|kopyala`; `python sistem/arsiv/analiz.py oto|bekleyen|yaz|uygun|ozet|proje-yaz`. Not: otomatik analizin keskinlik eşikleri kalibre edilmemiş tahminlerdir; arşivine göre `sistem/ortam/arsiv/esikler.json` ile ayarla (ayrıca klasör içi bağıl bulanıklık kontrolü vardır).

### Kategoriler ve kendi müzik/ses arşivin
Arşiv dosyaları dört kategoride gösterilir: **Resim**, **Video**, **Müzik** (müzik, ses kaydı, ses efekti) ve **Dosya** (çizim, PDF, Word, Excel, metin). Resim/video/müzik/dosya klasörlerinin her biri ayrı bir arşiv olarak eklenebilir (Ayarlar → Arşiv → *Arşiv ekle*; örn. ad `muzik`, yol müzik klasörün). Tarama müziğin süresini ve (varsa) başlık/sanatçı/albüm etiketlerini de okur. **Arşiv kütüphanesi**: kategori sekmeleriyle arar, müziği tarayıcıda dinletir, **Prompt'a ekle** ile adı video isteğine yazar.
Video isteğinde bir dosyayı **adıyla** anman yeterli (örn. `arka planda "Tarkan - Şımarık" çalsın`): orkestratör `python sistem/arsiv/arsiv.py bul "Tarkan Şımarık" --tur muzik --kopyala projeler/<ad>` ile arşivinde bulur, kopyayı projenin `kaynak/ses/` klasörüne koyar ve kullanır (arşivdeki orijinale dokunulmaz). Birden çok aday ya da hiç eşleşme varsa sana sorar. Dosya senin olduğu için lisansı senin sorumluluğundadır; hangi dosyanın nereden alındığı `kaynak/arsiv_secim.json`'a yazılır.

### Düşük puanlı fotoğrafları iyileştirme
Analizde düşük puan alan (küçük çözünürlük, bulanık) fotoğraflar için Arşiv kartında **"Düşük puanlı fotoğrafları iyileştir"**: puanı eşiğin altındakiler listelenir (çok küçük, <400 px olanlar kurtarılamaz sayılıp listelenmez), seçersin, **model** ve büyütme/keskinlik seçersin, çalıştırırsın; her fotoğraf için **önce/sonra** ve ölçülen puan görünür. Orijinal arşiv dosyasına dokunulmaz: iyileştirilmiş kopya `sistem/ortam/arsiv/iyilestirilmis/` altına yazılır (veritabanında kök + göreli yol), projeye alınırken o kopyalanır (`<ad>_iyi.jpg`); beğenmediğini **Sil** ya da "bunu kullan"ı kapat, orijinal gider. CLI: `python sistem/arsiv/iyilestir.py modeller|adaylar|calistir|liste|kullan`.
- **Modeller Ayarlar → "İşler ve modeller"de tanımlanır**, listede işaretlediklerin işlem ekranındaki açılır listede çıkar; kendi modelini ekleyebilirsin (sağlayıcı + servisteki model adı).
- **Yerel (ücretsiz):** *Real-ESRGAN x4* (gerçek ayrıntıyı toparlar, yeni nesne uydurmaz; GPU'da fotoğraf başına birkaç saniye, işlemcide yavaş; hareket bulanıklığını ve çok küçük görüntüleri tam kurtaramaz) ve *Klasik keskinleştirme* (yalnızca büyütür ve keskinleştirir). Yerelde "Claude" piksel işlemez: model Real-ESRGAN'dır, Claude/ajan seçimi ve kontrolü yönetir.
- **Ücretli bulut (isteğe bağlı):** Gemini ve OpenAI görsel düzenleme. Bağlayıcı etkin + API anahtarı olmalı ve **her işlemde** "fotoğraflar seçtiğim servise gönderilir" onayı verilir; her çağrı `sistem/ortam/arsiv/bulut_gunlugu.md`'ye yazılır. Üretken modeller **ayrıntı uydurabilir**: müşteriye "gerçek önce/sonra" diye gösterilecek işlerde yerel modeli seç.

## Ayarlar, bağlayıcılar, marka kiti
Panel → **Ayarlar**: (1) her ajan için **model ve effort** (genel varsayılan; proje bazında da ezilebilir; varsayılanları `sistem/ayar/varsayilan.json` tanımlar), (2) **bağlayıcılar**: ElevenLabs (seslendirme), Gemini ve OpenAI (görsel), HeyGen ve her MCP sunucusu; anahtar yalnızca bu bilgisayarda saklanır ve geri gösterilmez, her servis bir projede ancak o projede bulut izni verilirse kullanılır, (3) **marka kitleri**: logo, isim, slogan, iletişim bilgisi, renkler; intro, outro ve filigran her projede aç-kapa, (3a) **orkestratör**: işleri kim yönetsin? Varsayılan **Claude Code** (kendi aboneliğin; alt ajanlar onun içinde çalışır). İstersen Codex CLI, Gemini CLI ya da OpenCode seçilir (deneysel; hesap girişi o programın kendisindedir, API anahtarı gerekmez), (3b) **sağlayıcılar ve yetenekler**: **model adı elle yazılmaz**: OpenAI, Anthropic, OpenRouter, Ollama, LM Studio ya da genel OpenAI-uyumlu bir sunucu seçilir, adres ve (gerekiyorsa) anahtar girilir, **Bağlan ve modelleri getir** servisin kendi model listesini çeker, modeli açılır listeden seçersin (yazım hatası ya da olmayan model mümkün değil; yerel Ollama/LM Studio da aynı şekilde, ağdaki bir makine de olur). Gemini/ElevenLabs için de liste çekilir. Servis yetenek bilgisi vermiyorsa (OpenAI) tür model adından tahmin edilir ve "tahmin" diye işaretlenir. Hiçbir servis ya da model varsayılan değildir; Higgsfield, Seedance, HeyGen, fal.ai, OpenAI-uyumlu bir sunucu… ne kullanacaksan **kodsuz** tanımlarsın (örnek şablondan başla: asenkron HTTP servis, OpenAI-uyumlu, sahte test), anahtarını ve **model adını sen yazarsın**, her yetenek (video üret, görsel üret, seslendirme…) için **sıralı yedek listesi** yaparsın (kredi bitti/servis çöktü → sıradaki denenir), günlük **bütçe tavanı** ve onay eşiği koyarsın (ücretli çağrı tahmini manifestteki `maliyet`ten; tavan aşılırsa durur), (4) **işler ve modeller**: bir işin (örn. fotoğraf iyileştirme) hangi ücretsiz/ücretli modellerle yapılabileceği; işlem ekranında açılır listede seçilir, (5) **konumlar ve taşıma**: arşiv yolları, Gözat, taşıma yedeği, (6) **sistem**: önkoşul analizi (eksik varsa kopyalanabilir komut), stüdyoyu kapat. HeyGen yalnızca MCP olarak eklenir.

## B planı, karakterler, seriler, ses, dış depolama
- **Kodla video:** Claude Code videoyu kodla üretir (Remotion/HyperFrames). Yapamadığı şey fotogerçekçi *kişi* sentezidir: onu ya kodla yaklaşıklarız ya da senin seçtiğin üretken servise yaptırırız.
- **B planı (acil durum) düğmesi:** kişi çekime gidemedi. Yeni video ekranında *B planı* ya da proje kartında **B planı**: gerçek mekân fotoğraf/videoların kodla "içeride gezinti" hareketine çevrilir (**Depth Anything V2 Small** derinlik haritası + kamera kaydırma, düşük donanımda çalışır; model kurulu değilse yaklaşık derinlik), kişi köşede yuvarlak köşeli **sunucu penceresi** olarak durur (yürümez), anlatım sesi yerel EMA ya da senin tanımladığın klon-ses sağlayıcısıdır. İstersen **üretken (bulut) ikiz** de denenir: kişiyi mekânda yürütüp konuşturur (Higgsfield vb., sen seçersin; ücretli, ayrıntı uydurabilir, fotoğrafların o servise gider). "Dijital sunum" etiketi **senin kararındır** (varsayılan kapalı). Mekân görüntüleri **gerçek** olmalı; olmayan bir ziyaret iddia edilmez. Komut satırı: `python sistem/araclar/mekan_gezisi.py gezi <foto…> -o gezi.mp4 --sunucu portre.jpg --etiket "Dijital sunum"`.
- **Karakterler (dijital ikiz):** Ayarlar → Karakterler: boy + portre fotoğrafı, **rıza onayı ve onaylayan adı olmadan oluşmaz**; `kimlik/karakterler/` altında durur (git'e girmez, profil dışa aktarmaya girer).
- **Seriler:** `kimlik/seriler/<ad>/seri.json` seri kitabı (karakterler, stil, sezonlar, bölümler); her bölüm bir proje, senarist önceki bölüm özetlerini bağlam olarak okur (`seri.py`, panel: Seriler).
- **Ses kaydı + temizleme:** proje kartında **🎤 Ses kaydet**: mikrofon kaydı yerelde (ffmpeg) temizlenir (dip gürültüsü, boşluk kırpma, klik sınırlama, −16 LUFS) ve `kaynak/ses/` altına eklenir; ajan onu istediğin saniyeye yerleştirir. Kaydı **"Bu kaydı sesim olarak kullan (klonla)"** ile klon örneği de yapabilirsin.
- **Ses klonlama:** Yeni proje ekranında **Sesimi klonla**: bir uyarı penceresi çıkar (yalnızca kendi sesin ya da sahibinin izniyle; ses bu bilgisayarda işlenir, hiçbir yere gönderilmez), kabul edince promptu konuşarak yazdığın kayıt ya da **Sesimi kaydet** örnek ses olur (`kimlik/ses/`, depoya girmez). Örnek için beş ölçüt gösterilir (süre, gürültü, patlama, seviye, konuşma oranı: iyi/orta/zayıf + ipucu; hiçbiri klonlamayı engellemez) ve **Klonu dene** örnekle bir cümle üretip Whisper ile geri çözerek anlaşılırlık yüzdesini verir (sesin bozuk olup olmadığı; benzerliği ölçmez, onu kulakla değerlendirirsin). Motor: Pocket TTS Turkish (CC-BY-4.0, atıf aşağıda).
- **Dış depolama:** rclone ile Drive/Dropbox/OneDrive/S3 (yetkilendirme rclone'da; uzaktan yalnızca okuma/kopyalama), çıktıyı yükleme ve **storage.to** ile geçici paylaşım bağlantısı **açık onay** ister ve günlüklenir; yalnızca proje çıktıları dışarı gönderilebilir.
- Henüz yok: ncnn-Vulkan büyütme, ajan başına farklı abonelik.

## Panel
Sol kenar çubuğunda **Pano**, **Yeni proje** ve **Ayarlar** var. Pano: üretilen, şu an üretilen ve senden bekleyen projeler; istatistikler; bağlı modeller; ücretli kullanım. **Yeni proje** → *Tek video* (prompt, kaynak, model, ses, görsel) ya da *Seri / Dizi*. Üretime başlayınca Kurgu editörü panelin içinde canlı açılır; Pano'ya dönebilirsin, üretim arka planda sürer. Açık/koyu tema üst çubuktaki düğmeyle. Ayarlar → *Sistem ve güncelleme*'de GitHub deposu + jeton girersen saatte bir güncelleme kontrolü yapılır ve tek tıkla (yedek alarak) güncellenir.
Düşük donanım için isteğe bağlı: *Servisler → Yerel görsel üretim* (Z-Image-Turbo; ~7 GB, varsayılan kurulu gelmez).

## Bulut disk arşivi ve ajan başına ortam
- **Google Drive / OneDrive / Dropbox arşivi:** Studio → Arşiv → *Bulut disk*: rclone'u panelden kur (resmî siteden, sağlama toplamı doğrulanır), hesabı tarayıcıda bir kez yetkilendir (Drive için yalnızca okuma izni), klasörü gezerek seç, arşiv olarak ekle. Tarama sadece listeyi alır; fotoğraflar analiz/önizleme/kopyalama sırasında önbelleğe iner. Birden fazla hesap ve klasör eklenebilir.
- **Ajan başına çalışma ortamı:** Ayarlar → Ajanlar tablosunda "Çalışma ortamı". Claude Code orkestratör olarak seçili rolü `python sistem/araclar/ajan_cagir.py <ajan> <gorev.md>` ile Codex (ChatGPT aboneliği), Gemini CLI ya da OpenCode'a devredebilir.
- Her karttaki **?** düğmesi o bölümün ne işe yaradığını anlatır.

## Müzik ve ses efektleri
Hepsi `sistem/varlik/varliklar.db` içinde kayıtlıdır (kaynak adresi, sha256/commit, lisans); dosyalar **isteğe bağlı olarak panelden indirilir** (Pano'daki öneri ya da Ayarlar → Sistem → Arka plan kurulumu), depoda ses yoktur. Atıf gerektiren hiçbir şey alınmaz. **320 CC0 ses efekti** (Wyzowl SFX Kit; `sistem/araclar/sfx_bul.py` ile ekrandaki ana göre aranır, senkron noktasına yerleştirilir), **19 atıfsız müzik parçası** (Chopin: Internet Archive / Musopen, CC0; Satie, Debussy, Vivaldi: Wikimedia Commons, kamu malı) ve Pixabay efektleri. Yeni parça: `varlik.py ekle` (URL) ya da `ekle-yerel` (kendi müziğin).

## Testler
`python sistem/testler/calistir.py` hızlı testleri çalıştırır (ağ ve gerçek model gerekmez; kurulumun sanal ortamıyla ya da Pillow, NumPy, cryptography, fonttools, pypdf, pypdfium2 kurulu herhangi bir Python 3.10+ ile). `--canli` ayrıca çalışan panel ve kurulu modeller isteyen testleri (Pocket TTS, EMA, Depth Anything, Real-ESRGAN) çalıştırır; `calistir.py kimlik donanim` yalnızca adı geçenleri. Testler ayarları ve geçici `zz-*` projelerini kendileri yedekleyip geri yükler; panel kapalıyken çalıştırılmalıdır.

GitHub Actions (`.github/workflows/`; kota harcamamak için yalnızca elle çalışır: GitHub → Actions → Run workflow): **Testler** (`test.yml`) Linux, macOS ve Windows'ta hızlı testleri çalıştırır. **Kurulum testi** (`kurulum-testi.yml`) sıfır bir Linux ve macOS makinesinde tam kurulumu yapar, paneli açar, sağlık denetimini ve testleri çalıştırır, sürüm paketini ve günlükleri çıktı olarak bırakır. macOS sürümü GitHub'ın sanal macOS makinesinde kurulup test edilir.

## Dış bileşenler ve yamalar
Dış projeler depoya **konmaz**; kurulum bunları kendi depolarından, sabitlenmiş sürümle çeker (`sistem/kurulum/dis_kaynaklar.json`), ardından bizim değişikliklerimiz (`sistem/yama/`) üzerine uygulanır. Değişiklikler küçüktür: Kurgu'ya EMA konuşma entegrasyonu; üçüncü taraf skill'lere "YEREL KURAL" başlığı ve bulut/telemetri satırlarının sökülmesi.

Yeni varlık (müzik, ses efekti) eklemek: `sistem\ortam\venv\Scripts\python.exe sistem\varlik\varlik.py ekle --tur muzik --ad "…" --url https://… --hedef sistem/kit/muzik/ad.mp3 --lisans "…"`. Kayıt depoya gider; başka bilgisayardaki kurulum dosyayı kendisi indirir.

Yeni TTS motoru eklemek: `sistem/tts/__init__.py` başındaki yönerge.

## Ara sahne: kalemle çizim
Proje kartındaki **🎞 Ara sahne ekle** (ya da yeni proje formundaki *Ara sahne* galerisi) bir kaynağı kalemle çizilen kısa bir videoya çevirir. Üç stil: **parşömen eskizi**, **kara kalem**, **mavi teknik çizim**. Kaynak olarak şunlar seçilir:
- **Çizim (DWG/SVG):** çizgiler kademeli çizilir (DWG okuma yalnızca Windows'ta; başka sistemde SVG ver).
- **Herhangi bir resim:** kenarlar çıkarılıp kalemle çizilir; **"Çizim bitince gerçek resme dönüşsün"** seçilirse çizim bittikten N saniye sonra bulanıklaşıp aynı yerde gerçek resim açılır.
- **Video:** videonun **ilk karesi** çizilir, N saniye sonra gerçeğe dönüşüp video kesintisiz devam eder (çıktı: giriş + video, tek mp4; ses korunur). Örnek: kapıdan girilen bir sahnenin ilk karesini çiz, 2 sn sonra video başlasın.

**Zemin (kâğıt) rengi:** panelde *Zemin rengi* listesinden (aydınlık, yeşilimsi çimen, sıcak kâğıt, soğuk mavi-gri, karanlık ya da kendi rengin) seçilir; komut satırında `--zemin "#DCE8D2"`. Mürekkep zeminin parlaklığına göre koyu ya da açık seçilir (karanlık zemin: açık çizgi). Gerçeğe geçişte ya da video girişinde kenar dolgusu da aynı renktedir. Örneğin arkasında çimenlik olan bir sahne için yeşilimsi zemin seçersen çizimden gerçeğe geçiş uyumlu görünür.

**Resimlerde ton taraması:** kenar çizgilerine ek olarak koyu bölgeler kısa paralel kalem çizgileriyle (çapraz tarama, 4 katmana kadar) gölgelenir; böylece portre ve fotoğraflar çizgi çizimden fazlasıdır. `--tarama 0..1` (0: yalnızca kontur), `--detay 0..1` (kontur ayrıntısı; yüz gibi dokulu yerlerde düşük tut). Videoda `--cizim-kaynagi temiz.png` ile, çizilecek resim olarak videonun ilk karesi yerine aynı kadrajda vinyetsiz ve grensiz bir hâli verilebilir.

Komut satırı: `python sistem/araclar/kalem_cizim.py <kaynak> -o ara-sahne.mp4 --stil karakalem [--zemin "#EFEBE0"] [--gecis --bekle 2]`. Çizilen şey kenar çizgileri ve ton taramasıdır (renk değil): kontrastlı, yüksek çözünürlüklü resimlerde en iyi sonucu verir. Görünüm fikri ve çizim sürücüsü [kalem](https://github.com/leodavincs/kalem) projesinden uyarlanmıştır (MIT).

## Kurgu'nun içinde: Görsel, Ses, Ara sahne
Kurgu editörü panelin proje ekranına gömülüdür ve üst çubuğunda üç stüdyo düğmesi vardır (Düzen kipinde görünür); hepsi sonucu doğrudan zaman çizelgesine, oynatma başlığının olduğu ana koyar:
- **Görsel:** *Kütüphane* sekmesinde onaylı görsellerinden birini ekle; *Yeni üret* sekmesinde istem + stil + boyutla yerel modelle üret, beğendiğini onaylayıp ekle, beğenmediğini yeniden üret ya da reddet. Model kurulu değilse "Kurmak için panele git" düğmesi seni Ayarlar'daki Kur düğmesine götürür.
- **Ses:** metni yaz (seçili metin katmanının metni hazır gelir), motoru seç (EMA Lightning, Pocket TTS Turkish: ses, duygu, klonlanmış ses; kurulu ve anahtarı tanımlı bulut motorları da), hızı ayarla, **Seslendir**; dinle, beğendiysen ekle, değilse *Başka alım*. Aynı metin + ayar yeniden üretilmez, önbellekten gelir. Dosya projenin `media/tts/` klasörüne yazılır; atıf gerektiren motorda `ATIF.txt` da yazılır.
- **Ara sahne:** kaynak olarak oynatma başlığındaki kareyi, projedeki bir resmi ya da videoyu seç; kalem stilini, zemin rengini, "çizim bitince gerçek görüntüye dönüşsün" seçeneğini ve kalem sesini ayarla, **Çiz**. Sonuç `media/ara-sahne/` altına yazılır; ekleyince çizim sesiyle birlikte gelir.

Kurgu kendi deposundan çekilir; bu düğmeler ona kurulumda otomatik uygulanan bir eklentidir (`sistem/kurulum/kurgu_yama.py`, kaynaklar `sistem/yama/kurgu_ek/`). Eklenti yeni dosyalar ekler ve Kurgu'nun `server.py`, `web/index.html`, `pyproject.toml` dosyalarına yalnızca bağlantı satırları koyar; her satır Kurgu'nun sabitlenmiş sürümündeki bir çapaya bağlıdır.

**Kurgu'nun sürümü değişirse çalışma engellenmez.** Çapa bulunamazsa (Kurgu köklü değiştiyse) hiçbir dosyaya dokunulmaz, kurulum hata vermez, Kurgu kendi düz haliyle açılır ve panelin proje ekranı sarı bir bilgi şeridiyle "bu sürümde eklenti uyumsuz; Görsel için *Görsel üret*, ara sahne için Pano'daki proje kartı, seslendirme için ajan penceresi" der. Aynısı eklenti yüklenip içeride patlarsa da olur: `server.py`'deki import `try/except` içindedir, `/api/yst/` rotası yalnızca eklenti yüklüyse vardır, arayüz betiği ayrı bir modüldür ve Kurgu'nun arayüzü yüklendiğinde panele "hazır" der (25 sn içinde demezse şerit çıkar). Düz Kurgu istersen (ya da bir sorunda eklentiyi dışarıda bırakmak için): `python sistem/kurulum/kurgu_yama.py --kaldir` yamayı geri alır ve kurulum/Onar'ın yeniden uygulamasını durdurur, `--ac` geri getirir; aynıları panelin şeridindeki *Eklentiyi kapat / aç / yeniden dene* bağlantılarındadır. Kurulum ve **Onar** her seferinde yeniden uygular; elle denetlemek için `python sistem/kurulum/kurgu_yama.py kurgu --kontrol`, sağlık denetimi de bunu sorar. Kurgu'nun sürümünü yükseltirsen çapaları `kurgu_yama.py` içindeki `EKLER` listesinde güncelle ve `python sistem/testler/calistir.py kurgu_yama` çalıştır.

## Görsel üret, kütüphane ve diziler
**Görsel üret (yerel Z-Image-Turbo).** Ayarlar → Servisler ve modeller → *Yerel görsel üretim* → **Kur** ile kurulur (yaklaşık 7 GB; ekran kartı belleğine göre kalite seçilir). Kuruluysa kenar çubuğunda ve Pano'da **Görsel üret** çıkar, yeni projede "Görseli üret" listesinde varsayılan olur. Akış: istem + stil (anime dahil 14 stil) + boyut → üret → **kontrol** (kartta kalite ölçütü: düz, bulanık, karanlık uyarısı; asıl kontrol senin gözün) → beğendiysen **kütüphaneye ekle**, beğenmediysen **yeniden üret** (aynı istem, yeni tohum) ya da reddet. Onaylanan görseller `kimlik/gorseller/onayli/` altında durur ve "Üretilen görseller" adıyla arşiv köküne girer; yeni projede *Kaynaklar → Üretilen görseller*'den, açık bir projede Kurgu'nun üst çubuğundaki **Görsel** düğmesinden (kütüphaneden seç ya da orada yeni üret) kullanılır; görsel Kurgu `media/foto` klasörüne kopyalanır ve oynatma başlığına eklenir. Komut satırı: `python sistem/araclar/gorsel_kutuphane.py uret|liste|onayla|reddet|yeniden|projeye|stiller`.

**Diziler (Yeni proje → Seri / Dizi).** Üç iş ayrıdır: *yeni dizi projesi* kurmak, *mevcut diziye yeni bölüm* eklemek, *mevcut bölümü düzenlemek*. Dizi oluştururken tür, açıklama, anlatım tonu ve **görsel stil** (anime stilleri dahil) seçilir. Her dizinin **model seti** vardır: karakter, nesne ve mekân için onaylı görseller, bir ana görsel, görünüş tarifi ve her görsel üretiminde aynen eklenen **sabit istem eki**. Bölüm eklerken senaryo/kurgu yazılır ya da dosyadan yüklenir ve o bölümde görünen modeller işaretlenir; bölüm projesine `kaynak/belge/senaryo.md`, `kaynak/foto/model-*.png`, `seri_model_seti.md` ve `seri_baglami.md` (önceki bölüm özetleri dahil) yazılır. **Claude ile yap** düğmesi `/seri` akışını başlatır: orkestratör bölümü sana sunar, onayını alır, eksik görselleri üretip kontrol eder, sonra bölümü yapar ve bitince özetini seriye işler. Z-Image yalnızca metinden görsel üretir; aynı kişinin görünümü, onaylı görselleri doğrudan kullanmakla ve sabit istem ekini eklemekle korunur. Pano'da her bölüm "Dizi adı · S01B02" etiketiyle görünür.

## Marka kiti
Ayarlar → Marka ve üretim. Bir kit şunları içerir: kimlik ve iletişim, **birden çok logo** (ana, simge, yatay, koyu/açık zemin), **metinler** (slogan, çağrı, yasal uyarı…), ana renkler ve rolleriyle ek renkler, yazı tipleri, intro/outro/filigran ayarları ve **kullanım kuralları**. Bir kural bir öğe (logo, metin, renk, intro, outro, filigran, kapak ya da genel) için *nerede*, *ne zaman*, *nasıl* ve *yasak* alanlarını serbest cümlelerle taşır. Projeye kit uygulanınca `projeler/<ad>/marka_kullanimi.md` kılavuzu yazılır (kitin kimliği, logo dosyaları, o projedeki intro/outro/iletişim seçimleri ve senin kuralların); sahne yapımcısı ve diğer ajanlar bunu aynen uygular. Eski biçimli kitler olduğu gibi çalışır.
