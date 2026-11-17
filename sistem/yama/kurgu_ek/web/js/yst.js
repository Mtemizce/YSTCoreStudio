// yst.js — YSTCore eklentisi: Kurgu'nun içinde görsel (yerel Z-Image kütüphanesi), seslendirme ve kalemle ara sahne.
// Sunucu tarafı: yst_ek.py (/api/yst/*). Üretilen dosyalar projenin media/ klasörüne yazılır ve Kurgu'nun kendi addMedia işleviyle zaman çizelgesine konur.
import { S } from './state.js';
import { addMedia } from './import.js';
import { getLang, setLang } from './i18n.js';

const TXT = {
  tr: {
    gorsel: 'Görsel', ses: 'Ses', kalem: 'Ara sahne', gorselTip: 'Kütüphaneden görsel ekle ya da yerel modelle yeni görsel üret', sesTip: 'Metni yerel motorla seslendir ve zaman çizelgesine ekle',
    kalemTip: 'Bir kareyi, resmi ya da videoyu kalemle çizilen ara sahneye çevir', kapat: 'Kapat', kutuphane: 'Kütüphane', yeni: 'Yeni üret', ekle: 'Zaman çizelgesine ekle', eklendi: 'Zaman çizelgesine eklendi',
    bos: 'Kütüphane boş: "Yeni üret" sekmesinden üret ve beğendiğini ekle.', kurulu_degil: 'Yerel görsel üretim (Z-Image-Turbo) kurulu değil.', kur: 'Kurmak için panele git',
    istem: 'İstem', stil: 'Stil', stilYok: 'Stil yok', boyut: 'Boyut', adet: 'Kaç tane', uret: 'Üret', beg: 'Beğendim, ekle', yeniden: 'Yeniden üret', reddet: 'Reddet', calisiyor: 'üretiliyor…',
    metin: 'Seslendirilecek metin', metinSec: 'Seçili metin katmanının metnini al', motor: 'Motor', hiz: 'Hız', sesSec: 'Ses', duygu: 'Duygu', klon: 'Klonlanmış sesimi kullan', seslendir: 'Seslendir', tekrar: 'Başka alım',
    sesHazir: 'Hazır', kaynak: 'Kaynak', kare: 'Oynatma başlığındaki kare', zemin: 'Zemin rengi', gecis: 'Çizim bitince gerçek görüntüye dönüşsün', bekle: 'Dönüşüme kadar bekleme (sn)', sure: 'Çizim süresi (sn)',
    kalemSesi: 'Kalem çizim sesi ekle', ciz: 'Çiz', cizimHazir: 'Ara sahne hazır', hata: 'Hata', atif: 'Pocket TTS Turkish CC-BY-4.0: atıf proje klasöründeki ATIF.txt dosyasına yazıldı.',
    z_stil: 'Stilin kendi rengi', z_acik: 'Aydınlık', z_yesil: 'Yeşilimsi (çimen)', z_sicak: 'Sıcak kâğıt', z_koyu: 'Karanlık', kalite: 'kalite',
  },
  en: {
    gorsel: 'Image', ses: 'Voice', kalem: 'Pencil scene', gorselTip: 'Add an image from the library or generate one with the local model', sesTip: 'Speak a text with the local engine and add it to the timeline',
    kalemTip: 'Turn a frame, image or video into a pencil-drawn scene', kapat: 'Close', kutuphane: 'Library', yeni: 'Generate', ekle: 'Add to timeline', eklendi: 'Added to the timeline',
    bos: 'The library is empty: generate in the "Generate" tab and add what you like.', kurulu_degil: 'Local image generation (Z-Image-Turbo) is not installed.', kur: 'Go to the panel to install',
    istem: 'Prompt', stil: 'Style', stilYok: 'No style', boyut: 'Size', adet: 'How many', uret: 'Generate', beg: 'Like it, add', yeniden: 'Regenerate', reddet: 'Reject', calisiyor: 'generating…',
    metin: 'Text to speak', metinSec: 'Take the selected text layer\'s text', motor: 'Engine', hiz: 'Speed', sesSec: 'Voice', duygu: 'Emotion', klon: 'Use my cloned voice', seslendir: 'Speak', tekrar: 'Another take',
    sesHazir: 'Ready', kaynak: 'Source', kare: 'Frame at the playhead', zemin: 'Paper colour', gecis: 'Turn into the real picture when the drawing ends', bekle: 'Wait before the transition (s)', sure: 'Drawing time (s)',
    kalemSesi: 'Add pencil drawing sound', ciz: 'Draw', cizimHazir: 'Scene ready', hata: 'Error', atif: 'Pocket TTS Turkish CC-BY-4.0: attribution written to ATIF.txt in the project folder.',
    z_stil: 'Style default', z_acik: 'Light', z_yesil: 'Greenish (grass)', z_sicak: 'Warm paper', z_koyu: 'Dark', kalite: 'quality',
  },
};
const L = k => (TXT[getLang()] || TXT.tr)[k] || TXT.tr[k] || k;
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const $ = id => document.getElementById(id);
const bk = ms => new Promise(r => setTimeout(r, ms));
const GOMULU = window.parent !== window;
let DURUM = null;

