#!/usr/bin/env bash
# YSTCoreStudio başlatıcısı (Linux / macOS). Windows'ta Başlat.cmd kullanılır.
#   bash baslat.sh            paneli aç (ilk seferde kurulum sihirbazı)
#   bash baslat.sh durdur     paneli kapat
#   bash baslat.sh claude     bu klasörde claude'u ortam hazır açar
#   bash baslat.sh kontrol    sistem analizi
#   bash baslat.sh varlik     varlıkları (font vb.) yeniden indir
cd "$(dirname "$0")" || exit 1
export PYTHONUTF8=1

PY=""
for c in python3.12 python3.13 python3.11 python3.10 python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] else 1)' 2>/dev/null; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "Python 3.10+ bulunamadı."
  if [ "$(uname)" = "Darwin" ]; then echo "  Kur:  brew install python@3.12"; else echo "  Kur (Debian/Ubuntu):  sudo apt install python3 python3-venv python3-pip"; fi
  exit 1
fi
if ! "$PY" -c 'import venv, ensurepip' 2>/dev/null; then
  echo "Python'un venv modülü eksik."
  echo "  Debian/Ubuntu:  sudo apt install python3-venv python3-pip   (sonra bu betiği tekrar çalıştır)"
  exit 1
fi

if [ "$1" = "durdur" ] || [ "$1" = "claude" ] || [ "$1" = "kontrol" ] || [ "$1" = "varlik" ]; then
  exec "$PY" sistem/kurulum/baslat.py "$1"
fi
# panel arka planda kendi oturumunda çalışır; bu terminal kapansa da sürer
"$PY" sistem/kurulum/baslat.py sessiz >/dev/null 2>&1 &
disown 2>/dev/null
for i in $(seq 1 60); do
  if [ -f sistem/ortam/yerel/panel.json ]; then
    echo "Stüdyo paneli açıldı: $(sed -n 's/.*"port": *\([0-9]*\).*/http:\/\/127.0.0.1:\1/p' sistem/ortam/yerel/panel.json | head -1)"
    echo "Kapatmak için:  bash baslat.sh durdur"
    exit 0
  fi
  sleep 1
done
echo "Panel ya da kurulum sihirbazı arka planda başlıyor; tarayıcı kendiliğinden açılır (günlük: sistem/ortam/yerel/baslat.log)."
