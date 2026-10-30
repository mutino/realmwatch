'use strict';
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const dateFmt = new Intl.DateTimeFormat('en-GB', {day:'2-digit',month:'short',year:'numeric',timeZone:'Europe/London'});
const timeFmt = new Intl.DateTimeFormat('en-GB', {hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false,timeZone:'Europe/London'});
let state = null, selected = '', loading = false;
const serverName = id => state.servers.find(s => s.id === id)?.name || id;
const initials = name => name.split(/\s+/).slice(0,2).map(p=>p[0]).join('').toUpperCase();
const shortDate = time => time ? dateFmt.format(new Date(time)) : 'Not recorded';
const shortTime = time => time ? timeFmt.format(new Date(time)) : '';
function timeCell(at, approximate=false) {
  return at ? `<span title="${approximate ? 'Detected offline or server restarted; the exact logout was not logged. ' : ''}${esc(at)}">${approximate?'≈ ':''}${shortDate(at)}<small>${shortTime(at)}</small></span>` : '<span class="muted">Not recorded</span>';
}
function matchingServer(id) { return !selected || id === selected; }
function isToday(at) { return dateFmt.format(new Date(at)) === dateFmt.format(new Date()); }
function showNotice(message) { $('notice').textContent = message; $('notice').hidden = !message; }

