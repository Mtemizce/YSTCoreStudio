---
description: "Arşivdeki fotoğrafları bir kez anlamlandır (aşama, konu, açıklama, kullanılabilirlik) ve veritabanına yaz; sonraki videolar taramasız bu veriden seçer."
argument-hint: "[yıl aralığı, örn. 2022-2024] [proje klasörü ya da anahtar kelime]"
---

Arşiv analizi. Kapsam: $ARGUMENTS (boşsa kullanıcıya sor: hangi yıllar/hangi klasörler?)

Sen orkestratörsün (`.claude/skills/video-yonetmen/orkestrasyon.md`). Arşiv dosyaları yerinde kalır; analiz yalnızca veritabanına (`sistem/ortam/arsiv/arsiv.db`) yazılır.

1. **Durum:** `python sistem/arsiv/arsiv.py durum` → arşiv ayarlı ve **bağlı** mı, dizin dolu mu? Değilse dur ve kullanıcıya ne yapacağını söyle (panel → Arşiv → ayarla/tara). Hiç taranmadıysa: `python sistem/arsiv/arsiv.py tara` (uzun sürebilir, kesilirse devam eder; sor).
2. **Otomatik ölçüm** (yerel, ücretsiz; çözünürlük, keskinlik, ışık, yinelenen, video süre/çözünürlük): `python sistem/arsiv/analiz.py oto --yil <a-b>` (gerekirse `--proje <klasör>`). Çıktıdaki `kullanilabilir/kullanilamaz/yinelenen/bagil_bulanik` sayılarını kullanıcıya bildir.
3. **Kapsamı çıkar:** `python sistem/arsiv/analiz.py ozet --derinlik 2` → hangi proje klasörlerinde kaç kullanılabilir fotoğraf var, kaçı Claude analizi bekliyor. Çok büyükse (yüzlerce sayfa) **maliyeti söyle** ve kullanıcıdan kapsam onayı al: bir kontakt sayfası ≈ 24 fotoğraf; yüzlerce kareyi anlamlandırmak çok sayfa demektir. Öncelik: kullanıcının istediği yıl/projeler.
4. **Anlamlandırma:** `arsiv-analisti` ajanını çağır (ayar: `python sistem/ayar/ayar.py ajan arsiv-analisti` → `model`/`effort`'u açıkça ver). Birbirinden bağımsız klasörler için **paralel** birden çok ajan (her biri farklı klasör). Görev paketine kapsamı, sayfa sınırını ve çıktı sözleşmesini (veritabanına `analiz.py yaz`) yaz.
5. **Doğrula (sen):** `python sistem/arsiv/analiz.py ozet` ile kapsam arttı mı; `python sistem/arsiv/analiz.py uygun --yil <a-b> --asama yapim --limit 8` ile örnek sonuçlara bak ve **2-3 dosyanın açıklamasını gerçekten kontrol et** (arşivden küçük resim: `bekleyen` sayfası ya da dosyayı aç): ajan raporu bir iddiadır.
6. Kullanıcıya özet: kaç dosya anlamlandırıldı, kaçı kullanılabilir, hangi aşamalardan ne kadar (öncesi/yapım/sonrası), eksik kalan projeler, kullanılamayan dosyaların başlıca nedenleri.

Kurallar: arşive yazma/silme/taşıma yok · bulut yok · müşteri adı/adres/yüz tanımlama yok · eşikler arşive uymuyorsa `sistem/ortam/arsiv/esikler.json` ile ayarla (örn. `{"keskin_kotu": 12}`) ve `oto`yu yeniden çalıştır.
