/* Panel-owned conversation, permission prompts and local runtime selection. */
window.YST = (() => {
  const el = (tag, text) => { const x = document.createElement(tag); if (text) x.textContent = text; return x; };
  async function confirmPanel(text) {
    return new Promise(resolve => {
      const d = el('dialog'), p = el('p', text), yes = el('button', 'Onayla'), no = el('button', 'Vazgeç');
      d.style.cssText = 'max-width:560px;background:#16212d;color:white;border:1px solid #576575;border-radius:12px;padding:24px;white-space:pre-wrap';
      d.append(p, yes, no); document.body.append(d);
      const done = value => { d.close(); d.remove(); resolve(value); };
      yes.onclick = () => done(true); no.onclick = () => done(false); d.oncancel = e => { e.preventDefault(); done(false); }; d.showModal();
    });
  }
  let active = '', busy = false, last = '';
  const box = el('aside'); box.id = 'orkSohbet';
  box.innerHTML = '<h3>Orkestratör</h3><div id="orkStatus" role="status"></div><div id="orkMessages" aria-live="polite"></div><div id="orkPermission"></div><textarea id="orkMessage" rows="3" placeholder="Mesaj yaz veya /görsel, /video, /müzik ile doğrudan üret…"></textarea><button id="orkSend">Gönder</button><button id="orkStop">Üretimi iptal et</button><button id="orkDraft">Taslak olarak sakla</button><button id="orkDelete">İptal et ve sil</button>';
  box.style.cssText = 'display:none;min-width:280px;width:340px;max-width:100%;padding:16px;background:var(--yuzey,#15202b);border:1px solid #44505b;border-radius:10px';
  const frame = document.getElementById('kurguFrame');
  const layout = el('div'); layout.style.cssText = 'display:flex;align-items:stretch;gap:12px;flex-wrap:wrap;flex:1;min-height:500px;overflow:auto';
  frame.parentNode.insertBefore(layout, frame); layout.append(frame, box); frame.style.cssText += ';flex:1;min-width:320px;width:60%';
  const msgs = box.querySelector('#orkMessages'); msgs.style.cssText = 'height:42vh;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere';
  const status = box.querySelector('#orkStatus'), input = box.querySelector('textarea'), permissionBox = box.querySelector('#orkPermission');
  const planBox = el('details');
  planBox.hidden = true;
  const planTitle = el('summary', 'Storyboard');
  const planText = el('pre');
  planText.style.cssText = 'white-space:pre-wrap;max-height:35vh;overflow:auto';
  const cuts = el('div');
  const approvePlan = el('button', 'Planı onayla ve üret');
  const planFeedback = el('p');
  planFeedback.setAttribute('role', 'status');
  planBox.append(planTitle, planText, cuts, approvePlan, planFeedback);
  box.prepend(planBox);
  let planRevision = '';
  async function showPlan(name, running){
    const plan = await get('/api/proje/plan?proje=' + encodeURIComponent(name));
    if (name !== active) return;
    planBox.hidden = !plan.gerekli || !plan.storyboard;
    if (planBox.hidden) return;
    const changed = planRevision !== plan.revizyon;
    planRevision = plan.revizyon;
    planTitle.textContent = plan.onayli ? 'Storyboard · Onaylı' : 'Storyboard · Onay bekliyor';
    if (!running && changed && !plan.onayli) planBox.open = true;
    planText.textContent = plan.storyboard;
    const kept = plan.kesim?.korunan || [];
    const intervals = (list) => list.map(([a, b]) => a.toFixed(2) + '–' + b.toFixed(2) + ' sn');
    cuts.replaceChildren();
    if (plan.kesim) {
      cuts.append(el('strong', 'Sessizlik kesim önerisi'));
      const keptList = el('p', 'Korunacak aralıklar: ' + intervals(kept).join(', '));
      const silenceList = el('p', 'Tespit edilen sessizlik: ' + intervals(plan.kesim.sessizlik || []).join(', '));
      cuts.append(keptList, silenceList);
    }
    approvePlan.textContent = plan.onayli ? 'Onaylı plandan devam et' :
      plan.kesim ? 'Planı ve kesimleri onayla' : 'Planı onayla ve üret';
    approvePlan.disabled = running;
    approvePlan.hidden = plan.onayli && ['taslak-hazir','onaylandi','final-render','platform-surumleri','teslim'].includes(plan.asama);
  }
  approvePlan.onclick = async () => {
    approvePlan.disabled = true;
    planFeedback.textContent = '';
    try {
      const reply = await post('/api/proje/plan-onay', {
        proje:active, revizyon:planRevision, format:PROJE.ad === active ? PROJE.fmt : 'ana',
      });
      if (!reply.ok) throw new Error(reply.mesaj || 'Üretim başlatılamadı.');
    } catch (error) {
      planFeedback.textContent = error.message;
    } finally {
      await refresh();
    }
  };
  const preferences = el('details');
  preferences.append(el('summary', 'Bu projenin medya tercihleri'));
  const choiceFields = el('div');
  choiceFields.id = 'aktifProjeMedya';
  const style = el('select');
  style.setAttribute('aria-label', 'Kurgu stili');
  const consent = el('input');
  consent.type = 'checkbox';
  const consentLabel = el('label');
  consentLabel.append(consent, document.createTextNode(' Seçili API servislerine istem gönderilmesine izin veriyorum.'));
  const result = el('p');
  result.setAttribute('role', 'status');
  const savePrefs = el('button', 'Tercihleri kaydet');
  preferences.append(choiceFields, style, consentLabel, savePrefs, result);
  box.prepend(preferences);
  const updateConsent = () => {
    const choices = Object.values(medyaDegerleri('#aktifProjeMedya'));
    consentLabel.hidden = !choices.some(value => value.startsWith('api:') &&
      !BAG.saglayicilar.find(item => item.id === value.slice(4))?.yerel);
  };
  preferences.ontoggle = async () => {
    if (!preferences.open || !active || active === '_profil') return;
    const project = active;
    savePrefs.disabled = true;
    result.textContent = '';
    try {
      await veriYukle();
      const [production, styles] = await Promise.all([
        get('/api/proje/durum?proje=' + encodeURIComponent(project)), get('/api/kurgu/stiller'),
      ]);
      if (project !== active) return;
      const u = production.uretim || {};
      medyaSecenekleri('#aktifProjeMedya', {...AYAR.uretim, ...u}, updateConsent);
      style.replaceChildren(...Object.entries(styles).map(([id, item]) => new Option(item.ad, id)));
      style.value = u.kurgu_stili || 'sade';
      consent.checked = false;
      updateConsent();
      savePrefs.disabled = false;
    } catch (error) {
      result.textContent = error.message;
    }
  };
  savePrefs.onclick = async () => {
    savePrefs.disabled = true;
    try {
      const response = await post('/api/proje/medya', {
        proje: active, medya: medyaDegerleri('#aktifProjeMedya'), kurgu_stili: style.value, bulut_izni: consent.checked,
      });
      if (!response.ok) throw new Error(response.mesaj || 'Tercihler kaydedilemedi.');
      result.textContent = 'Proje tercihleri kaydedildi.';
    } catch (error) {
      result.textContent = error.message;
    } finally {
      savePrefs.disabled = false;
    }
  };
  const notes = el('button','Bekleyen Kurgu notlarını işle'); notes.hidden=true; box.prepend(notes);
  notes.onclick=()=>post('/api/ajan/notlar',{proje:active}).then(refresh).catch(e=>status.textContent=e.message);
  const profile = el('dialog'); profile.style.cssText='background:var(--yuzey,#15202b);color:inherit;border:1px solid #44505b;border-radius:12px;max-height:95vh;overflow:auto';
  const closeProfile=el('button','Kapat'); closeProfile.onclick=()=>profile.close(); profile.append(closeProfile);document.body.append(profile);
  profile.addEventListener('close',()=>{layout.append(box);box.style.display='none';active='';});
  async function refresh() {
    if (!active || document.hidden || busy) return;
    busy = true;
    try {
      const name=active;
      const d = await get('/api/ajan/durum?proje=' + encodeURIComponent(name));
      if(name!==active)return;
      if (name !== '_profil') showPlan(name, ['calisiyor','izin'].includes(d.durum)).catch(error => {
        if (name === active && !planBox.hidden) planFeedback.textContent = error.message;
      });
      notes.hidden=!d.bekleyen_not; notes.textContent='Bekleyen Kurgu notlarını işle ('+(d.bekleyen_not||0)+')';
      status.textContent = ({calisiyor:'Çalışıyor…', izin:'Yanıtınız bekleniyor', bitti:'Yanıt tamamlandı', hata:'Hata', iptal:'Durduruldu', kesildi:'Oturum kesildi', bekliyor:'Hazır'})[d.durum] || d.durum;
      if (d.hata) status.textContent += ': ' + d.hata;
      const text = JSON.stringify(d.mesajlar);
      if (last !== text) { last = text; msgs.replaceChildren(...d.mesajlar.map(m => { const p = el('p', (m.rol === 'user' ? 'Siz: ' : m.rol === 'assistant' ? 'Orkestratör: ' : '') + m.metin); p.style.borderBottom = '1px solid #35414a'; return p; })); msgs.scrollTop = msgs.scrollHeight; }
      box.querySelector('#orkSend').disabled = ['calisiyor','izin'].includes(d.durum);
      if (permissionBox.dataset.id !== (d.izin?.id || '')) {
        permissionBox.replaceChildren(); permissionBox.dataset.id = d.izin?.id || '';
        if (d.izin) {
          const i = d.izin, fields = [];
          permissionBox.append(el('strong', i.tool === 'AskUserQuestion' ? 'Orkestratör soruyor' : 'İşlem izni: ' + i.tool));
          if (i.tool === 'AskUserQuestion') {
            for (const q of i.input.questions || []) { permissionBox.append(el('p', q.question)); const t = el('input'); t.placeholder = (q.options || []).map(o => o.label).join(' / '); fields.push([q.question,t]); permissionBox.append(t); }
          } else { const pre = el('pre', JSON.stringify(i.input, null, 2)); pre.style.cssText = 'max-height:200px;overflow:auto;white-space:pre-wrap'; permissionBox.append(pre); }
          for (const [label, yes] of [['Onayla / yanıtla',true],['Reddet',false]]) { const b = el('button',label); b.onclick = async () => { try { await post('/api/ajan/izin',{proje:active,id:i.id,onay:yes,cevaplar:Object.fromEntries(fields.map(([q,t])=>[q,t.value]))}); await refresh(); } catch(e) { status.textContent=e.message; } }; permissionBox.append(b); }
        }
      }
    } catch(e) { status.textContent = e.message; } finally { busy = false; }
  }
  function show(name) { if (!name) return; if (active !== name) { planBox.hidden = true; planBox.open = false; planRevision = ''; planFeedback.textContent = ''; preferences.open = false; last = ''; permissionBox.replaceChildren(); permissionBox.dataset.id = ''; } active = name;
    if(name==='_profil'){profile.append(box);if(!profile.open)profile.showModal();}else if(profile.open){profile.close();active=name;}
    for(const id of ['orkStop','orkDraft','orkDelete'])box.querySelector('#'+id).hidden=name==='_profil';
    preferences.hidden = name === '_profil';
    box.style.display = 'block'; refresh(); }
  box.querySelector('#orkSend').onclick = async () => { const text=input.value.trim(); if (!text) return; try { await post('/api/ajan/mesaj',{proje:active,mesaj:text,format:PROJE.ad===active ? PROJE.fmt : 'ana'}); input.value=''; refresh(); } catch(e) { status.textContent=e.message; } };
  async function lifecycle(action) {
    if (action === 'sil' && !await confirmPanel('Üretim durdurulacak ve proje listeden kaldırılacak. Arşivdeki orijinaller korunur. Devam edilsin mi?')) return;
    await post('/api/proje/'+action,{proje:active});
    if (action === 'sil') { active=''; box.style.display='none'; location.hash='#/pano'; } else refresh();
    await projeYukle(); await panoYukle();
  }
  for (const [id,action] of [['orkStop','iptal'],['orkDraft','taslak'],['orkDelete','sil']]) box.querySelector('#'+id).onclick=()=>lifecycle(action).catch(e=>status.textContent=e.message);
  setInterval(refresh,1500);
  setInterval(()=>{ const match=location.hash.match(/^#\/proje\/([^/]+)/); if(match&&!profile.open) show(decodeURIComponent(match[1])); },1500);
  // Editor requests only use this exact iframe and origin; no arbitrary API proxy.
  window.addEventListener('message', async e => {
    if (e.source !== frame.contentWindow || !frame.src || e.origin !== new URL(frame.src).origin || e.data?.yst !== 'orkestrator') return;
    show(active || location.hash.split('/')[2]);
    if (e.data.message) { try { await post('/api/ajan/mesaj',{proje:active,mesaj:e.data.message,format:PROJE.ad===active ? PROJE.fmt : 'ana'}); refresh(); } catch(err) { input.value=e.data.message; status.textContent=err.message; } }
  });
  return {confirmPanel,show};
})();

// Optional video engine has the same explicit install/status flow as the image engine.
(() => {
  const parent=document.querySelector('.ayar-panel[data-t="servis"]');
  const card=document.createElement('section');card.innerHTML='<h2>Yerel video: Wan 2.2</h2><p>alexturkey/wan22-pascal-4gb · isteğe bağlı, yaklaşık 12 GB indirme.</p><p id="wanInfo"></p><button id="wanInstall">İndir ve kur</button><progress id="wanProgress" max="100"></progress><p id="wanStatus" role="status"></p>';
  parent.prepend(card);
  let polling=false;
  async function refresh(){if(polling)return;polling=true;try{const d=await get('/api/yerelvideo');card.querySelector('#wanInfo').textContent=d.destek+' '+d.not;const b=card.querySelector('button');b.disabled=d.is.var||d.kurulu;b.textContent=d.kurulu?'Kurulu':d.is.var?'İndiriliyor…':'İndir ve kur';card.querySelector('progress').value=d.is.yuzde;card.querySelector('#wanStatus').textContent=d.is.hata||d.is.adim||(d.kurulu?'Hazır':'Kurulu değil');}catch(e){card.querySelector('#wanStatus').textContent=e.message;}finally{polling=false;}}
  card.querySelector('button').onclick=async()=>{try{await post('/api/yerelvideo/kur',{});refresh();}catch(e){card.querySelector('#wanStatus').textContent=e.message;}};
  const box=document.getElementById('orkSohbet');
  const video=document.createElement('details');video.innerHTML='<summary>Yerel video üret</summary><textarea id="wanPrompt" placeholder="Video sahnesini tarif et"></textarea><select id="wanFrames"><option value="49">2 saniye</option><option value="121">5 saniye</option><option value="17">Kısa deneme</option></select><button id="wanGenerate">Video üret</button><button id="wanCancel">Videoyu durdur</button><button id="wanAdd" hidden>Kurguya ekle</button><p id="wanResult"></p>';
  box.append(video);
  video.querySelector('#wanAdd').onclick=()=>{const frame=document.getElementById('kurguFrame');if(frame.src.startsWith('http://127.0.0.1:'))frame.contentWindow.postMessage({yst:'video-ekle',path:video.dataset.output},new URL(frame.src).origin);else video.querySelector('#wanResult').textContent='Önce Kurgu editörünü açın.';};
  video.querySelector('#wanGenerate').onclick=async()=>{try{const p=location.hash.split('/')[2];await post('/api/yerelvideo/uret',{proje:p,istem:video.querySelector('textarea').value,kare:Number(video.querySelector('select').value)});video.querySelector('#wanResult').textContent='Üretim başladı…';}catch(e){video.querySelector('#wanResult').textContent=e.message;}};
  video.querySelector('#wanCancel').onclick=()=>post('/api/yerelvideo/iptal',{proje:location.hash.split('/')[2]}).catch(e=>video.querySelector('#wanResult').textContent=e.message);
  setInterval(async()=>{if(document.hidden)return;if(location.hash.includes('/ayar/servis'))refresh();if(video.open){try{const d=(await get('/api/yerelvideo')).uretim;video.querySelector('#wanAdd').hidden=d.proje!==location.hash.split('/')[2]||!d.dosya||d.var;video.dataset.output=d.dosya||'';if(d.proje===location.hash.split('/')[2])video.querySelector('#wanResult').textContent=d.var?'Üretiliyor…':d.iptal?'İptal edildi':d.hata|| (d.dosya?'Hazır: '+d.dosya+' — proje kaynaklarına eklendi.':'');}catch(e){video.querySelector('#wanResult').textContent=e.message;}}},2000);
})();


// Optional installs live in a single, non-modal drawer.
(() => {
  const make = (tag, text) => {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    return node;
  };
  const dock = make('div');
  dock.style.cssText = 'position:fixed;right:0;top:26%;display:flex;flex-direction:row-reverse;align-items:flex-start;z-index:35;max-width:100vw';
  const toggle = make('button', '‹ İsteğe bağlı kurulumlar');
  toggle.type = 'button';
  toggle.setAttribute('aria-expanded', 'false');
  toggle.setAttribute('aria-controls', 'optionalInstalls');
  const drawer = make('aside');
  drawer.id = 'optionalInstalls';
  drawer.setAttribute('aria-label', 'İsteğe bağlı kurulumlar');
  drawer.style.cssText = 'width:min(24rem,58vw);max-height:68vh;overflow:auto;padding:1rem;background:var(--yuzey,#19232f);border:1px solid #64748b;border-radius:0 0 0 12px;box-shadow:0 8px 18px #0005';
  drawer.hidden = true;
  const title = make('h3', 'İsteğe bağlı kurulumlar');
  const list = make('div');
  const message = make('p');
  message.setAttribute('role', 'status');
  drawer.append(title, list, message);
  dock.append(toggle, drawer);
  document.body.append(dock);
  const component = (name, desc, id, secenek) => ({
    name, desc, status:'/api/bilesen', install:'/api/bilesen/kur', body:{id, secenek},
    map:d => ({kurulu:!!d.bilesenler?.[id]?.secenekler?.[secenek]?.kurulu,
      is:d.is?.bilesen === id ? d.is : {var:false}}),
  });
  const items = [
    component('Pocket TTS Turkish', 'Projede kendi sesine benzer Türkçe seslendirme üretir.', 'klon', 'pocket-tr'),
    component('rclone', 'Bulut disk arşivlerini bağlamak için kullanılır.', 'rclone', 'rclone'),
    ...[
      ['tiny', 'En küçük konuşma çözümleme modeli.'],
      ['base', 'Düşük kaynak kullanımıyla dikte ve altyazı çıkarır.'],
      ['medium', 'Daha yüksek bellek kullanımıyla konuşma çözümleme.'],
      ['large-v3-turbo', 'Büyük Whisper modelinin daha hızlı sürümü.'],
      ['large-v3', 'Büyük konuşma çözümleme modeli.'],
    ].map(([id, desc]) => component('Whisper ' + id, desc, 'whisper', id)),
    {name:'Z-Image-Turbo', desc:'Yerelde metinden görsel üretir.', status:'/api/yerelgorsel', install:'/api/yerelgorsel/kur'},
    {name:'Wan 2.2', desc:'Metinden kısa video üretir. Windows ve uyumlu NVIDIA ekran kartı gerekir.', status:'/api/yerelvideo', install:'/api/yerelvideo/kur'},
    {name:'ACE-Step 1.5', desc:'Yerelde sözsüz fon müziği üretir.', status:'/api/yerelmuzik', install:'/api/yerelmuzik/kur'},
    {name:'Müzik ve ses efektleri', desc:'Hazır fon müziği ve efekt arşivini indirir.', status:'/api/arka-indirme', install:'/api/arka-indirme/ses',
      map:d => ({kurulu:!!d.ses && !d.ses.eksik, is:{var:d.ses?.iniyor, hata:d.ses?.sorun}})},
    {name:'NVIDIA hızlandırma', desc:'Uygun NVIDIA ekran kartlarında bazı yerel işlemleri hızlandırır.', status:'/api/arka-indirme', install:'/api/bilesen/kur', body:{id:'gpu', secenek:'cuda'},
      map:d => ({kurulu:!d.gpu?.oner, is:{var:false}})},
  ];
  let polling = false;
  let lastCount = '';
  const pending = new Set();
  const status = new Map();
  for (const item of items) {
    const row = make('div');
    row.className = 'kit';
    const feedback = make('div');
    feedback.className = 'meta';
    const button = make('button', 'Kur');
    button.type = 'button';
    button.onclick = async () => {
      pending.add(item);
      button.disabled = true;
      message.textContent = '';
      try {
        const result = await post(item.install, item.body || {});
        if (result.ok === false) throw new Error(result.mesaj || result.hata || 'Kurulum başlatılamadı.');
      } catch (error) {
        message.textContent = item.name + ' · ' + error.message;
      } finally {
        pending.delete(item);
        await refresh();
      }
    };
    const description = make('p', item.desc);
    description.className = 'meta';
    row.append(make('strong', item.name), description, button, feedback);
    row.hidden = true;
    item.render = d => {
      row.hidden = d.kurulu;
      button.disabled = pending.has(item) || !!d.is?.var;
      button.textContent = button.disabled ? 'Kuruluyor…' : 'Kur';
      feedback.textContent = d.is?.hata || (d.is?.var ? d.is.adim || 'Kurulum sürüyor…' : '');
    };
    list.append(row);
  }
  async function refresh() {
    if (polling || document.hidden) return;
    polling = true;
    try {
      const routes = [...new Set(items.map(item => item.status))];
      await Promise.allSettled(routes.map(async route => {
        const data = await get(route);
        for (const item of items.filter(item => item.status === route)) {
          const d = item.map ? item.map(data) : data;
          status.set(item, d);
          item.render(d);
        }
      }));
      const missing = [...status.values()].filter(d => !d.kurulu).length;
      if (status.size) lastCount = ' (' + missing + ')';
      toggle.textContent = (drawer.hidden ? '‹ ' : '› ') + 'İsteğe bağlı kurulumlar' + lastCount;
      if (status.size === items.length && !missing) message.textContent = 'Tüm isteğe bağlı bileşenler hazır.';
    } finally {
      polling = false;
    }
  }
  toggle.onclick = () => {
    drawer.hidden = !drawer.hidden;
    toggle.setAttribute('aria-expanded', String(!drawer.hidden));
    toggle.textContent = (drawer.hidden ? '‹ ' : '› ') + 'İsteğe bağlı kurulumlar' + lastCount;
    refresh();
  };
  dock.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !drawer.hidden) {
      toggle.click();
      toggle.focus();
    }
  });
  refresh();
  setInterval(refresh, 5000);
})();
