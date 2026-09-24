const $=id=>document.getElementById(id);
const fragment=new URLSearchParams(location.hash.slice(1));
if(fragment.has('key')){localStorage.setItem('veil-admin',fragment.get('key'));history.replaceState(null,'',location.pathname+location.search);}
const key=localStorage.getItem('veil-admin')||'',ticket=new URLSearchParams(location.search).get('ticket');
document.querySelector('main').insertAdjacentHTML('beforeend','<section id="accepted-history" hidden><div class="section-title"><h2>Accepted presentations</h2><span id="history-count"></span></div><p id="history-empty">No presentations accepted yet.</p><div id="history-list"></div></section>');
let historyState='';
async function refreshHistory(){const d=await request('/api/accepted');$('accepted-history').hidden=false;const signature=JSON.stringify(d);if(signature===historyState)return;historyState=signature;$('history-count').textContent=d.presentations.length;$('history-empty').hidden=!!d.presentations.length;$('history-list').replaceChildren(...d.presentations.map(item=>{const entry=document.createElement('details'),summary=document.createElement('summary');const name=item.disclosed.find(a=>a.index===0);summary.textContent=(name?.text||'Presentation')+' · '+new Date(item.accepted_at*1000).toLocaleString();entry.append(summary);for(const a of item.disclosed){const row=document.createElement('div');row.className='attribute-row';const label=document.createElement('strong'),value=document.createElement('span');label.textContent=a.label||'Attribute '+a.index;value.textContent=a.text||a.value;row.append(label,value);entry.append(row);}return entry;}));}
async function request(path,method='GET'){const r=await fetch(path+'?ticket='+encodeURIComponent(ticket),{method,headers:{'X-Admin-Key':key}});const d=await r.json();if(!r.ok)throw Error(d.error);return d;}
async function refresh(){
 if(!key){$('admin-status').textContent='Administrator access required. Open the private link from the server terminal on this device.';return;}
 try{await refreshHistory();}catch(e){$('admin-status').textContent=e.message;$('accepted-history').hidden=true;return;}
 if(!ticket){$('admin-status').textContent='Administrator ready. Scan a visitor presentation QR using your phone camera and open it in this browser.';return;}
 try{const d=await request('/api/review');$('review').hidden=false;$('admin-status').textContent=d.valid?'Cryptographic proof verified by Aurora-CF.':'Invalid proof.';
 $('admin-values').replaceChildren(...d.disclosed.map(({index,value,label,text})=>{const row=document.createElement('div');row.className='attribute-row';const name=document.createElement('strong'),content=document.createElement('span');name.textContent=label||'Attribute '+index;content.textContent=text||value;row.append(name,content);return row;}));
 $('decision').textContent=d.expired?'Expired':d.decision==='pending'?'Awaiting your decision':d.decision;
 $('accept').disabled=$('reject').disabled=d.expired||d.decision!=='pending'||!d.valid;
 }catch(e){$('admin-status').textContent=e.message;$('review').hidden=true;}
}
for(const action of ['accept','reject'])$(action).onclick=async()=>{ $('accept').disabled=$('reject').disabled=true;try{await request('/api/'+action,'POST');await refresh();}catch(e){$('admin-status').textContent=e.message;}};
refresh();setInterval(refresh,3000);