function render() {
  const data = state;
  const stale = data.stale || Date.now()-Date.parse(data.updated_at)>60000;
  const totalOnline = data.servers.reduce((sum,s)=>sum+(s.player_count||0),0);
  const unknown = data.servers.some(s=>s.player_count===null);
  $('liveBadge').classList.toggle('stale',stale);
  $('liveBadge').innerHTML = `<i></i> ${stale?'DATA DELAYED':'LIVE · 15 SEC'}`;
  if(stale) showNotice('The collector has stopped updating. Values below are the last known state, not live status.');
  else showNotice('');
  $('metricServers').textContent = data.servers.filter(s=>s.status==='online').length;
  $('metricServersTotal').textContent = `/ ${data.servers.length}`;
  $('metricOnline').textContent = totalOnline + (unknown?'+':'');
  $('metricPlayers').textContent = new Set(data.players.map(p=>p.name)).size;
  $('metricJoins').textContent = data.joins_today;
  $('realmCount').textContent = data.servers.length;
  $('realms').innerHTML = data.servers.map((s,i)=>`<button class="realm-card ${selected===s.id?'selected':''}" data-server="${esc(s.id)}" aria-pressed="${selected===s.id}">
    <svg class="mountains" viewBox="0 0 200 140" aria-hidden="true"><path d="m0 140 60-95 26 39 36-72 78 128ZM14 140l48-66 45 66Z"/></svg>
    <div class="card-top"><span class="status ${esc(s.status)}"><i class="status-dot"></i>${stale?'LAST KNOWN':s.status==='online'?'ONLINE':s.status==='offline'?'OFFLINE':'QUERY UNAVAILABLE'}</span><span class="rune" aria-hidden="true">${['ᛟ','ᚾ','ᛗ','ᛉ','ᚦ'][i%5]}</span></div>
    <h3>${esc(s.name)}</h3><span class="world">World · ${esc(s.world)}</span>
    <div class="card-bottom"><span class="card-population"><strong>${s.player_count??'—'}</strong>${s.player_count===1?'Viking':'Vikings'} online</span><span class="card-names" title="${esc(s.query_error||s.players.join(', '))}">${s.query_error?'Status unavailable':s.players.length?esc(s.players.join(', ')):s.player_count?'Names not yet recorded':'Quiet, for now'}</span></div>
  </button>`).join('') || '<div class="empty-state">No Valheim servers discovered yet.</div>';
  $('realms').querySelectorAll('[data-server]').forEach(button=>button.addEventListener('click',()=>{selected=selected===button.dataset.server?'':button.dataset.server;$('serverFilter').value=selected;render();}));
  const oldFocus = document.activeElement;
  if(oldFocus!==$('serverFilter')) {
    $('serverFilter').innerHTML = '<option value="">All realms</option>'+data.servers.map(s=>`<option value="${esc(s.id)}">${esc(s.name)}</option>`).join('');
    $('serverFilter').value=selected;
  }
  const active = data.players.filter(p=>p.online&&p.confirmed&&!stale&&matchingServer(p.server));
  const unnamed = data.servers.filter(s=>matchingServer(s.id)).reduce((n,s)=>n+s.unnamed_players,0);
  $('onlineCount').textContent=active.length+unnamed;
  $('onlinePlayers').innerHTML = active.map(p=>`<div class="online-player"><span class="avatar">${esc(initials(p.name))}</span><div><strong>${esc(p.name)}</strong><small>${esc(serverName(p.server))} · Joined ${shortTime(p.last_login)}</small></div><i class="status-dot"></i></div>`).join('')+(unnamed?`<div class="empty-state">${unnamed} more ${unnamed===1?'player':'players'} online; character names are not present in the available logs.</div>`:'') || `<div class="empty-state">${stale?'Live player data is unavailable.':data.servers.some(s=>matchingServer(s.id)&&s.status==='unreachable')?'Some servers cannot be queried. No confirmed players to show.':'The campfire is quiet. No Vikings are online in '+(selected?'this realm.':'any realm.')}</div>`;
  const search = $('search').value.trim().toLocaleLowerCase();
  const players = data.players.filter(p=>matchingServer(p.server)&&p.name.toLocaleLowerCase().includes(search));
  $('playerRows').innerHTML = players.map(p=>`<tr><td><span class="player-name"><span class="avatar">${esc(initials(p.name))}</span>${esc(p.name)}</span></td><td class="realm-cell">${esc(serverName(p.server))}</td><td><span class="player-state ${p.online&&p.confirmed?'online':''}"><i class="status-dot"></i>${p.online?(p.confirmed&&!stale?'Online':'Unconfirmed'):'Offline'}</span></td><td class="time-cell">${timeCell(p.last_login)}</td><td class="time-cell">${timeCell(p.last_logout,p.logout_reason&&p.logout_reason!=='log')}</td><td class="number">${p.sessions}</td></tr>`).join('')||`<tr><td colspan="6" class="table-empty">${search?'No characters match your search.':'No character sessions have been recorded '+(selected?'for this realm ':'')+'in the available logs yet.'}</td></tr>`;
  $('ledgerCount').textContent = `${players.length} character ${players.length===1?'record':'records'}`;
  const events = data.events.filter(e=>matchingServer(e.server)&&e.player.toLocaleLowerCase().includes(search)).slice(0,30);
  $('activity').innerHTML = events.map(e=>`<div class="activity-item"><span class="activity-icon ${esc(e.kind)}" aria-hidden="true">${e.kind==='join'?'↗':'↙'}</span><span class="activity-copy"><strong>${esc(e.player)}</strong> ${e.kind==='join'?'arrived':'left'}<small>${esc(serverName(e.server))}${e.reason&&e.reason!=='log'?' · '+(e.reason==='server_restart'?'server restarted':e.reason==='server_stopped'?'server stopped':'detected offline'):''}</small></span><time class="activity-time" datetime="${esc(e.at)}" title="${shortDate(e.at)} ${shortTime(e.at)}">${isToday(e.at)?'Today':shortDate(e.at)} · ${shortTime(e.at)}</time></div>`).join('')||'<div class="empty-state">No matching activity recorded yet.</div>';
  renderPortals();
  $('historyStart').textContent=data.history_start?`Available logs since ${shortDate(data.history_start)}`:'History starts with available logs.';
  $('updatedAt').textContent=`Updated ${shortTime(data.updated_at)} London`;
}

