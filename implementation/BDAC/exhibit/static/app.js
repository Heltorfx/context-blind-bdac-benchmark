const $=id=>document.getElementById(id),screenMode=location.pathname==='/screen';
$('wallet').hidden=screenMode;$('display').hidden=!screenMode;
let state={},sending=false,lastEvents='',started=0;
let celebratedTicket='';
const selected=new Set([0,1,2,3]);
let profileRendered='';
document.querySelector('.pass').insertAdjacentHTML('beforeend','<div id="acceptance-visual" hidden role="status"><div class="success-check" aria-hidden="true">✓</div><h2>Accepted.</h2><p>You’re all set.</p><span>VERIFIED AT THE DESK</span></div>');
$('consent').insertAdjacentHTML('afterbegin','<section><h3>Shared with the desk</h3><div id="preview-values"></div><details><summary>My fictional profile · 16 attributes</summary><div id="all-values"></div></details></section>');
$('feedback').insertAdjacentHTML('beforebegin','<section id="loading" hidden aria-live="polite"><div class="loading-caption"><strong id="loading-stage"></strong><span id="loading-time"></span></div><progress aria-label="Cryptographic operation in progress"></progress></section>');
document.querySelector('.pass').insertAdjacentHTML('beforeend','<div id="presentation-ticket" class="ticket-face" hidden><div class="ticket-heading"><span>VEIL / PRESENTATION</span><span>SCAN AT THE DESK</span></div><img id="ticket-qr" width="248" height="248" alt="Presentation QR code"><p id="desk-decision" role="status"></p></div>');
document.querySelector('#consent .disclosure strong').textContent='Choose four attributes';
$('consent').insertAdjacentHTML('afterbegin','<div id="attribute-picker" class="attribute-picker"></div>');
function picker(w,busy){const key=JSON.stringify(w.profile||[]);if(key!==profileRendered){profileRendered=key;$('attribute-picker').replaceChildren(...(w.profile||[]).map(a=>{const label=document.createElement('label'),input=document.createElement('input'),text=document.createElement('span');input.type='checkbox';input.value=a.index;input.checked=selected.has(a.index);text.textContent=a.label+': '+a.text;input.onchange=()=>{if(input.checked)selected.add(a.index);else selected.delete(a.index);$('agree').checked=false;render(state);};label.append(input,text);return label;}));}for(const input of $('attribute-picker').querySelectorAll('input'))input.disabled=busy||(!input.checked&&selected.size>=4);document.querySelector('#consent .disclosure span').textContent=selected.size+' / 4 selected';}
function rows(values,target){$(target).replaceChildren(...values.map(({index,label,text,value})=>{const row=document.createElement('div');row.className='attribute-row';const name=document.createElement('strong'),content=document.createElement('span');name.textContent=label||`Attribute ${index}`;content.textContent=text||value;row.append(name,content);return row;}));}
const metrics=m=>[['prove','Proof / s'],['verify','Verify / s'],['proof_kb','Proof / KB']].map(([k,l])=>`<div class="metric"><strong>${m?Number(m[k]).toFixed(2):'—'}</strong><span>${l}</span></div>`).join('');
async function post(path){const options={method:'POST'};if(path==='/api/present'){options.headers={'Content-Type':'application/json'};options.body=JSON.stringify({indexes:[...selected].sort((a,b)=>a-b)});}const r=await fetch(path,options),d=await r.json();if(!r.ok)throw Error(d.error);return d;}
function drawPass(){const c=$('art'),r=c.getBoundingClientRect(),d=Math.min(devicePixelRatio,2);c.width=r.width*d;c.height=r.height*d;const x=c.getContext('2d');x.scale(d,d);x.fillStyle='#254238';x.fillRect(0,0,r.width,r.height);}
if(!screenMode){drawPass();addEventListener('resize',drawPass);}
function render(s){state=s;$('connection').textContent=s.failed?'Setup failed':s.ready?'System online':'Preparing cryptography';const w=s.wallet;
 if(screenMode){$('public-url').textContent=s.public_url;return;}
 const has=w.credential,busy=w.busy||sending;
 $('pass-status').textContent=has?'ISSUED / CAPSS':'NOT ISSUED';$('step').textContent=has?'02 / PRESENT':'01 / ISSUE';$('action-title').textContent=w.decision==='accepted'?'You’re verified.':has?'Choose what you share.':'Make it yours.';
 $('action-description').textContent=has?'Review the four requested attributes before presenting.':'Receive a credential for a randomly generated fictional profile.';
 $('consent').hidden=!has;$('primary').textContent=busy?'Processing…':has?'Generate presentation':'Create my pass';$('primary').disabled=!s.ready||busy||(has&&!$('agree').checked);
 $('loading').hidden=!busy;if(busy){if(!started)started=Date.now();$('loading-stage').textContent=w.stage||'Sending your request';$('loading-time').textContent=Math.floor((Date.now()-started)/1000)+' s';}else started=0;
 $('feedback').textContent=w.status==='error'?'The operation failed. Please retry.':w.status==='ready'?'Your credential is ready.':'';
 picker(w,busy);if(has&&selected.size!==4)$('primary').disabled=true;
 rows(w.profile||[],'all-values');rows((w.profile||[]).filter(a=>selected.has(a.index)),'preview-values');
 document.querySelector('.pass-label').textContent=w.profile?.length?w.profile[0].text+' / Fictional visitor':'Fictional visitor';
 $('receipt').hidden=!w.metrics;if(w.metrics)$('wallet-metrics').innerHTML=metrics(w.metrics);if(w.disclosed)rows(w.disclosed,'values');
 const showTicket=!!w.ticket&&!busy;$('presentation-ticket').hidden=!showTicket;document.querySelector('.pass-content').hidden=showTicket;document.querySelector('.pass').classList.toggle('has-ticket',showTicket);
 const accepted=showTicket&&w.decision==='accepted',rejected=showTicket&&w.decision==='rejected',decided=accepted||rejected;
 const panel=$('acceptance-visual');panel.hidden=!decided;panel.classList.toggle('declined',rejected);
 document.querySelector('.pass').classList.toggle('is-accepted',accepted);document.querySelector('.pass').classList.toggle('is-rejected',rejected);
 panel.querySelector('.success-check').textContent=rejected?'×':'✓';
 panel.querySelector('h2').textContent=rejected?'Declined.':'Accepted.';
 panel.querySelector('p').textContent=rejected?'Not approved by the desk.':'You’re all set.';
 panel.querySelector(':scope > span').textContent=rejected?'ADMINISTRATOR DECISION':'VERIFIED AT THE DESK';
 if(decided&&celebratedTicket!==w.ticket){celebratedTicket=w.ticket;panel.classList.remove('celebrate');void panel.offsetWidth;panel.classList.add('celebrate');}
 if(showTicket){const url='/presentation-qr.png?ticket='+encodeURIComponent(w.ticket);if($('ticket-qr').getAttribute('src')!==url)$('ticket-qr').src=url;$('desk-decision').textContent={pending:'Ready to scan · Valid for 10 minutes',accepted:'Accepted by the administrator',rejected:'Declined by the administrator',expired:'Expired · Generate a new presentation'}[w.decision]||'';}
}
$('agree').onchange=()=>render(state);$('primary').onclick=async()=>{sending=true;started=Date.now();render(state);try{await post(state.wallet.credential?'/api/present':'/api/issue');sending=false;await poll();}catch(e){sending=false;render(state);$('feedback').textContent=e.message;}};
async function poll(){try{const r=await fetch('/api/state');if(!r.ok)throw Error();render(await r.json());}catch{$('connection').textContent='Connection interrupted';}}
(async()=>{if(!screenMode){try{await post('/api/join');}catch(e){$('feedback').textContent=e.message;}}await poll();setInterval(poll,1000);})();