function toast(text, kind = 'info', ms = 3500) {
  const host = $('toasts'); if (!host) return;
  const b = document.createElement('div'); b.className = 'toast ' + kind; const s = document.createElement('span'); s.className = 'toast-text'; s.textContent = text; b.append(s); host.append(b);
  while (host.children.length > 3) host.firstChild.remove();
  setTimeout(() => { b.classList.add('leave'); setTimeout(() => b.remove(), 300); }, ms);
}
async function api(yol, govde) {
  const r = await fetch(yol, govde === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(govde) });
  let d = null; try { d = await r.json(); } catch (e) { /* boş gövde */ }
  if (!r.ok) throw new Error((d && d.error) || ('HTTP ' + r.status));
  return d;
}
async function durum(yenile) { if (!DURUM || yenile) DURUM = await api('/api/yst/durum'); return DURUM; }

// ------------------------------------------------------------------ pencere
let AKTIF = null;
function pencere(baslik, govde) {
  kapat();
  const ov = document.createElement('div'); ov.className = 'yst-ov';
  ov.innerHTML = `<div class="yst-kutu" role="dialog" aria-modal="true"><div class="yst-bas"><b>${esc(baslik)}</b><button type="button" class="ib yst-x" aria-label="${esc(L('kapat'))}">✕</button></div><div class="yst-govde"></div></div>`;
  ov.querySelector('.yst-govde').append(govde);
  ov.addEventListener('mousedown', e => { if (e.target === ov) kapat(); });
  ov.querySelector('.yst-x').onclick = kapat;
  document.body.append(ov); AKTIF = ov; return ov;
}
function kapat() { if (AKTIF) { AKTIF.remove(); AKTIF = null; } }
document.addEventListener('keydown', e => { if (e.key === 'Escape' && AKTIF) { e.stopPropagation(); kapat(); } }, true);
function sekmeler(liste) {   // [[ad, el, açılınca-çağrılacak]]
  const kok = document.createElement('div'); const sat = document.createElement('div'); sat.className = 'yst-sek'; kok.append(sat);
  liste.forEach(([ad, e, ac], i) => {
    const b = document.createElement('button'); b.type = 'button'; b.textContent = ad; sat.append(b); e.hidden = i !== 0; kok.append(e); if (i === 0) b.classList.add('on');
    b.onclick = () => { [...sat.children].forEach(x => x.classList.toggle('on', x === b)); liste.forEach(([, y]) => { y.hidden = y !== e; }); if (ac) ac(); };
  });
  return kok;
}
function html(s) { const d = document.createElement('div'); d.innerHTML = s; return d; }
function karto(img, alt, yol) { return `<div class="yst-kart">${img}<div class="yst-kmeta">${alt}</div><div class="yst-kyol">${yol}</div></div>`; }

// ------------------------------------------------------------------ iş izleme
async function isIzle(id, ilerle) {
  for (;;) {
    await bk(1500);
    const i = await api('/api/yst/is?id=' + id);
    if (ilerle) ilerle(i.mesaj);
    if (i.durum === 'bitti') return i.sonuc;
    if (i.durum === 'hata') throw new Error(i.hata || 'hata');
  }
}

