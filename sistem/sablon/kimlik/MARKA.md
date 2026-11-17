# MARKA: kilitli görsel kimlik ("slop" olmayan video için sert sınır)

> Her grafik, her sahne, her kapak bu dosyaya göre **kontrol edilir**; eleştirmen ajan (`.claude/agents/elestirmen.md`) bu dosyayı ölçüt alır.
> **Erken kilitle:** görsel tutarlılık zamanla birikir; ortada değiştirmek, baştaki küçük hatadan pahalıdır.
> Bu varsayılan sade, koyu ve altın vurgulu bir görünümdür. **Kendi markan/kimliğin farklıysa değiştir** (renk, yazı tipi, yasaklar). Bir proje farklı marka gerektiriyorsa `projeler/<ad>/MARKA.md` yaz; o proje için o geçerli olur.
> Uygulamada kaynak: `sistem/kit/theme.ts` (aynı değerler). Biri değişirse diğeri de güncellenir.

## Renkler
| Rol | Hex | Not |
|---|---|---|
| Zemin (koyu) | `#0E1013` | antrasit, saf siyah değil |
| Zemin 2 | `#171B20` | kart/panel |
| Metin | `#F4EFE6` | sıcak beyaz, saf `#FFF` değil |
| **Vurgu (TEK)** | `#C9A24D` | altın; çizgi, alt çizgi, tek kelime vurgusu. Yumuşak: `#E6CC86` |
| Sönük metin | `#B9B2A3` | ikincil bilgi |

**Tek vurgu rengi.** İkinci bir vurgu rengi başka bir marka demektir.

## Yazı tipleri (yerel dosya, OFL)
- Başlık: **Cormorant Garamond** Bold (italik: vurgu satırı, imza cümle)
- Arayüz/etiket: **Inter** Medium/SemiBold, büyük harf, geniş harf aralığı (0.25-0.6em)
- Dosyalar: `sistem/kit/fonts/` (ve proje `media/fonts/`). Türkçe karakterler (ş ğ ı İ ö ü ç â î û) doğrulanmış.
- Büyük harfe çevirirken `toLocaleUpperCase('tr-TR')`.

## Doku ve ışık
- İnce vinyet (0.35-0.5), ince gren (0.04-0.06, **sabit tohum/kare başı tohum**; gren titremesi tohumsuz olur), sıcak renk derecelendirme.
- İnce altın çerçeve çizgisi (2 px, kenardan 44 px) açılış/kapanışta; her karede olmak zorunda değil.

## Hareket karakteri
Sakin, ağırlıklı, tipografi öncelikli. Uzun kuyruklu ease-out, kısa çıkış, inen başlık **ölü durur**. Süs için hareket yok: hareket gerekmiyorsa temiz durağan kare (premium okunur; sürekli hareket "şablon" okunur).

## Yasak listesi ("şu olmasın": bu liste paletten çok iş yapar)
- Siyah üstünde neon; mor-mavi "aurora" / gradyan mesh arka planlar
- Glassmorphism, buzlu cam paneller, parlak plastik 3B
- Stok-fotoğraf insanlar, yapay gülümseyen laptop görüntüleri
- Her şeyin ortalanması, hiyerarşisiz yerleşim
- Nefes alan/süzülen/nabız atan döngülerle "hareket varmış gibi" yapmak; inen başlığın kaymaya devam etmesi
- Aynı geçişi her yerde kullanmak; sahnelerin hepsinde aynı fade+slide-up
- Emoji yığını, "WOW!", "inanılmaz", "şok" tarzı abartı metin; ünlem yığınları
- Doğrulanmamış iddia (yıl, adet, ödül, telefon, "en iyi")
- Filigranı silmek; başkasının işini/logosunu kendininmiş gibi göstermek
- Okunur yazı/logoyu yapay zekâyla "yeniden çizdirmek"

## Güvenli kenar boşlukları
- 16:9 (1920×1080): kenardan ≥ 96 px (çerçeve çizgisi hariç).
- 9:16 (1080×1920): metin ve ana özne şu kutuda: sol 120, sağ 192, üst 288, alt 672 px boşluk (konservatif ortak değer; kaynaklar birbiriyle çelişiyor, `sosyal-surumler` skill'ine bak). Arka plan görüntü tam ekran olabilir.

## Altyazı stili
- Inter SemiBold, 2-3 kelime/satır (dikey) · 7 kelime (yatay), kelime-vurgusu: aktif kelime altın, diğerleri sıcak beyaz; hafif gölge; zemin şeridi yok.
- Dikey: y ≈ %58-62 yükseklik (alt arayüzün üstünde).

## Kimlik işareti (logo/maskot)
- Dosya: `sistem/kit/logo/` (varsa). Kullanıcı vermedi → **uydurma logo yapma**, yalnızca isim yazısı (Cormorant, harf aralıklı).
- Filigranlı fotoğraf: kullanıcının kendi filigranı bilerek bırakılır.