async function refresh() {
  if(loading) return;
  loading=true;$('refresh').disabled=true;
  try {
    const response=await fetch('/api/status',{cache:'no-store',signal:AbortSignal.timeout(10000)});
    if(response.status===401||response.status===403) {
      showNotice('Your sign-in session has ended. Refresh this page to sign in through authentik.');
      $('liveBadge').classList.add('stale');$('liveBadge').innerHTML='<i></i> SIGN IN REQUIRED';
      return;
    }
    const result=await response.json();
    if(!response.ok) throw new Error(result.error||'Server scan unavailable');
    state=result;render();
  } catch(error) {
    showNotice(state?'Cannot refresh the dashboard. The values shown are the last received snapshot.':error.message);
    $('liveBadge').classList.add('stale');$('liveBadge').innerHTML='<i></i> CONNECTION LOST';
  } finally {loading=false;$('refresh').disabled=false;}
}
$('refresh').addEventListener('click',refresh);
$('serverFilter').addEventListener('change',()=>{selected=$('serverFilter').value;if(state)render();});
$('search').addEventListener('input',()=>{if(state)render();});



// A seed-independent schematic: never reads terrain, seeds or exploration data.
// Colours mark approximate distance thresholds, not exclusive biome boundaries.
function worldBackdrop(px, py, scale) {
  const cx=px({x:0}), cy=py({z:0}), radius=10500*scale;
  const bands=[{r:10000,c:'mistlands'},{r:6000,c:'plains'},{r:3000,c:'swamp'},{r:2000,c:'forest'},{r:600,c:'meadows'}];
  const rings=[2000,4000,6000,8000,10000];
  const guide=bands.map(b=>`<circle cx="${cx}" cy="${cy}" r="${b.r*scale}" class="biome-guide ${b.c}"/>`).join('');
  // Illustrative polar caps only; these curves are not generated coastlines.
  const capY=7200*scale, capX=Math.sqrt(10500**2-7200**2)*scale;
  const north=`M${cx-capX} ${cy-capY} A${radius} ${radius} 0 0 1 ${cx+capX} ${cy-capY} Z`;
  const south=`M${cx+capX} ${cy+capY} A${radius} ${radius} 0 0 1 ${cx-capX} ${cy+capY} Z`;
  const polarX=cx-2600*scale, snowX=polarX, snowY=cy-9400*scale, fireY=cy+9400*scale;
  const polar=`<path d="${north}" class="polar-cap deep-north"/><path d="${south}" class="polar-cap ashlands"/><path d="M${cx-capX} ${cy-capY}H${cx+capX}M${cx-capX} ${cy+capY}H${cx+capX}" class="polar-guide-boundary"/><g class="polar-snow" transform="translate(${snowX} ${snowY})"><path d="M-9 0H9M-4.5 -7.8L4.5 7.8M-4.5 7.8L4.5 -7.8M-7 -3L-4 0 -7 3M7 -3L4 0 7 3"/></g><g class="polar-fire" transform="translate(${polarX} ${fireY})"><path d="M0 -11C7 -4 4 -2 8 2C11 10 -10 12 -8 2C-7 -2 -3 -2 -3 -7C1 -3 0 0 2 1C5 -4 0 -6 0 -11Z"/></g><text x="${polarX}" y="${cy-8200*scale}" text-anchor="middle" class="polar-label">DEEP NORTH</text><text x="${polarX}" y="${cy+8200*scale}" text-anchor="middle" class="polar-label">ASHLANDS</text>`;
  const distances=rings.map(r=>`<circle cx="${cx}" cy="${cy}" r="${r*scale}" class="distance-ring"/><text x="${cx+r*scale*.707+4}" y="${cy-r*scale*.707-4}" class="distance-label">${r/1000} km</text>`).join('');
  return `<rect width="800" height="600" class="map-background"/><circle cx="${cx}" cy="${cy}" r="${radius}" class="world-disc"/>${guide}${polar}<path d="M${cx-radius} ${cy}H${cx+radius}M${cx} ${cy-radius}V${cy+radius}" class="map-axis"/>${distances}<circle cx="${cx}" cy="${cy}" r="${radius}" class="world-edge"/><path d="M${cx-7} ${cy}h14M${cx} ${cy-7}v14" class="world-origin"/><text x="${cx+10}" y="${cy+19}" class="origin-label">0, 0</text><text x="400" y="24" text-anchor="middle" class="compass-label">N ↑ · DEEP NORTH</text><text x="400" y="586" text-anchor="middle" class="compass-label">S ↓ · ASHLANDS</text><text x="${cx}" y="${cy+radius+21}" text-anchor="middle" class="edge-label">WORLD EDGE · 10.5 km from centre</text><text x="24" y="34">W</text><text x="770" y="34">E</text>`;
}

