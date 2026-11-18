---
description: "Dizi bölümü üret ya da düzenle: seri bağlamını, model setini ve senaryoyu okuyup bölümü kullanıcıyla birlikte, adım adım yap."
argument-hint: "projeler/<seri>-s01b01 (panelde Seriler sayfasından açılan bölüm projesi)"
---

Yönetmen modundasın. Bir dizi bölümü üzerinde çalışıyorsun:

**Bölüm projesi:** $ARGUMENTS

Bu komut `/video` akışının dizi sürümüdür: önce serinin bağlamını oku, kullanıcıya bölümü **sun ve onaylat**, sonra `/video` adımlarını uygula. Orkestrasyon kuralları (`.claude/skills/video-yonetmen/orkestrasyon.md`) aynen geçerlidir.

## 0. Oku
- `projeler/<ad>/seri_baglami.md`: seri açıklaması, görsel stil, karakterler, **model seti**, bu bölümün senaryosu, önceki bölüm özetleri.
- `projeler/<ad>/seri_model_seti.md`: bu bölümde görünen karakter/nesne/mekânlar; onaylı görselleri `kaynak/foto/model-*.png` olarak projededir.
- `projeler/<ad>/kaynak/belge/senaryo.md` (varsa): kullanıcının yazdığı ya da önceki bölümlerden getirdiği senaryo/kurgu. Onu temel al, uydurma.
- `projeler/<ad>/uretim.json` → `seri` (hangi dizi, sezon, bölüm), `brief.md`, `marka_kullanimi.md` (varsa).

## 1. Bölümü kullanıcıya sun ve onaylat ✋
Kısa bir özet yaz ve sor (bölüm bölüm ilerle, hepsini birden yapma):
- "Şimdi **<Dizi> S01B02 "<ad>"** bölümünü yapıyoruz." Sahne akışı (sahne adı + bir cümle), süre tahmini.
- Hangi karakter/nesne/mekân hangi sahnede görünecek (model setinden).
- Eksik olanlar: görselsi olmayan model, senaryoda geçip model setinde olmayan karakter.
Kullanıcı "şöyle olsun" derse planı değiştir; onayı almadan üretime geçme. Çelişki (önceki bölümle, model tarifiyle) görürsen sor.

## 2. Storyboard

Bölüm özetinden sahne akışını ve onaylı model referanslarını `hikaye_tahtasi.md` dosyasına yaz. Eksik varlığı plan satırında belirt. Panelde storyboard onayını bekle ve bu turu bitir. Onaydan önce aşağıdaki üretim adımlarını çalıştırma.

## 3. Eksik görselleri proje tercihiyle üret ve kontrol et
`medya.image` seçimi yerel ise (eski bölümde tercih yoksa mevcut iş akışını koru) `python sistem/araclar/gorsel_kutuphane.py stiller` ve `... liste --seri <seri-id>`. Üretim: `python sistem/araclar/gorsel_kutuphane.py uret "<sahne ya da karakter istemi>, <modelin sabit istem eki>" --stil <serinin görsel stili> --seri <id> --sezon N --bolum M --adet 2 --bekle`.
**Her görseli kendin kontrol et** (dosyaya bak; `kalite` ölçütü yalnızca ipucudur): yüz/el bozuk mu, tarif tutuyor mu, stil serinin geri kalanıyla uyuyor mu, okunur yazı var mı. Kötüyse `yeniden <id>` (yeni tohum) ya da istemi düzelt; iyiyse kullanıcıya **göster ve onaylat**, sonra `onayla <id>`. Onaylanan görsel kullanıcının arşivine girer. Yeni model görseli onaylandıysa `python sistem/araclar/seri.py model-gorsel <seri> <model-id> <görsel-id>` ile modele bağla. Yerel model kurulu değilse bunu söyle; bulut görsel yalnızca projede izin varsa.
Z-Image-Turbo yalnızca metinden görsel üretir (kimlik/yüz kilidi yoktur): tutarlılık, **onaylı görselleri doğrudan kullanmak** ve sabit istem ekini her istemde aynen eklemekle sağlanır; "aynı kişi" iddiasında bulunma.

`medya.image` mevcut kaynaksa onaylı model görsellerini ve mevcut arşivi kullan. Kurgu veya API seçilmişse ilgili uzman seçilen yöntemle çalışsın; otomatik olarak Z-Image’a geçme.

## 4. Üretim

Bölüm projesini standart Kurgu ve panel sohbeti üzerinden yürüt. Yerel görsel/video/müzik gerektiğinde ilgili alt ajana kısa sahne görevi ver. `medya_gorevi.py` aynı hikâye tahtasını, açık Kurgu biçimini ve bölümün seri bağlamını kullanır. Onaylı model görselleri süreklilik için önceliklidir. Taslak ve final kararları panelde alınır.
`/video` akışının 1-3. adımları: planlama (senarist, redaktör), üretim (sahne yapımcısı: model görsellerini sahnelere yerleştir, `marka_kullanimi.md` kurallarına uy), taslak, eleştirmen, **dur** (`durum.py ayarla <ad> taslak-hazir`). Final render onaydan sonra `/final` ile.

## 5. Bölüm bitince
Kullanıcı bölümü onayladıysa 3-5 cümlelik **gerçek** özeti yaz: `python sistem/araclar/seri.py ozet <seri> <sezon> <bölüm> "<özet>"` (sonraki bölüm bunu okur). Bölüm düzenleme isteğinde mevcut `ana/project.json` ve render'ı bozma: yalnızca istenen sahneleri değiştir, önceki özeti güncelle.

## Kurallar
Üretimde internetten materyal yok · model setindeki görselleri ve tarifleri değiştirme · her bölüm kendi projesindedir; başka bölümün dosyasına dokunma · uydurma olay/kişi yok.
