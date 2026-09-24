const modules=[
['AI Estate Discovery','Discover AI systems, agents, models, tools, APIs, datasets, MCP servers, identities and dependencies.',['Shadow AI detection','Asset classification','Ownership and environment']],
['Agent Identity','Durable identity and lifecycle for every agent, including owner, version, environment and operating identity.',['Version history','Owner accountability','Identity linkage']],
['Authority Graph','Map Agent → Identity → Permission → Tool → API → Data → Business Action.',['Authority drift','Excess privilege','Delegated authority']],
['Permission Control','Compare technical capability with approved authority and enforce least privilege.',['Scoped permissions','Policy checks','Emergency restriction']],
['Production Observability','Capture real production behavior rather than relying only on pre-production claims.',['OpenTelemetry','Runtime events','Operational telemetry']],
['Execution Traces','Reconstruct request → model → context → tool → data → action.',['Trace completeness','Provenance','Replayable evidence']],
['Real-World Evaluation','Evaluate real workflows and system configurations rather than isolated benchmark prompts.',['Scenario orchestration','Workflow evaluation','Regression suites']],
['Adversarial Assurance','Actively probe prompt, context, tool, identity, data and agent boundaries.',['Prompt injection','Tool misuse','Privilege escalation','Context poisoning']],
['Tool & API Security','Evaluate and control tool calls, API access and consequential actions.',['Authorization','Tool provenance','Action policies']],
['Data Boundary Intelligence','Track sensitive data across models, tools, APIs and external destinations.',['PII/financial/health/secret classes','Egress controls','Tenant boundaries']],
['Supply-Chain / AIBOM','Maintain an AI bill of materials across models, tools, libraries, MCP servers and vendors.',['Versions','Provenance','Change alerts']],
['Multi-Agent Governance','Control delegated authority and information flow between cooperating agents.',['Delegation constraints','Authority preservation','Agent trust']],
['Policy Engine','Turn organizational requirements into executable, scoped controls.',['Thresholds','Exceptions','Enforcement actions']],
['Risk Engine','Combine technical findings with exposure, authority, data sensitivity and business impact.',['Explainable risk','Criticality','Exposure']],
['Deployment Gates','Evaluate releases before production and block unsafe changes.',['CI/CD','Release evidence','PASS / REVIEW / BLOCK']],
['Runtime Enforcement','Apply current assurance policy to consequential runtime actions.',['ALLOW','REVIEW','DENY','Quarantine']],
['Human Approval','Route sensitive actions to authorized reviewers with durable evidence.',['Four-eyes approval','Escalation','Approval history']],
['Evidence Fabric','Link findings, traces, policies, versions, approvals and incidents into verifiable evidence.',['Provenance','Integrity','Retention']],
['Assurance Passport','Maintain a machine-readable current assurance state for each AI system.',['Assurance history','Trust state','Verification']],
['Continuous Monitoring','Detect when production behavior, risk or SLOs change.',['Drift','SLO breaches','Stale assurance']],
['Change Impact Analysis','Identify systems, controls and evaluations affected by model, prompt, tool or dependency changes.',['Dependency graph','Targeted reassessment','Change history']],
['Continuous Re-Assurance','Automatically trigger evaluation after material changes or assurance expiry.',['Re-evaluation','Expiry','Evidence refresh']],
['Incident Response','Manage detection → containment → investigation → remediation → retest → restoration.',['Incident records','Containment','Recovery']],
['Remediation Verification','Prove that a corrective control actually resolved the underlying failure.',['Retesting','Verification','Closure']],
['Compliance Evidence Mapping','Map requirements to controls, evidence, findings and remediation.',['Framework mappings','Evidence packages','Audit export']],
['AI Reliability SLOs','Track task success, failures, policy adherence, latency, cost and regressions.',['SLOs','Regression alerts','Reliability trends']],
['Cost Intelligence','Connect inference, tool, retry, failure and human-review costs to AI operations.',['Execution cost','Retry budgets','Cost/risk tradeoffs']],
['Model / Vendor Switching','Compare candidate models or vendors against the same workload, controls and attack suite.',['Behavioral parity','Risk delta','Regression comparison']],
['Shadow AI Detection','Identify unsanctioned AI usage and unknown systems entering the organization.',['Discovery','Classification','Ownership routing']],
['Enterprise Connectors','Integrate identity, cloud, observability, SIEM, CI/CD, API gateways and AI providers.',['OpenTelemetry','Identity','Cloud / SIEM / CI/CD']],
['Central Control Plane','Give security, platform, engineering and risk teams one operational source of truth.',['Fleet posture','Risk queues','Approvals']],
['RBAC / ABAC','Control access to AAI itself according to enterprise roles and attributes.',['Roles','Attributes','Audit']],
['Private Deployment','Support private cloud, VPC, on-premise, hybrid and restricted environments.',['Network isolation','Data residency','Deployment controls']],
['Enterprise Security','Protect assurance data with encryption, secrets, keys, audit logs and isolation.',['Encryption','Key management','Auditability']],
['Executive Risk Intelligence','Show leadership where AI exposure and unresolved critical risk are concentrated.',['Fleet posture','Business exposure','Decision queues']],
['Engineering Intelligence','Give technical teams traces, exact failures, dependencies and remediation details.',['Root-cause context','Evidence','Controls']],
['API / SDK / CLI','Embed assurance into engineering and operational workflows.',['API','SDK','CLI']],
['Runtime Gateway Integration','Enforce AAI policy at API or gateway boundaries without rebuilding the AI system.',['Interception','Policy decisions','Action controls']],
['Evidence Retention','Retain historical assurance evidence according to organizational requirements.',['Retention policies','Exports','Legal-hold support']],
['Emergency Controls','Quarantine or restrict dangerous AI behavior immediately.',['Kill switch','Quarantine','Scoped restriction']],
['Business Ownership','Assign accountable owners and approval authority to every AI system.',['Owner records','Approvers','Escalation']],
['Assurance Intelligence Graph','Connect agents, models, tools, identities, data, policies, findings, incidents and controls.',['Relationships','Impact analysis','Cross-system context']],
['Failure Intelligence','Turn observed failures into reusable assurance scenarios and institutional knowledge.',['Failure patterns','Scenario reuse','Trend analysis']],
['AI-to-AI Assurance','Evaluate one agent\'s interactions with other agents and preserve authority boundaries.',['Delegation','Trust boundaries','Information flow']],
['Marketplace / Ecosystem','Support reusable evaluators, policies, connectors and assurance packs.',['Extensions','Policy packs','Connector ecosystem']],
['Procurement / Government','Support contracted deployments, evidence packages and procurement-specific operating requirements.',['Milestones','Evidence deliverables','Invoice-ready engagement']],
['Audit / Export','Export assurance evidence and decision history for internal, customer and authorized external review.',['Evidence bundles','Decision history','Integrity']],
['Assurance History','Keep the longitudinal record of what was assured, when, against which version and why the state changed.',['Versioned state','Change timeline','Historical evidence']],
['Assurance Blueprint / Requirements','Translate business context, risk classification and applicable requirements into controls and evaluations for each AI system.',['Requirements','Control mapping','Evaluation plan']],
['Data Residency & Sovereign Operations','Operate assurance in jurisdiction-constrained, isolated and sovereignty-sensitive environments.',['Residency policy','Regional isolation','Sovereign deployment']]
];
const grid=document.getElementById('modules');
modules.forEach(([title,desc,items])=>{const el=document.createElement('article');el.className='module';el.innerHTML=`<div class="tag">Paid capability</div><h3>${title}</h3><p>${desc}</p><ul>${items.map(x=>`<li>${x}</li>`).join('')}</ul>`;grid.appendChild(el);});
const locked=document.getElementById('locked'), workspace=document.getElementById('workspace'), status=document.getElementById('gate-status');
const tokenKey='aai_access_token';
function showWorkspace(tier){locked.classList.add('hidden');workspace.classList.remove('hidden');const badge=document.querySelector('[data-tier]');if(badge)badge.textContent=`ENTITLEMENT · ${String(tier||'ACTIVE').toUpperCase()}`;}
async function checkToken(token){if(!token)return null;try{const r=await fetch('/api/access/check',{headers:{authorization:`Bearer ${token}`}});if(!r.ok)return null;return await r.json();}catch(_){return null;}}
async function verify(){
  const credential=document.getElementById('access-code').value.trim();
  if(!credential){status.textContent='Enter the paid-workspace credential supplied after payment or enterprise activation.';status.classList.remove('hidden');return;}
  const button=document.getElementById('unlock'); button.disabled=true; button.textContent='Verifying…'; status.classList.remove('hidden'); status.textContent='Checking entitlement…';
  try{
    const r=await fetch('/api/access/verify',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({credential})});
    const d=await r.json();
    if(r.ok&&d.authorized&&d.token){localStorage.setItem(tokenKey,d.token);showWorkspace(d.tier);status.classList.add('hidden');return;}
    status.textContent=d.error||'Access was not authorized.';
  }catch(_){status.textContent='Access verification is temporarily unavailable.';}
  finally{button.disabled=false;button.textContent='Verify paid access';}
}
document.getElementById('unlock').addEventListener('click',verify);
document.getElementById('access-code').addEventListener('keydown',e=>{if(e.key==='Enter')verify();});
(async()=>{
  const q=new URLSearchParams(location.search);
  const saved=localStorage.getItem(tokenKey);
  const checked=await checkToken(saved);
  if(checked?.authorized){showWorkspace(checked.tier);return;}
  if(saved)localStorage.removeItem(tokenKey);
  const session=q.get('checkout_session_id')||q.get('session_id');
  if(session){status.classList.remove('hidden');status.textContent='Payment was completed, but automatic checkout verification requires the configured payment webhook. Use the paid access credential supplied by AAI.';}
})();
