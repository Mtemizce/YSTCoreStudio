---
description: "Stüdyo sağlık kontrolü: ortam, paketler, varlıklar, ajan/skill tanımları (ve istenirse ajanların canlı yoklaması)."
argument-hint: "[--canli] [--proje <ad>]"
---

`python sistem/araclar/saglik.py $ARGUMENTS` çalıştır ve sonucu özetle.
- Varsayılan: statik kontroller (ücretsiz, hızlı). Kırmızı (HATA) satırları nedeniyle ve çözümüyle listele.
- `--canli`: her ajan gerçekten bir kez çağrılır (küçük bir token maliyeti vardır): yanıt veriyor mu, `model:` doğru mu.
- `--proje <ad>`: o projede her aşamanın bıraktığı dosyalara bakar (üretim hattı gerçekten çalıştı mı).
Sonucu **bir iddia gibi** değil, kanıtla (çıkan satırlar) bildir.