// ------------------------------------------------------------------ görsel
async function gorselAc() {
  const d = await durum(true);
  const kut = html('<div class="yst-izgara"></div>'), yeni = html('');
  const dosya = id => `/api/yst/gorsel/dosya?id=${id}&k=1`;
  const ekleBagla = async (id, k) => {
    const r = await api('/api/yst/gorsel/ekle', { id });
    await addMedia('image', r.path, { quiet: true }); toast(L('eklendi'), 'ok'); if (k) k.innerHTML = `<span class="ok">✓ ${esc(L('eklendi'))}</span>`;
  };
  async function kutCiz() {
    const r = await api('/api/yst/gorsel/liste?durum=onayli'); const host = kut.firstChild;
    host.innerHTML = r.ogeler.map(o => karto(`<img loading="lazy" alt="" src="${dosya(o.id)}">`, `${esc(o.stil || '')} ${o.genislik}×${o.yukseklik}<br><span title="${esc(o.istem)}">${esc(o.istem.slice(0, 60))}</span>`,
      `<button type="button" class="tb" data-id="${o.id}" data-e="ekle">${esc(L('ekle'))}</button>`)).join('') || `<div class="yst-bilgi">${esc(L('bos'))}</div>`;
    host.onclick = async e => { const b = e.target.closest('[data-e=ekle]'); if (!b) return; try { await ekleBagla(b.dataset.id, b.parentElement); } catch (er) { toast(er.message, 'error'); } };
  }
  if (!d.gorsel.kurulu) {
    yeni.innerHTML = `<div class="yst-bilgi">${esc(L('kurulu_degil'))}</div><div class="yst-satir"><button type="button" class="btn primary" id="yst-kur">${esc(L('kur'))}</button></div>`;
    yeni.querySelector('#yst-kur').onclick = () => { kapat(); if (GOMULU) window.parent.postMessage({ yst: 'ayar-servis' }, '*'); };
  } else {
    let stil = '';
    yeni.innerHTML = `<label>${esc(L('istem'))}</label><textarea id="yst-g-istem" rows="3"></textarea><label>${esc(L('stil'))}</label><div class="yst-stiller" id="yst-g-stil"></div>
      <div class="yst-satir"><label>${esc(L('boyut'))}<select id="yst-g-boyut"><option value="yatay">16:9</option><option value="dikey">9:16</option><option value="kare">1:1</option><option value="genis">21:9</option></select></label>
      <label>${esc(L('adet'))}<select id="yst-g-adet"><option>1</option><option selected>2</option><option>3</option><option>4</option></select></label>
      <button type="button" class="btn primary" id="yst-g-uret">${esc(L('uret'))}</button><span class="yst-durum" id="yst-g-durum"></span></div><div class="yst-izgara" id="yst-g-sonuc"></div>`;
    const stilHost = yeni.querySelector('#yst-g-stil');
    stilHost.innerHTML = `<button type="button" class="yst-chip on" data-s="">${esc(L('stilYok'))}</button>` + d.gorsel.stiller.map(s => `<button type="button" class="yst-chip" data-s="${s.id}" title="${esc(s.aciklama)}"><i style="background:linear-gradient(135deg,${s.renk[0]},${s.renk[1]})"></i>${esc(s.ad)}</button>`).join('');
    stilHost.onclick = e => { const b = e.target.closest('.yst-chip'); if (!b) return; stil = b.dataset.s; stilHost.querySelectorAll('.yst-chip').forEach(x => x.classList.toggle('on', x === b)); };
    const sonuc = yeni.querySelector('#yst-g-sonuc'), dur = yeni.querySelector('#yst-g-durum'); let idler = [];
    async function taslakCiz() {
      const r = await api('/api/yst/gorsel/liste?durum=taslak');
      sonuc.innerHTML = r.ogeler.filter(o => idler.includes(o.id)).map(o => karto(`<img alt="" src="${dosya(o.id)}">`, `${esc(L('kalite'))}: <b class="${o.kalite.durum}">${esc(o.kalite.durum)}</b> ${esc((o.kalite.ipucu || []).join('; '))}`,
        `<button type="button" class="tb" data-e="beg" data-id="${o.id}">${esc(L('beg'))}</button><button type="button" class="tb" data-e="yeniden" data-id="${o.id}">${esc(L('yeniden'))}</button><button type="button" class="tb" data-e="reddet" data-id="${o.id}">${esc(L('reddet'))}</button>`)).join('');
    }
    async function izle() {
      for (;;) {
        const i = await api('/api/yst/gorsel/is'); idler = [...new Set([...idler, ...(i.idler || [])])]; dur.textContent = i.calisiyor ? `${L('calisiyor')} (${i.tamam}/${i.toplam})` : (i.hata || '');
        await taslakCiz(); if (!i.calisiyor) return; await bk(2000);
      }
    }
    yeni.querySelector('#yst-g-uret').onclick = async () => {
      try { idler = []; await api('/api/yst/gorsel/uret', { istem: yeni.querySelector('#yst-g-istem').value, stil, boyut: yeni.querySelector('#yst-g-boyut').value, adet: Number(yeni.querySelector('#yst-g-adet').value) }); dur.textContent = L('calisiyor'); await bk(500); izle(); }
      catch (er) { dur.textContent = er.message; }
    };
    sonuc.onclick = async e => {
      const b = e.target.closest('[data-e]'); if (!b) return; const id = b.dataset.id, a = b.dataset.e;
      try {
        if (a === 'beg') { await api('/api/yst/gorsel/onayla', { id }); await ekleBagla(id, b.parentElement); kutCiz(); }
        else if (a === 'reddet') { await api('/api/yst/gorsel/reddet', { id }); idler = idler.filter(x => x !== id); taslakCiz(); }
        else if (a === 'yeniden') { await api('/api/yst/gorsel/yeniden', { id }); idler = idler.filter(x => x !== id); await bk(400); izle(); }
      } catch (er) { toast(er.message, 'error'); }
    };
  }
  pencere(L('gorsel'), sekmeler([[L('kutuphane'), kut, null], [L('yeni'), yeni, null]]));
  kutCiz().catch(er => toast(er.message, 'error'));
}

