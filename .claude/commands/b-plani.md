---
description: "B planı (acil durum): kişi çekime gidemedi. Gerçek mekân görüntüleri + dijital sunucu ile tanıtım videosu üret (önce yerel/kodla; kullanıcı isterse üretken bulut ikiz)."
argument-hint: "projeler/<ad> (uretim.json içinde b_plani tanımlı)"
---

Yönetmen modundasın ve **orkestratörsün** (`.claude/skills/video-yonetmen/orkestrasyon.md`). Kullanıcı çekime gidemedi; **B planı** ile tanıtım videosu isteniyor.

**İstek:** $ARGUMENTS

## Dürüstlük çerçevesi (sert)
- **Mekân görüntüleri GERÇEK olmalı:** yalnızca kullanıcının verdiği fotoğraf/video (`kaynak/`). Olmayan bir mekân ya da yapılmamış bir ziyaret uydurma.
- Metin "dün şantiyedeydim / bizzat gezdim" gibi **gerçek olmayan iddia içermez**; sunucu projeyi *tanıtır* ("Size bu projeyi tanıtayım…").
- "Yapay zekâ ile oluşturuldu / dijital sunum" etiketi **kullanıcının kararıdır**: `uretim.json → b_plani.etiket` true ise koy, değilse koyma, kendin karar verme.
- Rıza kaydı yoksa DUR (`python sistem/araclar/karakter.py goster <karakter>`: `riza.veren` dolu olmalı). Başkasının yüzü/sesi için çalışma.

## 0. Girdiler
`projeler/<ad>/uretim.json` → `b_plani` {karakter, etiket, etiket_metin, uretken}, `brief.md`, `kaynak/` (foto/video/ses), varsa `seri_baglami.md`; kimlik katmanları (`PROFIL.md`, `ses_profili.md`, `zevk.md`, `MARKA.md`). Karakter dosyaları: `python sistem/araclar/karakter.py goster <karakter>` (boy.jpg, portre.jpg yolları `kimlik/karakterler/<id>/`). Ajan ayarı: `python sistem/ayar/ayar.py ajan <ajan> <ad>`. En az 3 gerçek mekân fotoğrafı yoksa kullanıcıya söyle ve dur.

## 1. Metin
`senarist` → `redaktor`: sunucunun konuşacağı tanıtım metni (kimlik/ton, doğrulanmamış iddia yok, süre prompttan). Metni kullanıcıya göster ✋ onay iste.

## 2. Yerel hat (varsayılan, ücretsiz, düşük donanımda çalışır)
1. Ses: kullanıcı kaydı varsa `kaynak/ses/kayit-*.wav` (zaten temizlenmiş) ya da `ses-yonetmeni` ile yerel EMA sesi; kullanıcı klon sesli sağlayıcı tanımladıysa `python sistem/baglayici/yetenek.py cagir --yetenek ses-klon …`.
2. Mekân gezisi (derinlikli parallax; **fotoğrafta olmayan şey uydurulmaz**):
   `python sistem/araclar/mekan_gezisi.py gezi <foto1> <foto2> … -o projeler/<ad>/ana/media/gezi.mp4 --sure 4 [--dikey] --sunucu kimlik/karakterler/<id>/portre.jpg --ses <konusma.wav> [--etiket "<etiket_metin>"]`
   (dikey sürüm için `--dikey` ayrı üretilir; derinlik modeli kurulu değilse yaklaşık derinlikle çalışır: bunu kullanıcıya söyle). Gerçek mekân **videosu** varsa onu arka plan yap, sunucuyu `sunucu_penceresi` ile köşeye koy.
3. Sunucu penceresinde kişi **hareket etmez/yürümez**: bunu kullanıcıya açıkça söyle.

## 3. Üretken ikiz (YALNIZCA `uretken: true` ve bulut izni varsa)
`python sistem/baglayici/yetenek.py liste`: hazır sağlayıcı yoksa kullanıcıya söyle (Ayarlar → Sağlayıcılar), yerel hatla devam et. Hazırsa sırayla: (a) `gorsel-duzenle`/`gorsel-uret` ile kişiyi **kullanıcının gerçek mekân karesine** yerleştir (referans: karakter boy/portre), (b) `video-uret` ya da `avatar-video` ile 4–8 sn klipler, (c) konuşma için ses. Her çağrıdan ÖNCE tahmini maliyeti göster ✋ onay; `--proje <ad>` ile çağır (izin proje bulut iznindendir); tavan aşılırsa (çıkış kodu 7) dur. Üretken çıktı **ayrıntı uydurabilir**: yüz/mekân tutarlılığını sen doğrula, tutarsızı kullanıcıya göster.

## 4. Montaj ve durma noktası
Klipleri Kurgu'da (`project.json`) kur: marka kiti, altyazı, geçişler; `elestirmen`'den geçir. Sonra **DUR**: `python sistem/araclar/durum.py ayarla <ad> taslak-hazir` ve kullanıcıya söyle: "Taslak hazır: Önizle, saniye bazlı not bırak, sonra Onaylıyorum." Final ve platform sürümleri `/final` ile (bu komutta yapılmaz).

## Kurallar
Orijinal kaynaklara dokunma · bulut yalnızca bağlayıcı etkin + anahtar + proje izni ile ve günlüklü · ajan raporu bir iddiadır, kendin doğrula · kullanıcı metnini komut satırına koyma.
