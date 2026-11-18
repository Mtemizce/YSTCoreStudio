# Hareket ve render doğrulaması

## Açılış karesi

Lansman, vitrin ve portfolyo için açılış karesinde konu ve görsel odak seçilebilir olmalı. Encode edilmiş taslağı ölç: `python sistem/araclar/montaj_olcum.py ilk-kare projeler/<ad>/ana/cikti/taslak.mp4 projeler/<ad>/hazir/ilk-kare.png`. PNG dosyasını aç. Siyah/düz kare uyarısını, okunabilirliği, kadrajı ve doğru ürünün gösterildiğini kontrol et. Siyah giriş stilin parçasıysa raporda belirt. Efektleri açılış, hareket ortası ve çıkış karelerinden kontrol et.

## Hareket

Kinetik tipografide Remotion `Captions` bileşenini `kinetic` ile ve gerçek kelime zamanlarıyla kullan. Başlığı ve satış iddiasını tek görsel odakta tut. HyperFrames sahnelerinde mevcut GSAP motorunun zaman çizelgesini kullan, hareketi render karesine bağla. Arayüz turunda gerçek ekran ve vurgu katmanı, modüler vitrinde görsel hiyerarşi, ritmik kolajda müzikteki güçlü geçiş adayları önceliklidir.

## Vuruş haritası

`python sistem/araclar/montaj_olcum.py vurus <müzik.mp3> projeler/<ad>/hazir/vuruslar.json`. Kaynaktan ölçülen saniyeleri timeline’daki ses başlangıcıyla kaydır. Vuruşlar ve BPM tahminidir. Konuşmayı veya bilinçli sessizlikleri kesme pahasına ritme kilitleme.