// ------------------------------------------------------------------ ses
const DUYGULAR = ['mutlu', 'üzgün', 'kızgın', 'şaşkın', 'sakin'];
async function sesAc() {
  const d = await durum(true);
  const motorlar = d.ses.motorlar.filter(m => m.hazir);
  const govde = html('');
  if (!motorlar.length) { govde.innerHTML = `<div class="yst-bilgi">${esc((d.ses.motorlar[0] && d.ses.motorlar[0].neden) || 'seslendirme motoru kurulu değil')}</div>`; pencere(L('ses'), govde); return; }
  const secili = S.selection.map(id => S.project.layers.find(l => l.id === id)).filter(l => l && l.type === 'text');
  govde.innerHTML = `<label>${esc(L('metin'))}</label><textarea id="yst-s-metin" rows="5">${esc(secili[0] ? secili[0].text : '')}</textarea>
    <div class="yst-satir">${secili.length ? '' : ''}<label>${esc(L('motor'))}<select id="yst-s-motor">${motorlar.map(m => `<option value="${m.id}">${esc(m.id)}</option>`).join('')}</select></label>
    <label>${esc(L('hiz'))}<input type="range" id="yst-s-hiz" min="0.7" max="1.4" step="0.05" value="1"><b id="yst-s-hizv">1.0</b></label></div>
    <div class="yst-satir" id="yst-s-pocket" hidden><label>${esc(L('sesSec'))}<select id="yst-s-ses"></select></label><label>${esc(L('duygu'))}<select id="yst-s-duygu"><option value="">-</option>${DUYGULAR.map(x => `<option>${x}</option>`).join('')}</select></label>
      <label class="yst-onay" id="yst-s-klonk"><input type="checkbox" id="yst-s-klon"> ${esc(L('klon'))}</label></div>
    <div class="yst-satir"><button type="button" class="btn primary" id="yst-s-uret">${esc(L('seslendir'))}</button><span class="yst-durum" id="yst-s-durum"></span></div><div id="yst-s-sonuc"></div>`;
  const motorSec = govde.querySelector('#yst-s-motor'), hiz = govde.querySelector('#yst-s-hiz');
  const motorDegisti = () => {
    const m = motorlar.find(x => x.id === motorSec.value); const pk = govde.querySelector('#yst-s-pocket');
    pk.hidden = !(m.desteklenen.ses || m.desteklenen.duygu || m.desteklenen.klon);
    govde.querySelector('#yst-s-ses').innerHTML = (m.sesler || []).map(x => `<option>${esc(x)}</option>`).join(''); govde.querySelector('#yst-s-ses').parentElement.hidden = !m.desteklenen.ses;
    govde.querySelector('#yst-s-duygu').parentElement.hidden = !m.desteklenen.duygu; govde.querySelector('#yst-s-klonk').hidden = !(m.desteklenen.klon && d.ses.klon_ornegi);
  };
  motorSec.onchange = motorDegisti; motorDegisti();
  hiz.oninput = () => { govde.querySelector('#yst-s-hizv').textContent = Number(hiz.value).toFixed(2); };
  let tohum = null;
  const uret = async () => {
    const dur = govde.querySelector('#yst-s-durum'), sonuc = govde.querySelector('#yst-s-sonuc'); sonuc.innerHTML = '';
    try {
      const m = motorlar.find(x => x.id === motorSec.value);
      const r = await api('/api/yst/ses/uret', { metin: govde.querySelector('#yst-s-metin').value, motor: motorSec.value, hiz: Number(hiz.value), ses: m.desteklenen.ses ? govde.querySelector('#yst-s-ses').value : null,
        duygu: govde.querySelector('#yst-s-duygu').value || null, klon: !!(m.desteklenen.klon && govde.querySelector('#yst-s-klon').checked), tohum });
      const s = await isIzle(r.id, mesaj => { dur.textContent = mesaj; }); dur.textContent = `${L('sesHazir')} (${s.sure} sn)`;
      sonuc.innerHTML = `<audio controls src="/media?path=${encodeURIComponent(s.path)}"></audio><div class="yst-satir"><button type="button" class="btn primary" id="yst-s-ekle">${esc(L('ekle'))}</button><button type="button" class="tb" id="yst-s-tekrar">${esc(L('tekrar'))}</button></div>${m.atif_gerekir || m.id.startsWith('pocket') ? `<div class="yst-bilgi">${esc(L('atif'))}</div>` : ''}`;
      sonuc.querySelector('#yst-s-ekle').onclick = async () => { try { await addMedia('audio', s.path, { quiet: true, time: S.t }); toast(L('eklendi'), 'ok'); kapat(); } catch (er) { toast(er.message, 'error'); } };
      sonuc.querySelector('#yst-s-tekrar').onclick = () => { tohum = Math.floor(Math.random() * 1e6); uret(); };
    } catch (er) { dur.textContent = er.message; }
  };
  govde.querySelector('#yst-s-uret').onclick = () => { tohum = null; uret(); };
  pencere(L('ses'), govde);
}

