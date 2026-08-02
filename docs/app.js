let papers=[],filtered=[],category='すべて',selected=new Set();
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const localStore=(key,fallback)=>{try{return JSON.parse(localStorage.getItem(key))??fallback}catch{return fallback}};
let favorites=new Set(localStore('favorites',[])),read=new Set(localStore('read',[]));

async function loadData(){
  notice('論文データを読み込んでいます…');
  try{
    const res=await fetch(`data/papers.json?t=${Date.now()}`);
    papers=await res.json();
    notice('');
    renderAll();
  }catch(e){notice('データを読み込めませんでした。GitHub Actionsを一度実行してください。')}
}
function dateStr(d){return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`}
function paperDate(p){return p.entry_date||p.created_at?.slice(0,10)||''}
function renderAll(){
  const now=new Date(),today=dateStr(now),yd=new Date(now);yd.setDate(yd.getDate()-1);
  $('todayCount').textContent=papers.filter(p=>paperDate(p)===today).length;
  $('yesterdayCount').textContent=papers.filter(p=>paperDate(p)===dateStr(yd)).length;
  $('unreadCount').textContent=papers.filter(p=>!read.has(p.pmid)).length;
  $('favoriteCount').textContent=favorites.size;
  renderCategories();applyFilters();
}
function renderCategories(){
  const cats=['すべて',...new Set(papers.map(p=>p.category).filter(Boolean))];
  $('categories').innerHTML=cats.map(c=>`<button class="chip ${c===category?'active':''}" data-cat="${esc(c)}">${esc(c)}</button>`).join('');
  document.querySelectorAll('[data-cat]').forEach(b=>b.onclick=()=>{category=b.dataset.cat;renderCategories();applyFilters()});
}
function dateMatch(p){
  const d=paperDate(p),mode=$('dateMode').value,now=new Date();
  if(mode==='all')return true;
  if(mode==='today')return d===dateStr(now);
  if(mode==='yesterday'){const x=new Date(now);x.setDate(x.getDate()-1);return d===dateStr(x)}
  if(mode==='7days'){const x=new Date(now);x.setDate(x.getDate()-6);return d>=dateStr(x)&&d<=dateStr(now)}
  return d===$('exactDate').value;
}
function applyFilters(){
  const q=$('searchInput').value.toLowerCase();
  filtered=papers.filter(p=>(category==='すべて'||p.category===category)&&dateMatch(p)&&
    [p.title_en,p.title_ja,p.authors,p.abstract_en,p.abstract_ja,(p.keywords||[]).join(' ')].join(' ').toLowerCase().includes(q));
  filtered.sort($('sortMode').value==='score'?(a,b)=>(b.relevance_score||0)-(a.relevance_score||0):(a,b)=>paperDate(b).localeCompare(paperDate(a)));
  renderCards();
}
function renderCards(){
  $('paperCount').textContent=`${filtered.length}件表示`;$('selectedCount').textContent=`${selected.size}件選択`;
  if(!filtered.length){$('cards').innerHTML='<div class="empty">この条件の論文はありません。</div>';return}
  $('cards').innerHTML=filtered.map(p=>`<article class="card"><div class="card-top">
    <input type="checkbox" data-select="${p.pmid}" ${selected.has(p.pmid)?'checked':''}>
    <div><div class="meta">${esc(paperDate(p))}｜${esc(p.category)}｜${'★'.repeat(p.relevance_score||0)}</div>
    <h3>${esc(p.title_en)}</h3><div class="jp">${esc(p.title_ja||'日本語タイトル未生成')}</div>
    <div class="meta">${esc(p.authors)}｜${esc(p.journal)}｜PMID: ${esc(p.pmid)}${p.doi?'｜DOI: '+esc(p.doi):''}</div></div></div>
    <div class="tags">${(p.keywords||[]).map(t=>`<span class="tag">${esc(t)}</span>`).join('')}</div>
    <div class="summary">${esc(p.results||p.purpose||'要約未生成')}</div>
    <div class="actions"><button data-abstract="${p.pmid}">要約・Abstract</button><button data-detail="${p.pmid}">詳細</button>
    <button onclick="window.open('${esc(p.pubmed_url)}','_blank')">PubMed</button>${p.doi_url?`<button onclick="window.open('${esc(p.doi_url)}','_blank')">DOI</button>`:''}
    <button data-fav="${p.pmid}">${favorites.has(p.pmid)?'★':'☆'}</button></div></article>`).join('');
  document.querySelectorAll('[data-select]').forEach(x=>x.onchange=()=>{x.checked?selected.add(x.dataset.select):selected.delete(x.dataset.select);renderCards()});
  document.querySelectorAll('[data-abstract]').forEach(x=>x.onclick=()=>openAbstract(x.dataset.abstract));
  document.querySelectorAll('[data-detail]').forEach(x=>x.onclick=()=>openDetail(x.dataset.detail));
  document.querySelectorAll('[data-fav]').forEach(x=>x.onclick=()=>{favorites.has(x.dataset.fav)?favorites.delete(x.dataset.fav):favorites.add(x.dataset.fav);localStorage.setItem('favorites',JSON.stringify([...favorites]));renderAll()});
}
function getPaper(id){return papers.find(p=>p.pmid===id)}
function sec(t,v){return `<div class="section"><h4>${t}</h4><div class="summary">${esc(v||'記載なし')}</div></div>`}
function openAbstract(id){const p=getPaper(id);read.add(id);localStorage.setItem('read',JSON.stringify([...read]));
  $('modalBody').innerHTML=`<h2>${esc(p.title_en)}</h2><h3>${esc(p.title_ja)}</h3><div class="meta">${esc(p.authors)}｜${esc(p.journal)}｜PMID: ${p.pmid}</div>
  ${sec('背景・目的',p.purpose)}${sec('方法',p.methods)}${sec('主な結果',p.results)}${sec('結論',p.conclusion)}${sec('限界',p.limitations)}${sec('研究への関連性',p.research_relevance)}
  <div class="section"><h4>Abstract（PubMed原文全文）</h4><div class="abstract">${esc(p.abstract_en||'Abstract未登録')}</div></div>
  <div class="section"><h4>Abstract 日本語訳（全文）</h4><div class="abstract">${esc(p.abstract_ja||'翻訳できませんでした。')}</div></div>`;showModal();renderAll()}
function openDetail(id){const p=getPaper(id),rows=p.result_table||[];
  $('modalBody').innerHTML=`<h2>詳細｜${esc(p.title_en)}</h2>${sec('研究デザイン',p.study_design)}${sec('方法の詳細',p.detail_methods)}${sec('結果の詳細',p.detail_results)}
  <div class="section"><h4>Abstractから抽出した数値</h4>${rows.length?`<table class="detail-table"><thead><tr><th>項目</th><th>値</th><th>根拠文</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(r.item)}</td><td>${esc(r.value)}</td><td>${esc(r.source)}</td></tr>`).join('')}</tbody></table>`:'<p>抽出できる数値はありません。</p>'}</div>`;showModal()}
