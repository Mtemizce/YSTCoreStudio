# Kurgu boru hattı (bu makine, bu kurulum)

## Yerleşim
```
<stüdyo klasörü>\                 Kurgu deposu (klon) — `kurgu` global aracı buna editable bağlı (speak aracı içerir)
  archive\                                        kullanıcının ham arşivi (dokunma)
  package.json + node_modules\             Remotion 4.0.543, HyperFrames 0.9.49, gsap, @remotion/{effects,transitions,motion-blur,shapes,rough-notation,lottie,noise}
  <proje>\                                 Kurgu projesi: project.json, brief.md, CLAUDE.md, senaryo.json
      media\foto\ fonts\ tts\ muzik\ sahne\ cizim\   medya (sahne\*.mp4 = kodla üretilen klipler)
      remotion\ (src\*.tsx, remotion.config.ts)   Remotion sahneleri; unit = kompozisyon id
      hyperframes\ (*.html, assets\, vendor\)     HyperFrames sahneleri; unit = dosya adı (uzantısız)
  Başlat.cmd (panel), Başlat.cmd claude
```
Kullanıcı yapılandırması: `sistem/ortam/kurgu-ayar/config.json` (Başlat.cmd `KURGU_CONFIG` ile depo içine yönlendirir; kurulum yazar) → `render_adaptors` (`remotion`, `hyperframes`). Proje dosyası komut taşıyamaz; `source.render` yalnızca adaptör ADI.

## Sahne değiştirme döngüsü (Kurgu notu gelince)
1. Notun `layers[].source` alanından `file` ve `unit`'i oku; notta `bounds`/`anchor` varsa konumu oradan hesapla.
2. **Kaynak dosyayı düzelt** (zaman çizelgesine yama katman koyma). Remotion: `remotion/src/<Sahne>.tsx` (ortak: `parts.tsx`, `theme.ts`). HF: `hyperframes/<unit>.html`.
3. `kurgu rerender <proje> <unit>` (MCP `rerender`): yalnızca o klip yeniden üretilir (Remotion ~15-30 sn, HF ~20-30 sn tipik bir bilgisayarda).
4. `kurgu frame <proje> <sn>` ya da `kurgu strip … --n 6` ile **bak**, sonra `kurgu notes done … --reply "seçtiğim değerler + nasıl değişir"`.
- Süre değişirse: Remotion `theme.ts` `FRAMES` + `Root.tsx`; HF `data-duration`; `project.json`'da `source.frames`, klibin `end`'i ve sonraki sahnelerin `start/end`, ses/altyazı katmanları kaydırılır (rerender yalnızca o klibin `end`'ini günceller, sonrakileri sana bırakır).
- Yeni foto: `media/foto/` (Remotion) **ve** `hyperframes/assets/foto/` (HF kendi kopyasını okur).
- Fontlar: Remotion `useFonts()` (parts.tsx) `media/fonts/`; HF `@font-face` `./assets/fonts/`.

## Yeni sahne ekleme
Remotion: `src/<Ad>.tsx` yaz → `Root.tsx`'e `<Composition id="Ad" …>` + `theme.ts FRAMES` → `project.json`'a video katmanı (`src: media/sahne/Ad.mp4`, `source:{kind:"remotion",root:"remotion",unit:"Ad",file:"src/Ad.tsx",fps:30,unit_start_frame:0,frames:N,render:"remotion"}`) → `kurgu rerender`.
HF: `hyperframes/<ad>.html` (kompozisyon id = ad; `data-duration` saniye) → katman (`kind:"hyperframes"`, `root:"hyperframes"`, `unit:"<ad>"`, `file:"<ad>.html"`, `render:"hyperframes"`). Sonra `npx hyperframes lint <ad>.html`.
Efektli Remotion sahnesi için: `assets/remotion-fx/*` → `src/fx/`; `remotion.config.ts`'de ANGLE (şu an AÇIK).

## Dikkat (denenerek öğrenildi)
- Remotion proje kökü = en yakın `package.json`; `remotion/package.json` bu yüzden var (yoksa ``'yu kök sanar, `public` yolu kayar).
- Remotion `Config.setPublicDir('../media')`; `staticFile('foto/..')`. İç içe `AbsoluteFill`/`Photo` için kap `position: relative` olmalı (aksi halde tüm ekranı kaplar).
- HyperFrames GSAP'ı yerel `vendor/gsap.min.js`'ten yükler (render ağsız/belirli); `lint` 0 hata/0 uyarı hedefle. Telemetri kapalı (`hyperframes telemetry status`).
- Windows'ta bash heredoc'a uzun/özel karakterli dosya yazarken hata verebiliyor: dosyaları Write ile yaz.
- Kurgu `rerender` adaptörleri `node` komutunu PATH'ten çalıştırır; `{root}/../../node_modules/…` göreli yol `remotion/` ve `hyperframes/` klasör derinliğine bağlıdır (proje `<proje>/` altında kalmalı).
- Python betikleri için Kurgu venv: `<stüdyo klasörü>\sistem\ortam\venv\Scripts\python.exe` (torch cu130, spandrel, ema-lightning, numpy, Pillow) ya da global `kurgu` aracının ortamı (`%APPDATA%\uv\tools\kurgu\Scripts\python.exe`: torch+ema-lightning var, spandrel yok → gerekirse `uv pip install --python <o python> spandrel safetensors`).
- Gizlilik: Kurgu hiçbir şey yüklemez; HyperFrames telemetrisi kapalı; modeller yalnızca Hugging Face'ten bir kez iner.

## DWG → görsel (✅ çalıştı)
LibreDWG 0.14 win64 (resmî GitHub sürümü; kullanıcı izniyle) `dwg2SVG.exe plan.dwg > plan.svg`. Notlar:
- `viewBox` aykırı nesnelere göre bozuk gelir → SVG yollarının %1-%99 sınırlarından kendi `viewBox`'ını hesapla (scratchpad `svg_crop.py` mantığı), y'yi çevir (`scale(1,-1)`), çizgi kalınlığını sınıra göre ver.
- MTEXT/çok satırlı yazılar atlanır (yazısız plan çıkar). Koyu zemin + altın çizgi sürümü (`#0e1013` / `#e6cc86`) filmle uyumludur: `media/cizim/kat_plani_dark.png`.
- Dosya adında kişi adı olabilir; filmde/metinde kullanma (kullanıcı onayı olmadan).
- Çizimi "çizdirmek" için SVG'yi Remotion/HF'de `stroke-dashoffset`/`evolvePath` ile animasyonla.

## Başlatıcılar
`Başlat.cmd` (stüdyo paneli: projeler, yeni proje, Kurgu editörü, Claude), `Başlat.cmd claude` (elle Claude). `kurgu setup-agent --claude --wake`: Gönder → Claude otomatik uyanır (headless, izinli araçlar: yalnızca kurgu komutları + mcp__kurgu; python/npm YOK).
