# Orkestrasyon protokolü: ana oturum yönetmen, ajanlar işi yapar, yönetmen denetler

Bu depoda **ana oturum (sen) orkestratörsün**. Üretimin ağır işini alt ajanlara verirsin, her teslimi kendin **doğrularsın**, kararı sen verirsin. Ajan raporu bir **iddiadır**, kanıt değildir: kareye, ölçüme, dosyaya bakmadan kabul etme.

## 1. Rol ayrımı
| Kim | Ne yapar | Ne yapmaz |
|---|---|---|
| **Ana oturum (yönetmen/orkestratör)** | brief ve profil analizi, görev paketlerini yazma, ajanları sırayla/paralel çağırma, **doğrulama**, sentez, kullanıcıya sorma, kararlar | toplu üretim kodu/sahne/ses yazmaz (yalnızca yapıştırıcı ve düzeltme); kendi işini kendi puanlamaz |
| `senarist` (opus) | ton rehberi, senaryo, hikâye tahtası | kod yazmaz, render almaz |
| `sahne-yapimcisi` (sonnet, sahne başına paralel) | Remotion/HyperFrames sahnesi + still kontrolü | senaryoyu değiştirmez |
| `ses-yonetmeni` (sonnet) | seslendirme planı/üretim, müzik/SFX, ölçüm | "doğal oldu" demez (duyamaz) |
| `gorsel-iyilestirici` (haiku) | toplu foto iyileştirme, önce/sonra | yargı yapmaz |
| `arsiv-analisti` (sonnet) | arşiv fotoğraflarını kontakt sayfasından anlamlandırır (aşama/konu/açıklama/kullanılabilirlik) → veritabanı | arşive yazmaz; müşteri adı/yüz tanımlamaz |
| `sosyal-kesici` (sonnet) | dikey sürümlerin yeniden kompozisyonu | ana filmi değiştirmez |
| **`elestirmen` (opus, bağımsız)** | rubrikle SHIP/DÜZELT kararı | yazma yetkisi yok; üretici bağlamı görmez |

Ajanlar birbirine konuşamaz ve senin sohbet geçmişini görmez: **her şeyi görev paketiyle ver**, sonuçları **dosya** olarak geri al.

## 2. Görev paketi (her devirde, eksiksiz)
```
GÖREV: tek cümle, tek sonuç
GİRDİ: okunacak dosyaların TAM yolları (brief.md, kimlik/PROFIL.md, kimlik/ses_profili.md, kimlik/zevk.md, kimlik/ogrenilenler.md,
       kimlik/MARKA.md, ton_rehberi.md, senaryo.md …) — ilgili olanlar, hepsi değil
ÇIKTI SÖZLEŞMESİ: hangi dosyalar, nerede, hangi biçimde (ör. projeler/<ad>/ana/ses/rapor.json)
KABUL ÖLÇÜTLERİ: ölçülebilir ("-14 ±1 LUFS", "hiçbir yasak kelime yok", "metin güvenli kutuda", "her sahne kaynağı dosya adıyla")
SINIRLAR: YEREL KURAL, MARKA, doğrulanmış gerçekler dışında iddia yok, orijinallere dokunma
RAPOR BİÇİMİ: değişen/üretilen dosyalar · baktığın kareler/ölçümler · açık riskler · yapamadıkların
```
Her çağrıda `model:` açık verilir (`senarist`/`elestirmen` opus; `sahne-yapimcisi`/`ses-yonetmeni`/`sosyal-kesici` sonnet; `gorsel-iyilestirici` haiku).

## 3. Akış ve paralellik
```
brief + kimlik katmanları analizi (sen)
  → senarist → [sen doğrula] → ✋ kullanıcı onayı (kimlik/PROFIL §16 tercihine göre)
  → ses-yonetmeni ‖ gorsel-iyilestirici ‖ sahne-yapimcisi×N (bağımsız sahneler aynı anda)
  → [sen her teslimi doğrula] → montaj (Kurgu) → render → ölçüm (kalite_olc/ses_olc)
  → elestirmen → SHIP | DÜZELT(madde madde) → ilgili ajana geri (en çok 3 döngü)
  → sosyal-kesici (dikey sürümler) → elestirmen → teslim → ✋ kullanıcı
  → öğrenilenleri yaz (kimlik/ogrenilenler.md, kullanıcı onayıyla)
```
Bağımlılık yoksa **tek mesajda birden çok ajan** çağır (paralel). Bağımlıysa sırayla ver ve çıktıyı dosya olarak ilet.

