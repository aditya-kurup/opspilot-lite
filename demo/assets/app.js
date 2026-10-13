const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let state = {requests:[],audit:[],messages:[]};
let busy = false;
const actorNames = {U_APPROVER:'Morgan',U_REQUESTER:'Alex',U_VISITOR:'Visitor',cleanup:'Cleanup worker'};
const labels = {pending:'Awaiting approval',executing:'Executing',provisioned:'Provisioned plan',rejected:'Rejected',failed:'Failed',deleting:'Deleting',deleted:'Deleted',cleanup_failed:'Cleanup failed'};
const shortTime = date => new Date(date).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});
function auditResult(result) {
  if (!result) return '';
  try { const parsed=JSON.parse(result);return parsed.bucket ? 'Dry-run plan: '+parsed.bucket : result; }
  catch { return result; }
}
function notice(message, error = false) { $('notice').hidden = false; $('notice').textContent = message; $('notice').className = error ? 'error' : ''; }
async function call(path, data) {
  const response = await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const result = await response.json();
  if (!response.ok) throw Error(result.error || 'Request failed.');
  return result;
}
function renderRequests(requests) {
  if (!requests.length) return '<div class="empty"><span>◇</span>No requests here yet.<small>Send a request or choose a different filter.</small></div>';
  return requests.map(r => '<div class="request"><div class="request-top"><div class="request-name"><span class="resource-icon">▣</span>'+esc(r.name)+'</div><span class="status '+esc(r.status)+'">'+esc(labels[r.status] || r.status)+'</span></div><div class="request-details"><span>'+esc(r.env)+' environment</span><span>◷ '+esc(r.ttl_hours)+' hours</span><span>Alex · '+esc(r.request_id.slice(0,8))+'</span></div>'+(r.bucket?'<div class="bucket">'+esc(r.bucket)+'<br><span class="expiry">Dry run · expires '+esc(new Date(r.ttl_expiry).toLocaleString())+'</span></div>':'')+(r.status === 'pending'?'<div class="request-actions"><button class="primary" data-id="'+esc(r.request_id)+'" data-decision="approve">Approve plan</button><button class="secondary danger" data-id="'+esc(r.request_id)+'" data-decision="reject">Reject</button></div>':'')+'</div>').join('');
}
function renderAudit(entries) {
  if (!entries.length) return '<div class="empty"><span>≡</span>No activity yet.<small>Recorded state changes will appear here.</small></div>';
  return entries.map(a => '<div class="audit-item"><span class="audit-icon">'+(a.status==='rejected'||a.status.includes('failed')?'×':a.status==='pending'?'◷':'✓')+'</span><div class="audit-info"><div class="audit-title"><span>'+esc(labels[a.status] || a.status)+'</span><time datetime="'+esc(a.timestamp)+'">'+esc(shortTime(a.timestamp))+'</time></div><div class="audit-detail">'+esc(actorNames[a.actor] || a.actor)+' · request '+esc(a.request_id.slice(0,8))+(a.result?'<br>'+esc(auditResult(a.result)):'')+'</div></div></div>').join('');
}
function render() {
  const requests=state.requests;
  const pending=requests.filter(r=>r.status==='pending').length;
  $('total').textContent=requests.length;
  $('pending').textContent=pending;
  $('provisioned').textContent=requests.filter(r=>r.status==='provisioned').length;
  $('queue-count').textContent=pending;
  $('nav-count').textContent=pending;
  const filter=$('filter').value;
  $('requests').innerHTML=renderRequests(requests.filter(r=>filter==='all'||r.status===filter));
  $('request-history').innerHTML=renderRequests(requests);
  $('recent-audit').innerHTML=renderAudit(state.audit.slice(0,4));
  $('audit-log').innerHTML=renderAudit(state.audit);
}
async function refresh() {
  const response=await fetch('/api/state',{cache:'no-store'});
  if (!response.ok) throw Error('Unable to load the workspace.');
  state=await response.json();render();
  $('connection').textContent='Local demo online';
  $('updated').textContent='Updated '+shortTime(new Date());
}
const views = {overview:['Provision with confidence.','Temporary infrastructure. Explicit approval. A traceable lifecycle.'],requests:['Every request, accounted for.','Review the complete resource request history in this workspace.'],audit:['A record of every transition.','See who acted, what changed, and the recorded outcome.'],controls:['Clear boundaries. Safer actions.','The controls behind the provisioning workflow.']};
document.querySelectorAll('[data-view]').forEach(button=>button.addEventListener('click',()=>{
  const view=button.dataset.view;
  for (const key of Object.keys(views)) $(key+'-view').hidden=key!==view;
  document.querySelectorAll('.nav').forEach(item=>{item.classList.toggle('active',item.dataset.view===view);if(item.dataset.view===view)item.setAttribute('aria-current','page');else item.removeAttribute('aria-current');});
  $('page-title').textContent=views[view][0];$('page-subtitle').textContent=views[view][1];$('view-title').textContent=view==='controls'?'Guardrails':view==='audit'?'Audit log':view[0].toUpperCase()+view.slice(1);
}));
document.querySelectorAll('[data-example]').forEach(button=>button.addEventListener('click',()=>{$('request').value=button.dataset.example;$('request').focus();$('notice').hidden=true;}));
$('actor').addEventListener('change',()=>{$('identity-description').textContent={U_APPROVER:'You can approve or reject Alex’s requests.',U_REQUESTER:'Alex requested these resources. Self-approval will be refused.',U_VISITOR:'Visitor is outside the approver allowlist. Decisions will be refused.'}[$('actor').value];});
$('filter').addEventListener('change',render);
$('submit').addEventListener('click',async()=>{
  if(busy)return;
  if(!$('request').value.trim()){notice('Describe the bucket, environment, and lifetime before submitting.',true);return;}
  busy=true;$('submit').disabled=true;notice('Validating your request…');
  try {
    const before=state.requests.length;
    await call('/api/request',{text:$('request').value});await refresh();
    const message=state.messages.at(-1);
    if(state.requests.length>before){$('filter').value='all';render();notice('Plan validated. Your request is waiting for a separate authorized approver.');}
    else notice(message?.type==='ephemeral'?message.text:'The request could not be validated. Please check the environment and lifetime.',true);
  }catch(error){notice(error.message,true);}finally{busy=false;$('submit').disabled=false;}
});
async function decide(event) {
  const button=event.target.closest('button[data-decision]');if(!button||busy)return;
  busy=true;button.disabled=true;
  try{const result=await call('/api/decision',{request_id:button.dataset.id,decision:button.dataset.decision,actor:$('actor').value});notice(result.message,result.message.includes('not authorized'));await refresh();}
  catch(error){notice(error.message,true);}finally{busy=false;button.disabled=false;}
}
$('requests').addEventListener('click',decide);$('request-history').addEventListener('click',decide);
$('refresh').addEventListener('click',()=>refresh().catch(error=>notice(error.message,true)));
$('reset').addEventListener('click',async()=>{
  if(busy||!window.confirm('Clear all local demo requests and audit entries?'))return;
  busy=true;$('reset').disabled=true;
  try{await call('/api/reset',{});$('filter').value='all';$('request').value='Create a dev bucket named campus-demo for 2 hours';await refresh();notice('Demo data cleared. The workflow is ready to record from the beginning.');}
  catch(error){notice(error.message,true);}finally{busy=false;$('reset').disabled=false;}
});
$('date').textContent=new Date().toLocaleDateString('en-IN',{weekday:'short',day:'numeric',month:'short'});
refresh().catch(error=>{notice(error.message,true);$('connection').textContent='Connection unavailable';});
setInterval(()=>{if(!busy)refresh().catch(()=>{$('connection').textContent='Connection unavailable';});},10000);
