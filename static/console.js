const state={apiKey:sessionStorage.getItem("aai_api_key")||"",assets:[],selected:null};
const $=id=>document.getElementById(id);
function toast(m){$("toast").textContent=m;$("toast").classList.add("show");setTimeout(()=>$("toast").classList.remove("show"),2400)}
function esc(v){return String(v??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]))}
async function api(path,options={}){
 const headers={...(options.headers||{})}; if(state.apiKey) headers["X-API-Key"]=state.apiKey;
 const r=await fetch(path,{...options,headers}); let d=null; try{d=await r.json()}catch{}
 if(!r.ok) throw new Error(d?.detail||`Request failed (${r.status})`); return d;
}
function setView(v){document.querySelectorAll(".view").forEach(x=>x.classList.remove("active"));$(`view-${v}`).classList.add("active");document.querySelectorAll("nav button").forEach(x=>x.classList.toggle("active",x.dataset.view===v));$("crumb").textContent="Control Plane / "+v.replace(/^./,x=>x.toUpperCase());if(v==="assets")loadAssets();if(v==="graph")loadGraph();if(v==="protocol")loadProtocol();if(v==="evidence")loadEvidence();if(v==="assurance")loadTrust()}
document.querySelectorAll("nav button").forEach(b=>b.onclick=()=>setView(b.dataset.view));
document.querySelectorAll("[data-action]").forEach(b=>b.onclick=()=>{if(b.dataset.action==="save-key")saveKey();if(b.dataset.action==="clear-key")clearKey();if(b.dataset.action==="refresh")loadAssets()});
async function init(){
 try{const h=await api("/api/health");$("version").textContent="v"+h.version;const r=await api("/api/readiness");$("serviceStatus").textContent=r.status==="ready"?"Operational":"Degraded"}catch(e){$("serviceStatus").textContent="Unavailable"}
 if(state.apiKey){$("apiKey").value=state.apiKey;loadAssets()}
 try{$("manifest").textContent=JSON.stringify(await api("/v1/control/protocol/manifest"),null,2)}catch(e){}
}
async function loadAssets(){
 if(!state.apiKey){$("assetCards").innerHTML='<div class="asset-card"><h3>Connect workspace</h3><p>Add an API key under Workspace.</p></div>';return}
 try{const d=await api("/v1/control/assets");state.assets=d.assets||[];$("metricAssets").textContent=state.assets.length;$("assetCards").innerHTML=state.assets.length?state.assets.map(a=>`<article class="asset-card" onclick="selectAsset('${a.id}')"><h3>${esc(a.name)}</h3><p>${esc(a.asset_type)} · ${esc(a.environment)} · ${esc(a.criticality)}</p><span class="badge">${esc(a.id)}</span></article>`).join(""):'<div class="asset-card"><h3>No assets yet</h3><p>Register the first AI system through the API or SDK.</p></div>'; }catch(e){toast(e.message)}
}
async function selectAsset(id){state.selected=id;setView("assurance");await loadTrust();await loadEvidence()}
async function loadTrust(){
 if(!state.selected)return;
 try{const t=await api(`/v1/control/assets/${state.selected}/trust`);$("metricState").textContent=t.state;$("trustRing").textContent=Math.round(t.score*100)+"%";$("trustHeadline").textContent=t.state;$("trustReasons").textContent=t.reasons.join(" ");$("trustTable").innerHTML=`<tr><td>Reliability</td><td>${esc(t.reliability)}</td><td>${Math.round(t.reliability*100)}%</td></tr><tr><td>Evidence</td><td>${esc(t.evidence_state)}</td><td>—</td></tr><tr><td>Dependencies</td><td>${esc(t.dependency_state)}</td><td>—</td></tr><tr><td>Policy</td><td>${esc(t.policy_state)}</td><td>—</td></tr><tr><td>Epoch</td><td>Persistent</td><td>${t.epoch}</td></tr>`}catch(e){$("trustHeadline").textContent="No trust state";$("trustReasons").textContent=e.message}
}
async function loadEvidence(){
 if(!state.selected)return;
 try{const d=await api(`/v1/control/assets/${state.selected}/evidence`);$("metricEvidence").textContent=d.evidence.length;$("evidenceTable").innerHTML=d.evidence.length?d.evidence.map(e=>`<tr><td>${esc(e.id)}</td><td>${esc(e.evidence_type)}</td><td>${esc(e.result)}</td><td>${esc(e.source)}</td><td class="mono">${esc(e.provenance_hash.slice(0,18))}…</td></tr>`).join(""):'<tr><td colspan="5" class="empty">No evidence.</td></tr>'}catch(e){}
}
async function loadGraph(){
 if(!state.apiKey)return;
 try{const g=await api("/v1/control/graph");$("graphSummary").textContent=`${g.nodes.length} nodes · ${g.edges.length} relationships`;$("graphNodes").innerHTML=g.nodes.map(n=>`<div class="node"><b>${esc(n.label)}</b><span>${esc(n.id)}</span></div>`).join("")}catch(e){toast(e.message)}
}
async function loadProtocol(){try{$("manifest").textContent=JSON.stringify(await api("/v1/control/protocol/manifest"),null,2)}catch(e){$("manifest").textContent=e.message}}
async function saveKey(){const k=$("apiKey").value.trim();if(!k)return toast("Enter an API key.");state.apiKey=k;sessionStorage.setItem("aai_api_key",k);$("keyStatus").textContent="Workspace credential loaded.";toast("Workspace connected.");loadAssets()}
function clearKey(){state.apiKey="";sessionStorage.removeItem("aai_api_key");$("apiKey").value="";$("keyStatus").textContent="No workspace credential loaded.";toast("Workspace disconnected.")}
async function demoDecision(decision){if(!state.selected)return toast("Select an asset first.");try{const d=await api("/v1/control/decisions",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({asset_id:state.selected,action:"execute",context:{ui_demo:true}})});d.ui_requested=decision;$("decisionOutput").textContent=JSON.stringify(d,null,2)}catch(e){toast(e.message)}}
init();
