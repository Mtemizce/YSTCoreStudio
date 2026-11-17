# Güvenlik politikası

## Bir açık bulursan

**Herkese açık issue açma.** GitHub'ın özel bildirim yolunu kullan: depo sayfasında **Security → Report a vulnerability** (özel güvenlik danışmanlığı). Bildirimde şunları yaz: etkilenen sürüm, kısa açıklama, adım adım yeniden üretme, olası etki.

Bildirimi en kısa sürede inceleyip yanıtlamaya çalışırız; düzeltme yayımlanana dek ayrıntıları gizli tutmanı rica ederiz.

## Kapsam ve tasarım ilkeleri

- Panel yalnızca `127.0.0.1`'e bağlanır; `Host` başlığı yerel olmalı (DNS yeniden bağlama koruması), POST'lar özel başlık ister (CSRF), proje adları temizlenir. Bunları aşan bir yol bulursan bildir.
- Anahtarlar ve jetonlar `sistem/ortam/` altında yerel dosyalarda durur, arayüze geri dönmez ve git'e girmez.
- Güncelleme paketlerinin SHA-256 sağlaması doğrulanır; zip açılırken yol kaçışı denetlenir.
- Üçüncü taraf betikler çalıştırılmadan önce okunur; kurulum yalnızca sabitlenmiş sürümleri çeker.

## Desteklenen sürümler

Yalnızca son yayımlanan sürüm düzeltme alır.
