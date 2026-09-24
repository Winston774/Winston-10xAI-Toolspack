import { createSession } from './session.mjs';
const session = createSession({ fetchImpl: (_endpoint, options) => fetch('/api/jev', { ...options, cache: 'no-store', credentials: 'omit' }) });
const $ = id => document.getElementById(id);
const COLORS = { I:'#43b9d4', O:'#e2b73e', T:'#a084d5', S:'#67b98e', Z:'#e17b85', J:'#6c9de0', L:'#e3a167', G:'#aebbcf' };
const SHAPES = { I:[[0,0],[1,0],[2,0],[3,0]], O:[[0,0],[1,0],[0,1],[1,1]], T:[[0,0],[1,0],[2,0],[1,1]], S:[[1,0],[2,0],[0,1],[1,1]], Z:[[0,0],[1,0],[1,1],[2,1]], J:[[0,0],[0,1],[1,1],[2,1]], L:[[2,0],[0,1],[1,1],[2,1]] };
const MOTIVES = [
 {id:'survive',label:'生存',color:'#d8798a'}, {id:'cleanup',label:'整地',color:'#419f98'},
 {id:'build',label:'堆疊',color:'#8e80c5'}, {id:'clear',label:'消行',color:'#bf963e'},
 {id:'spin',label:'旋轉機會',color:'#699ed2'},
];
const motive = id => MOTIVES.find(m => m.id === id) || {id:'baseline',label:'基本',color:'#8f97a7'};
const escape = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const percent = value => Number.isFinite(value) ? `${Math.round(value*100)}%` : '—';
const number = value => Number(value || 0).toLocaleString('zh-TW');
const sleep = ms => new Promise(resolve => setTimeout(resolve,ms));
let game, configured=false, mode='preview', running=false, busy=false, executing=false, remoteBusy=false, phase='idle', currentDecision=null;
let partial={senses:[],proposals:[]}, history=[], stats={calls:0,tokens:0,veto:0,decisions:0}, generation=0, animation=null;
let initialized=false;
const canvas=$('board'), ctx=canvas.getContext('2d');
const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;