function showModal(){$('modal').classList.add('show')}function notice(x){$('notice').style.display=x?'block':'none';$('notice').textContent=x}
function exportCsv(){const list=papers.filter(p=>selected.has(p.pmid));if(!list.length)return alert('論文を選択してください。');
  const cols=['category','title_en','title_ja','authors','journal','publication_date','entry_date','pmid','doi','study_design','purpose','methods','results','conclusion','limitations','research_relevance','abstract_en','abstract_ja','pubmed_url','doi_url'];
  const q=v=>`"${String(v??'').replace(/"/g,'""')}"`;const csv='\ufeff'+[cols.map(q).join(','),...list.map(p=>cols.map(c=>q(p[c])).join(','))].join('\r\n');
  const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));a.download=`新着論文_${new Date().toISOString().slice(0,10)}.csv`;a.click()}
function ask(){const q=$('chatQuestion').value.trim().toLowerCase(),list=papers.filter(p=>selected.has(p.pmid));if(!list.length)return $('chatLog').textContent='論文を選択してください。';
  $('chatLog').textContent=list.map(p=>{let a;if(/方法|対象|解析/.test(q))a=p.detail_methods||p.methods;else if(/結果|数値|p値|割合/.test(q))a=p.detail_results||p.results;else if(/結論/.test(q))a=p.conclusion;else if(/限界/.test(q))a=p.limitations;else if(/abstract|日本語訳|翻訳/.test(q))a=p.abstract_ja;else a=`目的: ${p.purpose}\n方法: ${p.methods}\n結果: ${p.results}\n結論: ${p.conclusion}`;return `【PMID ${p.pmid}】\n${p.title_en}\n${a||'該当情報なし'}`}).join('\n\n')}
$('reloadBtn').onclick=loadData;$('closeModal').onclick=()=>{$('modal').classList.remove('show')};$('chatToggle').onclick=()=>$('chatPanel').classList.toggle('show');$('askBtn').onclick=ask;
$('selectVisibleBtn').onclick=()=>{filtered.forEach(p=>selected.add(p.pmid));renderCards()};$('exportBtn').onclick=exportCsv;
$('searchInput').oninput=applyFilters;$('dateMode').onchange=applyFilters;$('sortMode').onchange=applyFilters;$('exactDate').onchange=()=>{$('dateMode').value='exact';applyFilters()};
loadData();