let portalWorld = '', portalSelected = '', portalZoom = 1, portalFit = false;
const portalStatus = {linked:'Linked',unpaired:'Unpaired',unresolved:'Unresolved link',unknown:'Unknown connection'};
function renderPortals() {
  const worlds = state.servers;
  if(!worlds.some(s=>s.id===portalWorld)) portalWorld=selected||[...worlds].sort((a,b)=>(b.portal_registry?.portals?.length||0)-(a.portal_registry?.portals?.length||0))[0]?.id||'';
  $('portalWorld').innerHTML=worlds.map(s=>`<option value="${esc(s.id)}">${esc(s.name)} · ${esc(s.world)}</option>`).join('');
  $('portalWorld').value=portalWorld;
  const world=worlds.find(s=>s.id===portalWorld), registry=world?.portal_registry;
  const all=registry?.portals||[], byId=new Map(all.map(p=>[p.id,p]));
  const query=$('portalSearch').value.toLocaleLowerCase();
  const visible=all.filter(p=>(!$('portalUnpaired').checked||p.status==='unpaired')&&p.tag.toLocaleLowerCase().includes(query));
  const linked=all.filter(p=>p.status==='linked').length;
  const old=registry?.saved_at && Date.now()-Date.parse(registry.saved_at)>3600000;
  $('portalSummary').textContent = registry ? `${all.length} endpoints · ${linked/2} saved pairs · ${all.filter(p=>p.status==='unpaired').length} unpaired · ${all.filter(p=>!['linked','unpaired'].includes(p.status)).length} unresolved/unknown. ${registry.saved_at?'Saved '+shortDate(registry.saved_at)+' '+shortTime(registry.saved_at)+' London. ':''}${registry.error?'Read failed: '+registry.error+'. '+(all.length?'Showing the last successful scan.':''):''}${old?'Save is over an hour old. ':''}${state.stale?'Monitor data is delayed.':''}` : 'Portal data is not available yet.';
  $('portalRows').innerHTML=visible.map(p=>{
    const q=byId.get(p.target);
    return `<tr class="${portalSelected===p.id?'portal-selected':''}"><td><button class="portal-row-button" data-portal="${esc(p.id)}">${esc(p.tag||'(blank tag)')}</button><small>X ${Math.round(p.x)} · Y ${Math.round(p.y)} · Z ${Math.round(p.z)}</small></td><td><span class="portal-status ${esc(p.status)}">${esc(portalStatus[p.status]||'Unknown')}</span>${p.same_tag_count>2?'<small>Duplicate tag</small>':''}</td><td>${q?`${esc(q.tag||'(blank tag)')}<small>X ${Math.round(q.x)} · Z ${Math.round(q.z)}</small>`:'—'}</td></tr>`;
  }).join('')||'<tr><td colspan="3" class="table-empty">'+(registry?.error&&!all.length?'Save unavailable.':all.length?'No matching portals.':'No portals in this committed save.')+'</td></tr>';
  $('portalRows').querySelectorAll('[data-portal]').forEach(b=>b.addEventListener('click',()=>{portalSelected=b.dataset.portal;renderPortals();}));
  const focus=byId.get(portalSelected);
  $('portalDetail').textContent=focus?`${focus.tag||'(blank tag)'}: X ${focus.x.toFixed(1)}, Y ${focus.y.toFixed(1)}, Z ${focus.z.toFixed(1)}. ${portalStatus[focus.status]}. ${focus.same_tag_count} endpoint(s) have this exact tag. Links use saved connection records; matching tags alone do not establish a link.`:'Linked means a saved connection, not a live teleportability check. Unpaired means no saved partner. Blank and duplicate tags are preserved exactly.';
  // Use a consistent frame for the world; searching does not change the scale.
  const xs=all.map(p=>p.x), zs=all.map(p=>p.z);
  const minX=Math.min(0,...xs),maxX=Math.max(0,...xs),minZ=Math.min(0,...zs),maxZ=Math.max(0,...zs);
  const center=focus&&portalZoom>1?focus:portalFit?{x:(minX+maxX)/2,z:(minZ+maxZ)/2}:{x:0,z:0};
  const scale=(portalFit?Math.min(700/Math.max(200,maxX-minX),500/Math.max(200,maxZ-minZ)):250/10500)*portalZoom;
  const px=p=>400+(p.x-center.x)*scale, py=p=>300-(p.z-center.z)*scale;
  const show=new Set(visible.map(p=>p.id));
  const lines=all.filter(p=>p.status==='linked'&&p.id<p.target&&show.has(p.id)&&show.has(p.target)).map(p=>{
    const q=byId.get(p.target); if(!q)return '';
    return `<line x1="${px(p)}" y1="${py(p)}" x2="${px(q)}" y2="${py(q)}" class="portal-link ${portalSelected===p.id||portalSelected===q.id?'highlight':''}"/>`;
  }).join('');
  $('portalMap').innerHTML=`<title>Portal positions for ${esc(world?.world||'world')}</title>${worldBackdrop(px,py,scale)}${lines}`+visible.map(p=>`<g role="button" tabindex="0" data-portal="${esc(p.id)}" aria-label="${esc(p.tag||'Blank tag')}, ${esc(portalStatus[p.status])}" class="portal-point ${esc(p.status)} ${portalSelected===p.id?'highlight':''}"><title>${esc(p.tag||'(blank tag)')} · X ${Math.round(p.x)}, Z ${Math.round(p.z)} · ${esc(portalStatus[p.status])}</title><circle cx="${px(p)}" cy="${py(p)}" r="${portalSelected===p.id?9:6}"/>${all.length<40||portalSelected===p.id?`<text x="${px(p)+10}" y="${py(p)-8}">${esc(p.tag||'(blank)')}</text>`:''}</g>`).join('');
  $('portalMap').querySelectorAll('[data-portal]').forEach(b=>{
    const choose=()=>{portalSelected=b.dataset.portal;renderPortals();};
    b.addEventListener('click',choose);b.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();choose();}});
  });
}
$('portalWorld').addEventListener('change',()=>{portalWorld=$('portalWorld').value;portalSelected='';portalZoom=1;portalFit=false;if(state)renderPortals();});
$('portalSearch').addEventListener('input',()=>{if(state)renderPortals();});
$('portalUnpaired').addEventListener('change',()=>{if(state)renderPortals();});
$('portalZoomIn').addEventListener('click',()=>{portalZoom=Math.min(16,portalZoom*1.5);if(state)renderPortals();});
$('portalZoomOut').addEventListener('click',()=>{portalZoom=Math.max(0.5,portalZoom/1.5);if(state)renderPortals();});
$('portalReset').addEventListener('click',()=>{portalZoom=1;portalSelected='';portalFit=true;if(state)renderPortals();});
$('portalWorldView').addEventListener('click',()=>{portalZoom=1;portalSelected='';portalFit=false;if(state)renderPortals();});
refresh();setInterval(refresh,15000);
