---
name: video-yonetmen
description: "Stüdyonun yönlendirici skill'i. Kullanıcı yeni bir video istediğinde (konu + foto/video + serbest prompt) kişilik profiline, markaya ve kaynaklara göre profesyonel, \"slop\" olmayan ana video (16:9) ve ondan TikTok / Instagram Reels / YouTube Shorts sürümlerini üretir. Hepsi yerelde (Kurgu + Remotion + HyperFrames + ffmpeg + EMA Lightning). Tetikleyiciler: \"yeni video\", \"tanıtım filmi\", \"reels/tiktok/shorts yap\", \"bu fotoğraflarla video\", \"videoyu platformlara uyarla\", /video, /sosyal. Önce bunu oku."
---

# Video Yönetmen: uçtan uca akış

**İlke:** İnsan yönetmen ve kalite kapısıdır; sen **orkestratörsün**: ağır üretimi alt ajanlara verir, her teslimi **kendin doğrular**, kararları sen alırsın. Sen yönetmenin yerine **zevk dayatmazsın**; profil, marka ve kaynaklardan çıkardığın gerekçeli kararları sunarsın. Hiçbir şey stüdyo dışına çıkmaz (bulut yok, hesap yok, telemetri yok).
**Devir ve denetim kuralları (görev paketi, doğrulama, çalışma günlüğü, durma kuralları, öğrenme döngüsü): `orkestrasyon.md` (bu klasörde). Her ajan çağrısını `projeler/<ad>/calisma_gunlugu.md`'ye işle.**

## Üretmeden önce DÖRT KARAR (hyperframes-video-director'dan; kısa yaz, deneme yazma)
1) İzleyicide bu videoda **ne değişir?** (tek cümle) 2) **Son karenin hissi** ne? 3) **Tek cesur seçim**: görsel fikir, ritim ya da geçiş dili 4) Bilerek **yapmayacaklarım**. Plan "ortada metin + tekrar eden fade-up" ise kuruluma geçmeden kamera/yerleşim/geçiş/ritimden birini değiştir. Cevaplar `brief.md`'ye girer.

