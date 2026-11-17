---
description: "Yeni video üret: panelden gelen üretim isteğini (prompt, seslendirme, görsel üretimi, platformlar, marka kiti) planla, ajanlara dağıt, taslağı hazırla ve önizleme için dur."
argument-hint: "projeler/<ad> (panelden açılan proje) ya da ne istediğini serbestçe tarif et"
---

Yönetmen modundasın. Kullanıcı yeni bir video istiyor:

**İstek:** $ARGUMENTS

Sen **orkestratörsün**: `.claude/skills/video-yonetmen/orkestrasyon.md` protokolünü uygula (görev paketi, her teslimi doğrulama, `calisma_gunlugu.md`). Durumu `python sistem/araclar/durum.py ayarla <ad> <aşama>` ile güncelle ki panel gösterebilsin.

> **B planı:** `projeler/<ad>/uretim.json` içinde `b_plani` varsa kişi çekime gidemedi demektir: bu komut yerine `.claude/commands/b-plani.md` akışını uygula (gerçek mekân görüntüleri + dijital sunucu).

## 0. Girdileri topla (hepsi dosyada)
- `projeler/<ad>/uretim.json` (kullanıcının panelde seçtikleri: prompt, seslendirme açık/kapalı + sağlayıcı, görsel üretimi + sağlayıcı + karakter tarifi, süre (yoksa prompttan al), **platformlar**, marka kiti seçimi, arşivden bul), `brief.md` (sihirbaz cevapları: kullanıcı beyanı, tekrar sorma), `ayar.json` (proje ayarı, bulut izni), `kaynak/` ve `hazir/`.
- Kimlik katmanları: `kimlik/PROFIL.md`, `ses_profili.md`, `zevk.md`, `ogrenilenler.md`, `MARKA.md`; `kimlik/marka_kitleri/<kit>/` ve projedeki `marka_secimi.json`. Eksik katmanı bir kez söyle (`kimlik_olc.py`), varsayımla ilerle.
- Marka: `projeler/<ad>/marka_kullanimi.md` (kitin kimliği + kullanıcının yazdığı yerleşim/kullanım kuralları: **aynen uygula**). Dizi bölümüyse `seri_baglami.md`, `seri_model_seti.md` ve (varsa) `kaynak/belge/senaryo.md` (`/seri` akışı).
- **Çözülmüş ajan ayarı:** her ajan için `python sistem/ayar/ayar.py ajan <ajan> <ad>` (model, effort, bağlayıcı). Agent aracını çağırırken **bu model ve effort'u açıkça ver**. Kullanıcı panelden değiştirmiş olabilir (genel ya da bu proje için); varsayılanları kendin seçme.

## 1. Planlama (`durum: planlama`)
1. **Kaynakları bul (arşiv veritabanından, taramasız):** `arsivden_bul` açıksa (ve/veya prompt yıl/proje belirtiyorsa) arşiv diskine gitme; analiz edilmiş veritabanından seç:
   - Kapsam: `python sistem/arsiv/analiz.py ozet --derinlik 2` (hangi proje klasörlerinde kaç kullanılabilir fotoğraf, kaçı anlamlandırılmış).
   - Aday: `python sistem/arsiv/analiz.py uygun --yil <a-b> --kelime "<konu>" --asama oncesi|yapim|sonrasi --limit 40` (her aşama için ayrı), video için `--tur video`. Sonuçta açıklama, puan ve aşama hazır gelir. Kullanıcı düşük puanlı bir fotoğrafı arşiv ekranında iyileştirmişse `iyilestirilmis_puan` dolu gelir ve `arsiv.py kopyala` iyileştirilmiş sürümü (`*_iyi.jpg`) kopyalar; sen ayrıca iyileştirme çalıştırmazsın.
   - **Kapsamda analiz eksikse** (kullanılabilir/anlamlandırılmış sayısı az): önce `/arsiv-analiz <yıl> <klasör>` mantığını çalıştır (`oto` + `arsiv-analisti`), ya da kullanıcıya maliyeti söyleyip sor. Arşiv hiç taranmadıysa panelde Arşiv → Tara gerektiğini söyle.
   - Adayları kullanıcıya **tek ekranda özetle** (proje, yıl, kaç kare, aşama dağılımı) ✋ onay al; onaylananı `python sistem/arsiv/arsiv.py kopyala --idler … --hedef projeler/<ad>/kaynak` ile kopyala (arşive yalnızca okunur) ve `python sistem/arsiv/analiz.py kopya-listesi --idler … --hedef projeler/<ad>/kaynak` ile analizi `kaynak/arsiv_analiz.json`'a yaz: senarist ve sahne ajanları neyin ne olduğunu oradan okur.
   - Arşiv bağlı değilse kopyalama yapılamaz (dizin çevrimdışı aranabilir); diski takmasını iste. Kullanıcının panelden **elle eklediği** dosyalar (`kaynak/`, `kaynak/belge/…md`) arşiv seçiminden önceliklidir ve her zaman kullanılır.