## 4. Doğrulama (her teslimde; "tamam" demeden önce)
- **senarist:** yasak kelime taraması (`grep` ile PROFIL §4 listesi + MARKA), her rakam/yıl/ödül `kimlik/PROFIL.md §15` doğrulanmış gerçekler tablosunda var mı, tempo (kelime/sn), her sahnenin kaynak dosyası gerçekten var mı, ses_profili ritmine yakın mı.
- **sahne-yapimcisi:** kritik karelerde `remotion still` ya da `kurgu frame/strip`: metin taşması, güvenli kutu, marka rengi/yazı tipi, ilk 3 sn, son kart. Kareyi **sen** aç ve bak.
- **ses-yonetmeni:** `rapor.json` var mı, `sistem/araclar/ses_olc.py` (perde/sönüş), LUFS/tepe hedefi, parça süreleri sahne süreleriyle uyumlu mu. Tonu/doğallığı **kullanıcı dinler**; sen iddia etme.
- **gorsel-iyilestirici:** önce/sonra karşılaştırma görseline bak; okunur yazı/logo/yüz yeniden çizilmemiş olmalı.
- **sosyal-kesici:** 9:16 güvenli kutu, altyazı, ilk 3 sn, süre, `kalite_olc.py --platform`.
- **elestirmen:** kararı olduğu gibi aktar; DÜZELT maddelerini ajana geri ver, "yumuşatma".

## 5. Çalışma günlüğü (zorunlu): `projeler/<ad>/calisma_gunlugu.md`
Her devirde bir satır ekle (yalnızca ekle, silme). Panel/`saglik.py --proje` bunu okur: ajanın gerçekten çalıştığının kaydı budur.
```
| zaman | ajan (model) | görev | girdi | beklenen çıktı | gerçek çıktı | doğrulama (ne baktım) | karar | not |
```
Karar: `kabul` · `revize (n. döngü)` · `ret` · `kullanıcıya sorulacak`.

## 6. Üst makam ve durma kuralları
- Bir ajan aynı hatayı 2 denemede çözemezse dur, nedenini yaz, **kullanıcıya seçenek sun**; kaliteyi sessizce düşürme.
- Kullanıcının sözü > bu protokol > ajan önerisi. Kimlik/MARKA ile çelişen ajan çıktısı reddedilir.
- Bulut/ücretli servis yalnızca **bağlayıcı etkin + anahtar var + projede bulut izni** varsa (§9); telemetri ve atıf gerektiren hiçbir şey kullanma.
- Maliyet: mekanik iş haiku, üretim sonnet, yargı opus. Aynı işi iki ajana yaptırma.

## 7. Proje sonu: öğrenme döngüsü
Kullanıcının geri bildirimini ("altyazı alt boşluk bırakıyor", "outro havada kalıyor", "bu müziği sevdim") **dosyaya bağla**: `kimlik/ogrenilenler.md`'ye tarihli, projeli, tek satırlık kural olarak ekle (kullanıcıya göster, onaylarsa kaydet). Sonraki projelerin ilk adımı bu dosyayı okumaktır: sistem seni kullandıkça daha iyi tanır.

