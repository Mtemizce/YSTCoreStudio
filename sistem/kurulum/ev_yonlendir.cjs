// Stüdyo "tek klasör" kuralı: HyperFrames önbelleğini (Chrome, yazı tipleri, geçmiş) sabit kodlu `~/.cache/hyperframes` yerine stüdyo klasörüne yazar.
// HyperFrames ev dizinini os.homedir() ile bulur ve yolu değiştirmeye izin vermez; bu ön yükleyici (NODE_OPTIONS=--require) YALNIZCA hyperframes komutunun
// kendi sürecinde ev dizini ortam değişkenlerini stüdyo klasörüne çevirir. Başka hiçbir Node sürecine (npm, Remotion, Claude Code...) dokunmaz.
const ev = process.env.YST_NODE_EV;
const girdi = String(process.argv[1] || '').replace(/\\/g, '/');
if (ev && /\/hyperframes(\/dist\/cli\.js|\/bin\/[^/]*)?$|\/\.bin\/hyperframes(\.cmd)?$/.test(girdi)) {
  try { require('fs').mkdirSync(ev, { recursive: true }); } catch (e) { /* klasör yoksa HyperFrames kendi yolunu kullanır */ }
  process.env.HOME = ev;
  process.env.USERPROFILE = ev;
}