// ------------------------------------------------------------------ ara sahne
const ZEMIN = [['', 'z_stil'], ['#F4F1EA', 'z_acik'], ['#DCE8D2', 'z_yesil'], ['#EFE2C6', 'z_sicak'], ['#1E2430', 'z_koyu']];
async function kalemAc() {
  const d = await durum(true);
  const govde = html('');
  if (!d.kalem.hazir) { govde.innerHTML = `<div class="yst-bilgi">ffmpeg ${esc(L('hata'))}</div>`; pencere(L('kalem'), govde); return; }
  let dosyalar = []; try { dosyalar = (await api('/api/files')).filter(f => f.kind === 'image' || f.kind === 'video'); } catch (e) { /* liste olmadan da çalışır */ }
  const zt = (S.t || 0).toFixed(2);
  govde.innerHTML = `<div class="yst-satir"><label>${esc(L('kaynak'))}<select id="yst-k-kaynak"><option value="@kare">${esc(L('kare'))} (${zt} sn)</option>${dosyalar.map(f => `<option value="${esc(f.path)}" data-k="${f.kind}">${esc(f.path)}</option>`).join('')}</select></label>
    <label>${esc(L('stil'))}<select id="yst-k-stil">${d.kalem.stiller.map(s => `<option value="${s.id}" ${s.id === 'karakalem' ? 'selected' : ''}>${esc(s.ad)}</option>`).join('')}</select></label>
    <label>${esc(L('zemin'))}<select id="yst-k-zemin">${ZEMIN.map(([v, k]) => `<option value="${v}">${esc(L(k))}</option>`).join('')}</select></label></div>
    <div class="yst-satir"><label class="yst-onay"><input type="checkbox" id="yst-k-gecis" checked> ${esc(L('gecis'))}</label><label class="yst-onay"><input type="checkbox" id="yst-k-ses" checked> ${esc(L('kalemSesi'))}</label></div>
    <div class="yst-satir"><label>${esc(L('sure'))}<input type="number" id="yst-k-sure" value="8" min="4" max="30" style="width:70px"></label><label>${esc(L('bekle'))}<input type="number" id="yst-k-bekle" value="2" min="0.5" max="10" step="0.5" style="width:70px"></label>
    <button type="button" class="btn primary" id="yst-k-ciz">${esc(L('ciz'))}</button><span class="yst-durum" id="yst-k-durum"></span></div><div id="yst-k-sonuc"></div>`;
  govde.querySelector('#yst-k-ciz').onclick = async () => {
    const dur = govde.querySelector('#yst-k-durum'), sonuc = govde.querySelector('#yst-k-sonuc'); sonuc.innerHTML = '';
    try {
      const sec = govde.querySelector('#yst-k-kaynak'), kare = sec.value === '@kare';
      const r = await api('/api/yst/kalem/uret', { kaynak: kare ? { kare: S.t } : sec.value, stil: govde.querySelector('#yst-k-stil').value, zemin: govde.querySelector('#yst-k-zemin').value,
        gecis: govde.querySelector('#yst-k-gecis').checked, bekle: Number(govde.querySelector('#yst-k-bekle').value), sure: Number(govde.querySelector('#yst-k-sure').value), kalem_sesi: govde.querySelector('#yst-k-ses').checked });
      const s = await isIzle(r.id, mesaj => { dur.textContent = mesaj; }); dur.textContent = L('cizimHazir');
      sonuc.innerHTML = `<video controls src="/media?path=${encodeURIComponent(s.path)}" style="max-width:100%;max-height:300px"></video><div class="yst-satir"><button type="button" class="btn primary" id="yst-k-ekle">${esc(L('ekle'))}</button></div>`;
      sonuc.querySelector('#yst-k-ekle').onclick = async () => { try { await addMedia('video', s.path, { quiet: true, time: S.t }); toast(L('eklendi'), 'ok'); kapat(); } catch (er) { toast(er.message, 'error'); } };
    } catch (er) { dur.textContent = er.message; }
  };
  pencere(L('kalem'), govde);
}

