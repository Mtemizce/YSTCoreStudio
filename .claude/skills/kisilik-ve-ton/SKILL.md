---
name: kisilik-ve-ton
description: kimlik/PROFIL.md'yi (kişilik, konuşma tarzı, değerler, hedef kitle, sınırlar) kullanıcının video prompt'u ve kaynaklarıyla birlikte analiz edip projeye özel bir "ton rehberi" üretir; prompt'u değerlendirir (eksik/çelişki/varsayım), videonun sesi, ritmi, hook'u, altyazısı ve müziği için gerekçeli kararlar verir. Yeni video başında, profil değiştiğinde ya da "benim tarzıma uygun olsun" dendiğinde kullan.
---

# Kişilik ve ton analizi

Amaç: videoyu "herkes için genel" değil, **bu kişi için** yapmak: konuşma biçimi, tempo, mizah, görsel zevk, sınırlar; ve bunu **gerekçeyle** göstermek.

## 1. Oku (dört katman; güven sırası: kullanıcının sözü > ölçüm > beyan)
1. **Beyan:** `kimlik/PROFIL.md` (tamamı). Boş alanları "bilinmiyor" say; **uydurma**. §15 (doğrulanmış gerçekler) dışında rakam/yıl/ödül kullanma; §16 telaffuz sözlüğünü ses planına aktar.
2. **Kanıt:** `kimlik/ses_profili.md` (gerçek yazı/ses örneklerinden ölçülen ritim, hitap, dolgu sözcükler, örnek cümleler). Beyanla çelişirse **ölçüm kazanır** ve bunu söylersin ("beyanın resmi, yazdıkların gündelik: gündelik yazıyorum"). Dosya yoksa ya da güvenilirlik "zayıf" ise ton kararlarının **güvenini düşür** ve kullanıcıdan gerçek örnek iste (`kimlik/ornekler/`).
3. **Zevk:** `kimlik/zevk.md` (A/B testinde seçilen/reddedilen cümle stilleri ve müzik) ve `kimlik/ogrenilenler.md` (önceki projelerde öğrenilen kurallar: bağlayıcıdır).
4. **Bağlam:** proje `brief.md` (tarif + sihirbaz cevapları), kullanıcı prompt'u, `hazir/envanter.json`.

## 2. Prompt'u değerlendir (brief.md'ye yaz)
Her satır: ✅ net · ⚠ varsayım · ❓ eksik (kritikse sor). Kontrol:
- **Amaç/CTA:** izleyici sonunda ne yapacak? (profil §7 ile uyumlu mu)
- **Kitle ve platform:** kim, nerede, sesli mi sessiz mi
- **Süre:** ana video + her platform sürümü (varsayılan: ana 30-60 sn; Reels 20-35; TikTok 20-35; Shorts 20-45)
- **Ton:** profil ile çelişiyor mu? ("kurumsal" isteniyor ama profil mizahlı ve samimi → çatışma bayrağı)
- **Zorunlular / yasaklar:** mutlaka olacak ve asla olmayacak şeyler (profil §5, §11)
- **Kaynak yeterliliği:** envanter: kaç görsel, çözünürlük, yönelim; konu için yeterli mi, hangi kare eksik
- **Doğrulanabilirlik:** metinde geçecek her iddia kaynakta var mı
En fazla **3 kritik soru**; kalan her şey makul varsayım + işaret.

## 3. Ton rehberi üret (`projeler/<ad>/ton_rehberi.md`)
Şablon (her karar yanında **profil izi**: hangi satırdan çıktı):
```
# Ton rehberi: <proje>
## Kişilik özeti (3 cümle, profilden; kopyala-yapıştır değil, sentez)
## Karar tablosu
| Alan | Karar | Gerekçe (PROFIL §…) | Güven |
Ses/anlatım      | persona, hitap (sen/siz), cümle uzunluğu, mizah dozu, yasak kelimeler | §3 §4 | yüksek/orta/varsayım
Tempo            | kelime/dk, duraklama stili (voice-direction.md) | §4 tempo, §3 enerji |
Kurgu ritmi      | ortalama çekim süresi, geçiş çeşit sayısı, hareket miktarı | §3 enerji/resmiyet |
Görsel dil       | kimlik/MARKA.md ile ilişki, ek vurgular, "olmasın" listesi | §8 |
Hook stili       | hook-ve-kapak'tan hangi açı | §3 mizah, §6 kitle |
Altyazı          | stil/yoğunluk | §9 sessiz izleme |
Müzik            | hava, tempo, kaynak kuralı | §9 |
CTA              | cümle (kullanıcının sözleriyle) | §7 |
## Çakışmalar ve riskler  (prompt ↔ profil ↔ marka ↔ kaynak)
## Varsayımlar (onay bekleyenler)
## Kullanılacak kullanıcı ifadeleri (PROFIL §4'ten birebir; videoda kullanılabilir olanlar)
## Yasaklı ifadeler/kalıplar
```
Kurallar:
- Profil kaba/ortalama ise ("samimi ama profesyonel") **örnek cümlelere** bak: gerçek tonu onlar verir. Örnek yoksa bunu en büyük eksik olarak işaretle ve **sorulacak soru #1** yap ("bu videoda kendi cümlenle 2-3 satır yazar mısın?").
- Enerji ↔ ritim eşlemesi (başlangıç, sonuçla doğrula): enerji 1-3 → ortalama çekim 3-5 sn, 3 geçiş türü, ağırlıklı durağan başlık; 4-7 → 2-3.5 sn; 8-10 → 1-2 sn, hızlı vuruşlar. Hızlı tempo ≠ çok efekt.
- Resmiyet ↔ dil: yüksek → "siz", uzun/ölçülü cümle; düşük → "sen", kısa cümle, günlük kelime. **Argo/emoji dozu profilden**, varsayılan sıfır.
- Mizah yalnızca profil izin veriyorsa ve çevirisi/bağlamı güvenliyse; mizah evrensel değildir, hedef kitleye göre.
- "Hissettirmek istediğim 3 duygu" (§13) hook, renk derecelendirme, müzik ve hareket ağırlığını yönetir; her duyguyu en az bir somut karara bağla.
- Kullanıcı kendi sesini kaydedecekse: kayıt metnini ritim planıyla (satır başına süre) ver.

## 4. Sonuç ve onay
Yönetmene **tek ekranda** özetle: 5 madde karar + 3 çakışma/risk + varsayımlar. Onay ya da notla güncelle. Profil değiştiyse **eski ton rehberlerini eskimiş** işaretle.

## 5. Gizlilik
`kimlik/PROFIL.md` kişiseldir: dışarıya gönderilmez, uzak API'ye yazılmaz, başka projelere/commit'lere kopyalanmaz; ton rehberinde yalnızca gereken ifadeler alıntılanır.