## 8. Ajan ayarı: model ve effort kullanıcının elinde
Kullanıcı panel → Ayarlar'dan her ajanın **modelini** (opus/sonnet/haiku/fable) ve **effort**'unu (low…max) genel olarak ya da proje bazında seçer. Öncelik: varsayılan < kullanıcı < proje (`sistem/ayar/`). Bu yüzden:
- **Çalışma ortamı (ajan başına abonelik):** `ayar.py ajan <ajan> <proje>` çıktısındaki `calisma_ortami` `claude-code` değilse (örn. `codex`, `gemini-cli`) o rol için Agent aracını KULLANMA: görevi bir dosyaya yaz (girdi dosyaları, beklenen çıktı dosyası, kurallar) ve `python sistem/araclar/ajan_cagir.py <ajan> <gorev.md> --proje <ad>` ile çalıştır; ajanın yanıtı bir iddiadır, çıktı dosyasını kendin doğrula. Salt yanıt isteyen görevlerde `--salt-okunur`. Kurulu ortamlar: `python sistem/araclar/ajan_cagir.py ortamlar`. Başarısız olursa (kurulu değil / giriş yok) rolü Claude ile yürüt ve kullanıcıya söyle.
- Agent aracını çağırmadan önce **her seferinde** `python sistem/ayar/ayar.py ajan <ajan> <proje>` çalıştır ve dönen `model` ile `effort`'u çağrıya **açıkça** ver. Varsayılanları ezbere kullanma.
- Kullanıcı bir ajanı değiştirdiyse (ör. redaktörü opus/high yaptı) o ayara uy; "daha ucuzu yeter" diye kendi kararınla düşürme. Kalite sorunu görürsen ayarı değil sonucu raporla ve kullanıcıya öner.
- Ajan dosyalarındaki `model:`/`effort:` yalnızca ajan doğrudan çağrıldığında geçerlidir (`ayar.py esitle` genel ayardan yazar).

## 9. Bağlayıcılar (ücretli/bulut servisler): isteğe bağlı, varsayılan KAPALI
ElevenLabs, Gemini/OpenAI görsel, HeyGen (MCP) gibi ücretli servisler **isteğe bağlı** kullanılabilir. Kurallar:
1. Üç koşul birlikte: sağlayıcı **etkin** (Ayarlar) + **API anahtarı** var (yalnızca `sistem/ortam/baglayici/anahtar.json`, asla repoda/çıktıda) + projede **bulut izni** (`ayar.json izin.bulut`; panel yeni projede bulut özelliği açılıp onaylanınca yazar). Hepsi `sistem/baglayici/uret.py` içinde denetlenir; **ağa/anahtara doğrudan dokunma**, yalnızca bu aracı çağır.
2. Her çağrı `projeler/<ad>/bulut_gunlugu.md`'ye yazılır (ne gitti, nereye). Proje sonunda kullanıcıya çağrı sayısı ve maliyet notunu bildir.
3. Kaynak fotoğraflar buluta **gönderilmez** (ayar açık değilse); referans olarak yalnızca kendi ürettiğin görsel. Gerçek kişi/izinsiz içerik/okunur yazı-logo ürettirme.
4. Ücretli motorda `--aday` artırma (her alım faturalanır). Üretilen görsel **kanıt gibi sunulmaz**; `media/uretilen/` altında "YAPAY ZEKÂ ÜRETİMİ" kaydıyla durur.
5. İzin/anahtar yoksa **sessizce yerele düşme**: ne eksik olduğunu kullanıcıya söyle (yerel EMA seslendirme gibi yerel alternatif varsa seçenek olarak sun, kendi başına seçme).
6. MCP sunucuları (HeyGen vb.) Claude oturumuna `--mcp-config` ile eklenir (panel → Ayarlar → MCP); aynı izin ve günlük ilkeleri geçerlidir.

## 10. Durum makinesi ve onay
`durum.json` (`sistem/araclar/durum.py`): hazirlaniyor → planlama → (plan-onayi-bekliyor) → uretiliyor → **taslak-hazir** → onaylandi → final-render → platform-surumleri → teslim (+ engel). `/video` taslakta durur; kullanıcı Kurgu'da saniye bazlı not bırakır (Gönder → notları uygula, taslağı yenile) ve panelden **Onaylıyorum** der; panel `onay.json` yazar, `/final` çalışır. Onay gelmeden final render ve platform sürümleri üretme.

## 11. Dikey-öncelikli üretim
Yatay (16:9) ve dikey (9:16) birlikte planlanır: dikey platform seçiliyse hikâye tahtası sahne başına iki kompozisyon içerir, görseller iki oranda hazırlanır, dikey kadrajlar (odak noktası, güvenli kutu) planlama aşamasında belirlenir. Dikey sürüm yatayın kırpması/bulanık zemini **değildir**; `sosyal-surumler` ve `kit/useFormat` kurallarına göre yeniden kompoze edilir. Instagram Story ve diğer dikey platformların arayüz alanları yükleme ekranında doğrulanır.