// ------------------------------------------------------------------ üst çubuk
function kur() {
  const hedef = $('b-theme'); if (!hedef || $('yst-grup')) return;
  const g = document.createElement('div'); g.className = 'seg'; g.id = 'yst-grup'; g.setAttribute('role', 'group'); g.dataset.edit = '';
  g.innerHTML = `<button type="button" class="tb" id="yst-b-gorsel" title="${esc(L('gorselTip'))}"><span>${esc(L('gorsel'))}</span></button><button type="button" class="tb" id="yst-b-ses" title="${esc(L('sesTip'))}"><span>${esc(L('ses'))}</span></button><button type="button" class="tb" id="yst-b-kalem" title="${esc(L('kalemTip'))}"><span>${esc(L('kalem'))}</span></button>`;
  hedef.before(g);
  const sar = fn => () => fn().catch(er => toast(er.message || String(er), 'error'));
  $('yst-b-gorsel').onclick = sar(gorselAc); $('yst-b-ses').onclick = sar(sesAc); $('yst-b-kalem').onclick = sar(kalemAc);
  const etiketle = () => { $('yst-b-gorsel').firstChild.textContent = L('gorsel'); $('yst-b-ses').firstChild.textContent = L('ses'); $('yst-b-kalem').firstChild.textContent = L('kalem'); };
  new MutationObserver(etiketle).observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] });
  if (GOMULU) {
    document.documentElement.classList.add('yst-gomulu');
    try { if (!localStorage.getItem('kurgu.lang')) setLang('tr'); } catch (e) { /* depolama yok */ }
  }
}
let deneme = 0;
const bekleyici = setInterval(() => {
  if ($('b-theme') && S.project) {
    clearInterval(bekleyici);
    try { kur(); if (GOMULU) window.parent.postMessage({ yst: 'hazir' }, '*'); } catch (e) { console.error('YSTCore eklentisi başlatılamadı', e); }   // eklenti hatası Kurgu'yu etkilemez
  } else if (++deneme > 200) clearInterval(bekleyici);   // ~60 sn sonra vazgeç: Kurgu'nun arayüzü değişmişse sessizce pasif kal
}, 300);