2. `kisilik-ve-ton` ile prompt'u ve profili değerlendir, `ton_rehberi.md` üret.
3. **Dikey-öncelikli planlama:** seçili platformlarda dikey (shorts, reels, story, tiktok) varsa hikâye tahtasına **her sahne için hem 16:9 hem 9:16 kompozisyonu** yazdır: yatay materyaller dikeyde kırpılmaz/bulanık zemine konmaz; her görsel için dikey kadraj/odak noktası planlanır, üretilen görseller iki oranda (`*_yatay`, `*_dikey`) istenir (`sosyal-surumler`).
4. `senarist` → `redaktor` (ucuz denetim: yazım, yasak kelime, §15 dışı iddia, ritim) → senaryoyu kullanıcı beyanıyla çelişkiye karşı kontrol et. Ayar `onay: plan-ve-taslak` ise planı özetleyip ✋ onay iste (`durum: plan-onayi-bekliyor`).

## 2. Üretim (`durum: uretiliyor`), bağımsız işleri paralel
- `gorsel-iyilestirici` (yerel, düşük çözünürlüklü fotoğraflar).
- `gorsel-uretici`: **yalnızca** `uretim.json` "görsel üret" açık, sağlayıcı etkin, anahtar var ve `ayar.json` bulut izni verilmişse (`python sistem/baglayici/uret.py durum --proje <ad>`). Karakter sayfası önce, sonra sahne görselleri (yatay + dikey). Aksi halde atla ve nedenini günlüğe yaz.
- `ses-yonetmeni`: seslendirme açıksa seçilen motorla (`ema` yerel; ücretli motor yalnızca izinliyse), müzik/SFX (`ses-kutuphanesi.md`).
- `sahne-yapimcisi` (sahne başına paralel): marka kiti bileşenleri (`MarkaIntro`, `MarkaOutro`, `Filigran`: `remotion/src/marka.json`; kapalı olanları çizme), shader geçişleri (`gecis('…')`), format-bilinçli sahneler. Montajı Kurgu'da (`project.json`) kur.
- Her teslimi **sen** doğrula (kare, ölçüm); günlüğe işle.

## 3. Taslak ve durma noktası
Taslak render'ı al (`--draft`), `elestirmen`'den geçir. Sonra **DUR**: `durum.py ayarla <ad> taslak-hazir`. Kullanıcıya şunu söyle: "Taslak hazır. Panelden **Kurgu'da aç** ile önizle; saniye bazlı not bırakabilirsin (Gönder), sonra panelden **Onaylıyorum**." Kullanıcı Kurgu'da not gönderirse (wake/`notes wait`) notları uygula, taslağı yenile, durumu `taslak-hazir` tut. **Final render ve platform sürümleri bu komutta yapılmaz**: onaydan sonra `/final projeler/<ad>` çalışır.

## Kurallar
Üretimde internetten materyal arama/indirme yok (kaynak eksikse kullanıcıya sor ya da yerelde üret) · Doğrulanmamış iddia yok · orijinal kaynaklara dokunma · bulut yalnızca bağlayıcı etkin + anahtar + proje izni varsa, her çağrı `bulut_gunlugu.md`'de · ajan raporu bir iddiadır · taslakta bile marka ve MARKA.md yasakları geçerli · proje sonunda geri bildirimi `kimlik/ogrenilenler.md`'ye ekle (onayla).