## Tasarım planı ve "jenerik varsayılan" kontrolü (frontend-design, Anthropic, Apache-2.0)
Sahneleri yazdırmadan önce `.claude/skills/frontend-design/SKILL.md` ilkelerini **videoya uyarla** (web'e özgü kısımlar hariç): (1) konuyu/kitleyi/işi tek cümleyle yaz; (2) küçük bir token planı çıkar (4-6 adlandırılmış renk, yazı tipi rolleri, yerleşim fikri, ilkeler: `kimlik/MARKA.md` renk ve yazı tipini zaten kilitler, plan onun içinde kalır); (3) planı brief'e karşı sına: "bunu her benzer videoya yazardım" diyorsan o kısmı değiştir ve ne değiştirdiğini söyle; (4) cesareti **tek yere** harca, gerisi sakin; (5) hareketi seyrek ve nedenli kullan (her bölümde kayarak giriş = AI gibi okunur). Jenerik işaretler: krem + toprak rengi aksan, koyu zemin + tek neon aksan, aynı yuvarlaklık/gölgeyle özdeş kartlar, her başlığın üstünde büyük harfli etiket, tek kelimeyi vurgulama alışkanlığı (kullanıcı özellikle istemedikçe; bu stüdyoda 4 kelimelik hook başlığı gibi bilinçli kullanım serbest). **Kullanıcının/brief'in sözü her zaman kazanır.**

## Girdiler (hepsi birlikte okunur; çelişkide sıra: kullanıcının sözü > ölçüm > beyan)
1. **Beyan:** `kimlik/PROFIL.md` (kişilik, ses, kitle, mesajlar, çağrı, izinler, **§15 doğrulanmış gerçekler**, **§16 telaffuz ve çalışma tercihi**, §17 anlatı) → `kisilik-ve-ton`
2. **Kanıt:** `kimlik/ses_profili.md` (gerçek yazı/ses örneklerinden ölçülen ritim, hitap, dolgu sözcükler; yoksa `sistem/araclar/ses_profili.py`) ve `kimlik/ornekler/`
3. **Zevk:** `kimlik/zevk.md` (A/B zevk testi: beğenilen/reddedilen cümle ve müzik) ve **`kimlik/ogrenilenler.md`** (önceki projelerden öğrenilen kurallar: ilk okunacaklardan)
4. `kimlik/MARKA.md` (+ varsa proje `MARKA.md`): kilitli görsel kimlik + yasak listesi → `marka-kilidi`
5. Prompt'ta/brief'te **adı geçen müzik, resim, video ya da dosya** varsa önce kullanıcının arşivinden bul ve projeye al: `python sistem/arsiv/arsiv.py bul "<ad>" --tur muzik|resim|video|dosya --kopyala projeler/<ad>` (3 = belirsiz/yok → kullanıcıya sor). Projenin `brief.md`'si: kullanıcının tarifi ve **sihirbaz cevapları** (seslendirme, müzik, ton, süre, çağrı, "mutlaka/asla" notları: kullanıcı beyanıdır, tekrar sorma; çelişki varsa sor) + `kaynak/` ve `hazir/` (panel hazırlar; arşivden seçilen dosyalar `kaynak/arsiv_secim.json` ile izlenir)
Eksik katman varsa (`python sistem/araclar/kimlik_olc.py`) bunu yönetmene **bir kez** söyle ve varsayımla ilerle (varsayımları `brief.md`'de işaretle).

## Akış (kapılı: ✋ = insan onayı olmadan ilerleme)
| # | Adım | Kim | Çıktı |
|---|---|---|---|
| 0 | **Hazırlık:** `kimlik/PROFIL.md` boş/yetersizse en fazla 3 kritik soru sor; yoksa varsayımla ilerle ve işaretle | ana oturum | — |
| 1 | **Prompt değerlendirme + kaynak envanteri:** `sistem/araclar/medya_envanteri.py` (foto/video/ses); **belge türleri (.dwg .pdf .docx .xlsx): panel/`yeni_proje.py` bunları `projeler/<ad>/hazir/belge/` altına çevirir** (elle: `sistem/araclar/belge_al.py <dosya|klasör> -o projeler/<ad>/hazir/belge`; DWG → koyu/açık PNG + `_yakin`, PDF → sayfa PNG + metin, Word → .md, Excel → .csv + özet; `belgeler.md`'yi oku; .doc/.xls desteklenmez, OCR yok); eksik/çelişen noktaları listele | ana oturum (+ `gorsel-iyilestirici`) | `projeler/<ad>/brief.md`, `envanter.json`, kontak sayfası |
| 2 | **Ton rehberi:** profil analizi, çakışma bayrakları, gerekçe izi | `kisilik-ve-ton` | `ton_rehberi.md` |
| 3 | **Senaryo + hikâye tahtası** (zaman → ekranda ne → işi → çıkış geçişi); hook (ilk 3 sn); ses satırları | `senarist` ajanı | `senaryo.md`, `hikaye_tahtasi.md` |
| ✋ | **Yönetmen onayı:** brief + ton + tahta tek ekranda özetlenir | ana oturum | onay/not |
| 4 | **Medya iyileştirme** (düşük çözünürlüklü foto → Real-ESRGAN), kaba kurgu gerekiyorsa `kaba-kurgu` | `gorsel-iyilestirici`, ana oturum | `media/foto/` |
| 5 | **Sahneler:** Remotion/HyperFrames kodu, `sistem/kit/` bileşenleri, still ile kontrol, `kurgu rerender` | `sahne-yapimcisi` (sahne başına paralel olabilir) | `media/sahne/*.mp4` |
| 6 | **Ses:** seslendirme planı → `voice_studio.py`, müzik (lisanslı/telifsiz, kaynak kaydı), SFX, miksaj | `ses-yonetmeni` | `media/tts`, `muzik`, `ses_plani.md` |
| 7 | **Montaj (Kurgu `project.json`)** ana 16:9; taslak render | ana oturum | `taslak.mp4` |
| 8 | **Bağımsız eleştirmen turu** ("üreten ≠ yargılayan") | `elestirmen` ajanı (taze bağlam) | `kalite_raporu.md` (SHIP / DÜZELT listesi) |
| ✋ | Yönetmen taslağı izler/dinler, not verir (Kurgu editöründe not + Gönder) | insan | notlar |
| 9 | Düzeltmeler → tam kalite render → ana video | ana oturum | `cikti/ana_16x9.mp4` |
| 10 | **Platform sürümleri** (TikTok, Reels, Shorts): yeniden kompozisyon, altyazı, ses, kapak, açıklama/etiket | `sosyal-kesici` ajanı + `sosyal-surumler` | `cikti/<platform>/…`, `paylasim_<platform>.md` |
| 11 | Son eleştirmen turu (her sürüm) + ölçüm raporu | `elestirmen` | `kalite_raporu.md` güncel |

Ajanlar yalnızca `.claude/agents/` altındaki tanımlarla çağrılır. **Her çağrıda `model:` açıkça verilir** (fable-orchestration ilkesi: pahalı ana modelin token'ı yargıya gider, hacim ucuz katmana):
`senarist`/`elestirmen` → opus · `sahne-yapimcisi`/`ses-yonetmeni`/`sosyal-kesici` → sonnet · `gorsel-iyilestirici` (mekanik) → haiku. Ajan raporu bir **iddiadır**: kareye/ölçüme bakmadan "tamam" deme.

## Proje klasörü
```
projeler/<ad>/
  kaynak/{foto,video,ses,belge}/   kullanıcının orijinalleri (dokunma)
  hazir/                           envanter.json + kontak sayfası, belge çıktıları (belge/…): DWG→PNG, PDF→PNG+md, Word→md, Excel→csv
  brief.md  ton_rehberi.md  senaryo.md  hikaye_tahtasi.md  ses_plani.md  kalite_raporu.md
  ana/  reels/  tiktok/  shorts/   her biri bir Kurgu projesi: project.json, media/{foto,foto_orijinal,sahne,tts,muzik,fonts}, remotion/, hyperframes/, ses/, cikti/
  cikti/                           TESLİM: bitmiş videolar, kapaklar, paylasim_<platform>.md  (render sonrası ilgili biçimin cikti/ dosyasını buraya kopyala)
```
Yeni proje: panelden (Başlat.cmd) ya da `python sistem/araclar/yeni_proje.py <ad> --tarif "…" --kaynak <yollar> --format ana reels` (şablondan açar). Mevcut projeye yeni biçim: `… <ad> --format tiktok`.

## Sert kurallar
- **Doğruluk:** uydurma müşteri/yıl/adet/ödül/telefon yok. Kaynak yoksa "kavram filmi" etiketi ya da o satır yok.
- **Sessiz izlemede anlaşılır** (altyazı/tipografi taşır): bitişte izleyici ne yaptığını ve ne yapacağını anlar.
- **Slop yok:** `kimlik/MARKA.md` yasak listesi ve `kurgu-video-studio` kalite kapısı. "Daha çarpıcı" = daha çok efekt değil, daha net fikir + ritim + kontrast.
- **Yerel:** bulut servis, hesap, anahtar, telemetri yok; model indirmeleri (HF) yalnızca ağırlık dosyası olarak ve bir kez.
- **İzin/gizlilik:** kişi/çocuk yüzleri `kimlik/PROFIL.md` §11; belirsizse `notes_ask`/soru.
- **Headless uyanma modunda** python/npm/ffmpeg yok: yalnızca `kurgu` komutları. Üretim işleri interaktif oturumda.
- İnsanın elle yaptığını koru: `changes.md`, `.kurgu/state.json` önce okunur (Kurgu kuralı).

## Hızlı başvuru
- Karar tablosu/teknik: `kurgu-video-studio` (user-level) · hareket/Remotion: `remotion-best-practices` · HTML sahne: `hyperframes` · premium kalite çıtası ve Gauntlet: `business-motion-film` · platform: `sosyal-surumler` · hook/kapak: `hook-ve-kapak`.