async function api(path,body) {
 return session.request(path,body);
}
function showError(error) {$('error-banner').textContent=error?.message||String(error);$('error-banner').hidden=false;}
function clearError() {$('error-banner').hidden=true;}
function setPhase(value) {
 phase=value;const names={idle:'待命中',sense:'感知中',motor:'提出落點',judge:'裁判判定',move:'執行落子',paused:'已暫停',done:'遊戲結束'};
 $('stage-pill').innerHTML=`<i></i>${names[value]||'待命中'}`;
 $('stage-pill').classList.toggle('running',['sense','motor','judge','move'].includes(value));
 $('session-state').textContent=names[value]||'準備就緒';
 $('board-tag').textContent=({idle:'等待決策',sense:'讀取局面',motor:'比較候選落點',judge:'裁判與教練判定',move:'執行所選落點',paused:'決策已暫停',done:'本局結束'})[value]||'等待決策';
 $('board-tag').classList.toggle('active',['sense','motor','judge','move'].includes(value));
 drawNetwork();
}
function syncControls() {
 $('start-button').innerHTML=running||executing?'<svg viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><path d="M4 3h3v10H4zm5 0h3v10H9z"/></svg><span>暫停</span>':`<svg viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><path d="m5 3 8 5-8 5z"/></svg><span>${mode==='live'?'開始即時執行':'開始預演'}</span>`;
 $('start-button').disabled=!initialized||(!running&&!executing&&busy)||remoteBusy||game?.gameOver;
 $('step-button').disabled=!initialized||running||busy||remoteBusy||game?.gameOver;
 for(const id of ['preview-mode','live-mode','scenario','reset-button','settings-button']) $(id).disabled=!initialized||busy||running||remoteBusy;
 $('preview-mode').setAttribute('aria-pressed',String(mode==='preview'));
 $('live-mode').setAttribute('aria-pressed',String(mode==='live'));
 $('mode-note').classList.toggle('live',mode==='live');
 $('mode-note').innerHTML=mode==='live'?`<i></i>Jev 即時 · ${configured?'API 金鑰已設定':'請設定 API 金鑰'}`:'<i></i>本機啟發式預演 · 不呼叫 API';
 $('connection-dot').classList.toggle('connected',configured);
 $('latency-label').textContent=mode==='live'?'本輪 API 決策時間':'本輪預演時間';
}
function miniPiece(type, color=COLORS[type], extra='') {
 const cells=SHAPES[type]||SHAPES.T,w=Math.max(...cells.map(c=>c[0]))+1,h=Math.max(...cells.map(c=>c[1]))+1;
 return `<svg viewBox="0 0 52 36" aria-hidden="true" ${extra}>${cells.map(([x,y])=>`<rect x="${(52-w*10)/2+x*10}" y="${(36-h*10)/2+y*10}" width="9" height="9" rx="1.5" fill="${color}"/>`).join('')}</svg>`;
}
function updateGameLabels() {
 if(!game)return;
 $('score').textContent=number(game.score);$('lines').textContent=number(game.lines);$('pieces').textContent=number(game.pieces);
 $('round-label').textContent=`第 ${String(game.pieces+1).padStart(2,'0')} 個方塊`;
 $('next-pieces').innerHTML=game.next.map(p=>`<div class="mini-piece" aria-label="${p} 方塊">${miniPiece(p)}</div>`).join('');
 $('board-message').hidden=!game.gameOver;
 $('board-message').textContent=game.gameOver?'本局完成。\n重新開始，看看另一種決定。':'';
 if(game.gameOver){running=false;setPhase('done');}
}
function block(x,y,color,{alpha=1,outline=false,veto=false}={}) {
 const s=60;ctx.save();ctx.globalAlpha=alpha;ctx.beginPath();ctx.roundRect(x*s+2.4,y*s+2.4,s-4.8,s-4.8,7);
 if(outline){ctx.lineWidth=3;ctx.strokeStyle=veto?'#cc4358':color;ctx.stroke();ctx.fillStyle=veto?'#cc435817':`${color}22`;ctx.fill();}
 else{ctx.fillStyle=color;ctx.fill();ctx.fillStyle='#ffffff22';ctx.beginPath();ctx.roundRect(x*s+5,y*s+5,s-10,5,3);ctx.fill();}
 if(veto){ctx.beginPath();ctx.strokeStyle='#cc435870';ctx.lineWidth=1.8;for(let i=8;i<55;i+=12){ctx.moveTo(x*s+i,y*s+4);ctx.lineTo(x*s+4,y*s+i);}ctx.stroke();}
 ctx.restore();
}
function drawBoard(moving=null) {
 if(!game)return;ctx.clearRect(0,0,600,1200);ctx.fillStyle='#f0f2f6';ctx.fillRect(0,0,600,1200);
 ctx.strokeStyle='#e3e7ee';ctx.lineWidth=1;ctx.beginPath();for(let x=0;x<=10;x++){ctx.moveTo(x*60,0);ctx.lineTo(x*60,1200);}for(let y=0;y<=20;y++){ctx.moveTo(0,y*60);ctx.lineTo(600,y*60);}ctx.stroke();
 game.board.forEach((row,y)=>row.forEach((p,x)=>{if(p)block(x,y,COLORS[p]||COLORS.G);}));
 if(['motor','judge','move'].includes(phase)&&partial.version===game.version){
 const unique=new Set();const candidates=[...partial.proposals].sort((a,b)=>Number(a.id===partial.selectedProposalId)-Number(b.id===partial.selectedProposalId));
 for(const p of candidates){if(!p.placement||unique.has(`${p.placementId}-${p.veto}`))continue;unique.add(`${p.placementId}-${p.veto}`);const color=motive(p.motiveId).color;
 p.placement.cells.forEach(({x,y})=>block(x,y,color,{outline:true,veto:p.veto,alpha:p.id===partial.selectedProposalId?1:.55}));
 if(p.id===partial.selectedProposalId){const {x,y}=p.placement;ctx.fillStyle=p.veto?'#a33048':'#376799';ctx.font='500 19px system-ui';ctx.textAlign='left';ctx.fillText(`${p.veto?'否決':motive(p.motiveId).label} ${percent(p.probability)}`,Math.min(x*60+2,470),Math.max(75,y*60-10));}
 }
 }
 if(moving){moving.cells.forEach(({x,y})=>block(x,moving.y+y,COLORS[game.current]));}
 else if(!game.gameOver){const shape=SHAPES[game.current];const width=Math.max(...shape.map(c=>c[0]))+1;shape.forEach(([x,y])=>block(x+Math.floor((10-width)/2),y+1,COLORS[game.current],{alpha:.9}));}
}
function drawNetwork() {
 const width=580, xs=[80,185,290,395,500];let svg=`<svg viewBox="0 0 ${width} 336" xmlns="http://www.w3.org/2000/svg"><text class="layer-label" x="3" y="22">01 感知層</text><text class="node-secondary" x="577" y="22" text-anchor="end">現在，什麼最重要？</text>`;
 const senses=MOTIVES.map(m=>({...m,...partial.senses.find(s=>s.id===m.id)}));
 const active=senses.filter(s=>s.active);const props=partial.proposals;
 const py=181;const motorXs=props.length?props.map((_,i)=>props.length===1?290:58+i*(464/(props.length-1))):[150,290,430];
 // Wires are tied to actual active motives and actual motor proposals.
 if(props.length) props.forEach((p,i)=>{const n=MOTIVES.findIndex(m=>m.id===p.motiveId);const x=n<0?555:xs[n];const color=motive(p.motiveId).color;
 svg+=`<path class="wire ${phase!=='idle'?'active':''}" style="--wire:${color}" d="M${x} ${n<0?112:98} C${x} 128,${motorXs[i]} 123,${motorXs[i]} 159"/>`;
 svg+=`<path class="wire ${['judge','move'].includes(phase)?'active':''}" style="--wire:${p.veto?'#ce7685':color}" d="M${motorXs[i]} 199 C${motorXs[i]} 223,248 224,248 253"/>`;
 });
 else{xs.forEach(x=>{svg+=`<path class="wire" d="M${x} 99 C${x} 132,290 125,290 159"/>`;});svg+='<path class="wire" d="M290 199 C290 228,248 224,248 253"/>';}
 svg+='<path class="wire" d="M389 272 H296"/>';
 if(phase==='judge'||phase==='move')svg+=`<path class="wire active" style="--wire:${partial.proposals.some(p=>p.veto)?'#ce7685':'#7b94b7'}" d="M389 272 H296"/>`;
 senses.forEach((s,i)=>{const dim=partial.senses.length&&!s.active;svg+=`<g class="neuron ${dim?'inactive':''} ${phase==='sense'?'phase-active':''}"><circle cx="${xs[i]}" cy="76" r="24" fill="${s.color}0e"/><circle class="node-ring" cx="${xs[i]}" cy="76" r="21" stroke="${partial.senses.length&&s.active?s.color:'#dce0e8'}"/><text class="node-prob" x="${xs[i]}" y="81" text-anchor="middle" fill="${s.color}">${percent(s.probability)}</text><text class="node-label" x="${xs[i]}" y="116" text-anchor="middle">${s.label}</text></g>`;});
 svg+='<text class="layer-label" x="3" y="146">02 運動層</text>';
 if(props.length){svg+='<circle cx="555" cy="108" r="4" fill="#abb4c3"/><text class="node-secondary" x="555" y="123" text-anchor="middle">基本</text>';props.forEach((p,i)=>{const color=motive(p.motiveId).color;svg+=`<g class="${phase==='motor'?'phase-active':''}"><rect class="node-ring" x="${motorXs[i]-37}" y="162" width="74" height="38" rx="8" stroke="${p.veto?'#d57583':color}"/><text class="node-label" x="${motorXs[i]}" y="177" text-anchor="middle">${motive(p.motiveId).label}</text><text class="node-secondary" x="${motorXs[i]}" y="191" text-anchor="middle">第 ${p.placement.x+1} 欄 · R${p.placement.rotation}</text></g>`;});}
 else svg+='<rect x="235" y="162" width="110" height="38" rx="8" fill="#f7f8fa" stroke="#e4e7ed"/><text class="node-secondary" x="290" y="184" text-anchor="middle">等待落點提案</text>';
 svg+='<text class="layer-label" x="3" y="236">03 判定層</text>';
 const judged=Boolean(partial.selectedProposalId),chosen=props.find(p=>p.id===partial.selectedProposalId),veto=props.filter(p=>p.veto).length;
 svg+=`<g class="${phase==='judge'?'phase-active':''}"><rect class="node-ring" x="199" y="253" width="98" height="43" rx="10" stroke="${judged?'#6995d1':'#dce0e8'}"/><text class="node-label" x="248" y="271" text-anchor="middle">裁判</text><text class="node-secondary" x="248" y="286" text-anchor="middle">${judged?`${motive(chosen?.motiveId).label} · ${percent(chosen?.probability)}`:'選擇提案'}</text><rect class="node-ring" x="389" y="253" width="98" height="43" rx="10" stroke="${veto?'#d57583':'#dce0e8'}"/><text class="node-label" x="438" y="271" text-anchor="middle">教練</text><text class="node-secondary" x="438" y="286" text-anchor="middle">${judged?(veto?`${veto} 個否決`:'通過檢查'):'檢查風險'}</text></g>`;
 svg+=`<text class="node-secondary" x="290" y="324" text-anchor="middle">${partial.fallback?'全部提案受否決 · 使用本機基本提案':judged?'判定完成，將所選落點交給遊戲執行。':active.length?`${active.length} 種動機已啟動，並保留基本提案。`:'程式讀取棋盤 · Jev 負責判斷'}</text></svg>`;
 $('network').innerHTML=svg;$('network').setAttribute('aria-label',`三層決策網路，${active.length} 個動機啟動，${props.length} 個提案，${veto} 個否決`);
}
function drawProposals() {
 const props=partial.proposals;
 if(!props.length){$('proposal-count').textContent='等待提案';$('proposals').innerHTML='<div class="empty-proposals"><span>開始後，這裡會比較各個落點。<small>你也可以用「單步決策」慢慢看。</small></span></div>';return;}
 $('proposal-count').textContent=`${props.length} 個提案 · ${new Set(props.map(p=>p.placementId)).size} 個落點`;
 const sorted=[...props].sort((a,b)=>Number(b.id===partial.selectedProposalId)-Number(a.id===partial.selectedProposalId)||b.probability-a.probability);
 $('proposals').innerHTML=sorted.map(p=>{const selected=p.id===partial.selectedProposalId,m=motive(p.motiveId),f=p.placement.features;
 const piece=partial.rawTrace?.[0]?.request?.state?.current||game?.current||'T';
 return `<div class="proposal ${selected?'selected':''} ${p.veto?'veto':''}"><div class="proposal-piece">${miniPiece(piece,m.color)}</div><div><div class="proposal-topline"><span>${m.label}</span><small>第 ${p.placement.x+1} 欄 · 旋轉 ${p.placement.rotation}</small></div><div class="proposal-meta"><span>消除 ${f.linesCleared} 行</span><span>空洞 ${f.holes}</span><span>高度 ${f.maxHeight}</span></div><div class="prob-bar"><i style="width:${Math.max(0,p.probability*100)}%;--bar:${p.veto?'#cc4358':m.color}"></i></div></div><div class="proposal-result"><strong>${partial.selectedProposalId?percent(p.probability):'—'}</strong><span>${selected?(partial.fallback?'教練否決 · 備援執行':'已選擇'):p.veto?'教練否決':'候選'}</span></div></div>`;
 }).join('');
}
function renderMetrics() {
 $('latency').innerHTML=`${currentDecision?number(currentDecision.timings.total):'—'}<small> ms</small>`;
 $('api-calls').innerHTML=`${number(stats.calls)}<small> 次</small>`;
 $('veto-count').innerHTML=`${number(stats.veto)}<small> 次</small>`;
 $('tokens').textContent=mode==='live'&&stats.calls?number(stats.tokens):'—';
 $('history-count').textContent=`${stats.decisions} 個決策`;
 $('history').innerHTML=history.slice(-30).reverse().map((d,i)=>`<div class="history-row"><span>${stats.decisions-i}</span><strong>${d.mode==='live'?'Jev 即時':'本機預演'}</strong><span>${escape(motive(d.proposals.find(p=>p.id===d.selectedProposalId)?.motiveId).label)} → 第 ${d.selected.x+1} 欄${d.fallback?' · 程式備援':d.coachVeto?' · 有提案遭否決':''}</span><span>${number(d.timings.total)} ms</span></div>`).join('');
}
function hydrate(state) {
 game=state.game;currentDecision=state.lastDecision;partial=currentDecision||{senses:[],proposals:[]};
 remoteBusy=Boolean(state.busy&&!executing);
 if(state.recentDecisions)history=state.recentDecisions;
 if(state.sessionStats){const s=state.sessionStats;stats={calls:s.calls,tokens:s.inputTokens,veto:s.vetos,decisions:s.decisions};}
 setPhase(remoteBusy?'sense':game.gameOver?'done':currentDecision?'paused':'idle');
 const selected=currentDecision?.proposals.find(p=>p.id===currentDecision.selectedProposalId);
 $('decision-caption').textContent=currentDecision?(currentDecision.fallback?'所有提案受否決，改採本機基本提案。':`${motive(selected?.motiveId).label}提案獲選${currentDecision.coachVeto?'，教練已排除風險提案':''}。`):'讀取棋盤特徵，讓每個決策都有跡可循。';
 $('decision-time').textContent=currentDecision?`${number(currentDecision.timings.total)} ms`:'—';
 if(state.lastError)showError(new Error(state.lastError.message));
 updateGameLabels();renderMetrics();drawBoard();drawNetwork();drawProposals();
}
function phaseEvent(event) {
 if(!initialized)return;
 if(event.phase==='reset'&&!busy){game=event.detail.game;partial={senses:[],proposals:[]};currentDecision=null;history=[];stats={calls:0,tokens:0,veto:0,decisions:0};setPhase('idle');updateGameLabels();drawBoard();drawProposals();renderMetrics();syncControls();return;}
 if(['move','stopped','error','reset'].includes(event.phase)&&!busy){running=false;generation++;api('/api/state').then(state=>{hydrate(state);syncControls();}).catch(showError);return;}
 if(event.version!==game?.version||!busy)return;
 if(['sense','motor','judge'].includes(event.phase)){
  setPhase(event.phase);if(event.detail){partial={...partial,...event.detail};drawNetwork();drawProposals();drawBoard();}
  const phrases={sense:'感知層正在判斷五種動機。',motor:'啟動的動機，分別選出合適的落點。',judge:'裁判與教練正在同時評估提案。'};$('decision-caption').textContent=phrases[event.phase];
 }
}
async function animatePlacement(placement,ticket) {
 const duration=reduced?0:$('pace').value==='slow'?900:$('pace').value==='fast'?180:430;
 const minY=Math.min(...placement.cells.map(c=>c.y)),cells=placement.cells.map(c=>({x:c.x,y:c.y-minY}));
 return new Promise(resolve=>{const start=performance.now();function frame(now){if(ticket!==generation){resolve();return;}const t=duration?Math.min(1,(now-start)/duration):1;drawBoard({cells,y:1+(minY-1)*(1-Math.pow(1-t,3))});if(t<1)animation=requestAnimationFrame(frame);else{animation=null;resolve();}}animation=requestAnimationFrame(frame);});
}
async function step() {
 if(busy||!game||game.gameOver)return;
 if(mode==='live'&&!configured){running=false;openSettings();syncControls();return;}
 clearError();const ticket=generation;busy=true;executing=true;partial={version:game.version,senses:[],proposals:[]};syncControls();setPhase('sense');drawBoard();drawProposals();
 try{
  const result=await api('/api/step',{mode,version:game.version});
  if(ticket!==generation)return;
  currentDecision=result.decision;partial=currentDecision;drawProposals();setPhase('judge');drawBoard();
  const selected=currentDecision.proposals.find(p=>p.id===currentDecision.selectedProposalId);
  $('decision-caption').textContent=currentDecision.fallback?'所有提案受否決，改採本機基本提案。':`${motive(selected?.motiveId).label}提案獲選${currentDecision.coachVeto?'，教練已排除風險提案':''}。`;
  $('decision-time').textContent=`${number(currentDecision.timings.total)} ms`;
  await sleep(reduced?0:$('pace').value==='slow'?900:230);if(ticket!==generation)return;
  setPhase('move');await animatePlacement(currentDecision.selected,ticket);if(ticket!==generation)return;
  game=result.game;history.push(currentDecision);if(history.length>300)history.shift();
  stats.calls+=currentDecision.calls;stats.tokens+=currentDecision.usage?.inputTokens||0;stats.veto+=currentDecision.proposals.filter(p=>p.veto).length;stats.decisions++;
  updateGameLabels();renderMetrics();drawBoard();
  if(!running&&!game.gameOver)setPhase('paused');
 }catch(error){if(ticket===generation){running=false;if(!['STOPPED','STALE_RESULT'].includes(error.code))showError(error);setPhase('paused');try{hydrate(await api('/api/state'));}catch{}}}
 finally{busy=false;executing=false;syncControls();}
}
async function play() {
 if(!initialized||!game)return;
 if(running||executing){await stop();return;}
 if(busy)return;if(mode==='live'&&!configured){openSettings();return;}
 running=true;syncControls();const ticket=generation;
 while(running&&ticket===generation&&!game.gameOver){await step();if(!running||ticket!==generation)break;await sleep($('pace').value==='slow'?1300:$('pace').value==='fast'?160:550);}
 if(ticket===generation){running=false;syncControls();}
}
async function stop() {
 running=false;generation++;syncControls();
 try{await api('/api/stop',{});const state=await api('/api/state');hydrate(state);setPhase(game.gameOver?'done':'paused');drawBoard();drawProposals();}
 catch(error){showError(error);}finally{syncControls();}
}
async function reset() {
 if(!initialized||busy||running)return;clearError();generation++;busy=true;syncControls();
 try{const state=await api('/api/reset',{scenario:$('scenario').value,seed:42});game=state.game;partial={senses:[],proposals:[]};currentDecision=null;history=[];stats={calls:0,tokens:0,veto:0,decisions:0};setPhase('idle');updateGameLabels();drawBoard();drawProposals();renderMetrics();$('decision-caption').textContent='讀取棋盤特徵，讓每個決策都有跡可循。';$('decision-time').textContent='—';}
 catch(error){showError(error);}finally{busy=false;syncControls();}
}
async function selectMode(value){if(busy||running||value===mode)return;mode=value;await reset();syncControls();}
function openSettings(){ $('key-status').textContent=configured?'已設定金鑰，可直接開始即時執行。':'尚未設定 API Key。';$('settings-dialog').showModal();}
$('start-button').addEventListener('click',play);$('step-button').addEventListener('click',step);
$('reset-button').addEventListener('click',reset);$('scenario').addEventListener('change',reset);
$('preview-mode').addEventListener('click',()=>selectMode('preview'));$('live-mode').addEventListener('click',()=>selectMode('live'));
$('settings-button').addEventListener('click',openSettings);$('about-button').addEventListener('click',()=>$('about-dialog').showModal());
$('focus-button').addEventListener('click',()=>{const enabled=document.body.classList.toggle('focus-mode');$('focus-button').setAttribute('aria-pressed',String(enabled));$('focus-button').textContent=enabled?'退出展示':'展示模式';});
document.querySelectorAll('.close-dialog').forEach(button=>button.addEventListener('click',()=>button.closest('dialog').close()));
document.querySelectorAll('dialog').forEach(dialog=>dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}}));
$('settings-form').addEventListener('submit',async e=>{e.preventDefault();const input=$('api-key'),button=e.submitter;if(!input.value.trim()){$('key-status').textContent='請先貼上 API Key。';return;}button.disabled=true;try{const s=await api('/api/config',{apiKey:input.value.trim()});configured=s.keyConfigured;$('key-status').textContent='金鑰僅供此分頁暫時使用。重新整理、離開頁面或清除後即移除。';syncControls();}catch(error){$('key-status').textContent=error.message;}finally{input.value='';button.disabled=false;}});
$('clear-key').addEventListener('click',async()=>{try{const s=await api('/api/config',{apiKey:''});configured=s.keyConfigured;$('api-key').value='';$('key-status').textContent='金鑰已移除。';syncControls();}catch(error){$('key-status').textContent=error.message;}});
document.addEventListener('keydown',e=>{if(e.code==='Space'&&!e.repeat&&!['INPUT','SELECT','BUTTON','SUMMARY'].includes(document.activeElement.tagName)&&!document.querySelector('dialog[open]')){e.preventDefault();play();}});
document.addEventListener('visibilitychange',()=>{if(document.hidden&&running)stop();});
window.addEventListener('pagehide',()=>{running=false;generation++;session.dispose();configured=false;$('api-key').value='';syncControls();});
window.addEventListener('pageshow',e=>{if(e.persisted){configured=false;syncControls();}});
document.querySelectorAll('dialog').forEach(dialog=>dialog.addEventListener('close',()=>{$('api-key').value='';}));
$('export-link').addEventListener('click',e=>{e.preventDefault();const url=URL.createObjectURL(new Blob([JSON.stringify(session.export(),null,2)],{type:'application/json'}));const anchor=document.createElement('a');anchor.href=url;anchor.download='jev-tetris-session.json';anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
async function boot(){
 try{const [status,state]=await Promise.all([api('/api/status'),api('/api/state')]);configured=status.keyConfigured;game=state.game;mode=state.lastDecision?.mode||'preview';$('scenario').value=game.scenario;initialized=true;hydrate(state);syncControls();
 session.subscribe(phaseEvent);
 }catch(error){showError(error);syncControls();}
}
syncControls();boot();
