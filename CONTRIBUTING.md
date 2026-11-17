# Katkı rehberi

YSTCoreStudio'ya katkı yapmak istediğin için teşekkürler. Küçük düzeltmeler de değerlidir.

## Başlamadan

- **Hata bildirimi:** Issues → *Hata bildirimi* şablonunu doldur. İşletim sistemi, Python/Node sürümü ve `python sistem/araclar/saglik.py` çıktısı çok yardımcı olur. **Günlüklere ve ekran görüntülerine kişisel bilgi (kullanıcı adı, yol, API anahtarı) sızmasın.**
- **Güvenlik açığı:** herkese açık issue açma; [SECURITY.md](SECURITY.md).
- **Büyük değişiklik:** önce bir issue aç, fikri konuşalım.

## Geliştirme ortamı

1. `Başlat.cmd` (Windows) ya da `bash baslat.sh` (Linux/macOS) kurulumu yapar (Python sanal ortamı, Node paketleri, modeller; ~7 GB).
2. Testler (kurulu sanal ortamın Python'uyla): `python sistem/testler/calistir.py`. `--canli` ayrıca çalışan panel ve kurulu modeller isteyen testleri çalıştırır. Testler ayarları ve geçici `zz-*` projelerini yedekleyip geri yükler; panel kapalıyken çalıştırılmalıdır.
3. Arayüz tek dosyadır: `sistem/panel/index.html`; sunucu `sistem/panel/panel.py` + `ek_api.py` (yalnızca standart kütüphane).

## Kurallar

- **Her değişiklikle test:** yeni davranış için `sistem/testler/` altına test ekle; bir hatayı düzeltiyorsan onu yakalayan test yaz. Testler ağ ve gerçek model gerektirmemeli (gerekiyorsa `canli_` önekiyle).
- **Dürüst iddia:** denemediğin şeyi belgede "çalışır" diye yazma; denendiği platformu belirt.
- **Kişisel veri yok:** depoya ad, e-posta, yerel yol, anahtar, müşteri dosyası girmez. Kimlik dosyaları (`kimlik/`) git'e girmez.
- **Üçüncü taraf kod/içerik:** lisansı (MIT, Apache-2.0, OFL, CC0, CC-BY…) uygunsa ekle; kaynak, lisans ve yaptığın değişikliği `.claude/skills/THIRD_PARTY_NOTICES.md` ve README atıf tablosuna yaz, lisans metnini yanına koy. Lisansı belirsiz içerik kabul edilmez. Betikleri çalıştırmadan önce oku (`python sistem/araclar/skill_tara.py <klasör>` kaba bir elektir, güvence değildir).
- **Yerel ve gizli:** varsayılan olarak her şey yerelde çalışır; bulut servisleri kapalı başlar ve açık izin ister. Bu ilkeyi bozan değişiklik kabul edilmez.
- **Commit mesajları:** Türkçe ya da İngilizce, ne ve neden.

## Lisans

Katkın, depoyla aynı lisansla (MIT) yayımlanır.
