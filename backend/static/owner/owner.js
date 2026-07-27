// Practenture Owner Console
const API_BASE = '/api/owner';
const token = () => localStorage.getItem('token');
const state = {professors: [], invitations: [], auditEvents: []};
const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const when = (value) => value ? new Date(value).toLocaleString() : '—';

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: 'same-origin',
    headers: {...(options.body ? {'Content-Type':'application/json'} : {}), Authorization: `Bearer ${token()}`, ...(options.headers || {})}
  });
  const data = response.status === 204 ? {} : await response.json().catch(() => ({}));
  if (response.status === 401 || response.status === 403) {
    localStorage.removeItem('token');
    window.location.replace('/admin');
    throw new Error('Authentication required');
  }
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
  return data;
}
const get = path => api(path);
const post = (path, body={}) => api(path, {method:'POST', body:JSON.stringify(body)});

function notify(message, error=false) {
  let box = $('admin-notice');
  if (!box) { box=document.createElement('div'); box.id='admin-notice'; box.style.cssText='position:fixed;right:20px;bottom:20px;z-index:1000;padding:14px 18px;border-radius:8px;color:white;max-width:420px'; document.body.appendChild(box); }
  box.style.background=error?'#b91c1c':'#166534'; box.textContent=message; box.hidden=false;
  setTimeout(()=>box.hidden=true, 6000);
}
function modal(html) { $('modal-content').innerHTML=html; $('modal-overlay').classList.remove('hidden'); $('modal-content').classList.remove('hidden'); }
function closeModal() { $('modal-overlay').classList.add('hidden'); $('modal-content').classList.add('hidden'); }

async function loadOverview() {
  const [users, invitations, health, audit] = await Promise.all([get('/users?role=professor'),get('/professor-invitations'),get('/system/database-health'),get('/audit-events')]);
  $('total-professors').textContent=(users.users||[]).length;
  $('total-sessions').textContent=health.tableCounts?.sessions ?? 0;
  $('active-invitations').textContent=(invitations.invitations||[]).filter(x=>x.status==='active').length;
  $('database-health').textContent=health.status;
  $('recent-activity').innerHTML=(audit.events||[]).slice(0,10).map(e=>`<div class="activity-item"><span>${when(e.occurredAt)}</span> ${esc(e.action)} by ${esc(e.actorUserId||'system')}</div>`).join('')||'<p>No recent activity</p>';
}
async function loadProfessors() {
  const data=await get('/users?role=professor'); state.professors=data.users||[];
  $('professors-list').innerHTML=state.professors.map(p=>`<tr><td>${esc(p.username)}</td><td>${esc(p.name||'—')}</td><td>${esc(p.email||'—')}</td><td>${esc(p.status||'active')}</td><td>${when(p.createdAt)}</td><td>—</td><td><button class="btn btn-secondary" data-user="${esc(p.username)}">Manage</button></td></tr>`).join('')||'<tr><td colspan="7">No professors found</td></tr>';
  document.querySelectorAll('[data-user]').forEach(b=>b.onclick=()=>manageProfessor(b.dataset.user));
}
async function loadInvitations() {
  const data=await get('/professor-invitations'); state.invitations=data.invitations||[];
  $('invitations-list').innerHTML=state.invitations.map(i=>`<tr><td>${esc(i.maskedCode)}</td><td>${esc(i.intendedEmail)}</td><td>${esc(i.status)}</td><td>${when(i.expiresAt)}</td><td>${i.useCount}/${i.maxUses}</td><td>${esc(i.issuedBy||'—')}</td><td>${i.status==='active'?`<button class="btn btn-secondary" data-revoke="${esc(i.id)}">Revoke</button>`:'—'}</td></tr>`).join('')||'<tr><td colspan="7">No invitations found</td></tr>';
  document.querySelectorAll('[data-revoke]').forEach(b=>b.onclick=async()=>{if(confirm('Revoke this invitation?')){await post(`/professor-invitations/${encodeURIComponent(b.dataset.revoke)}/revoke`); notify('Invitation revoked'); loadInvitations();}});
}
async function loadOrganizations() {
  const invitations=state.invitations.length?state.invitations:(await get('/professor-invitations')).invitations||[];
  const ids=[...new Set(invitations.map(i=>i.organizationId).filter(Boolean))];
  $('organizations-list').innerHTML=ids.map(id=>`<tr><td>${esc(id)}</td><td>—</td><td>—</td><td>—</td></tr>`).join('')||'<tr><td colspan="4">No organizations found</td></tr>';
}
async function loadAuditEvents() {
  const data=await get('/audit-events'); state.auditEvents=data.events||[];
  $('audit-list').innerHTML=state.auditEvents.map(e=>`<tr><td>${when(e.occurredAt)}</td><td>${esc(e.actorUserId||'system')}</td><td>${esc(e.action)}</td><td>${esc(e.targetType||'—')}: ${esc(e.targetId||'—')}</td><td>${esc(e.outcome)}</td></tr>`).join('')||'<tr><td colspan="5">No audit events found</td></tr>';
}
function openInvitationForm() { modal(`<h2>Create Professor Invitation</h2><form id="invite-form"><label>Organization ID</label><input id="invite-org" required value="practenture"><label>Professor email</label><input id="invite-email" type="email" required><label>Notes</label><textarea id="invite-notes"></textarea><div class="modal-actions"><button class="btn btn-primary" type="submit">Create code</button><button class="btn btn-secondary" type="button" id="cancel-modal">Cancel</button></div></form>`); $('cancel-modal').onclick=closeModal; $('invite-form').onsubmit=createInvitation; }
async function createInvitation(e) { e.preventDefault(); try { const result=await post('/professor-invitations',{organizationId:$('invite-org').value.trim(),intendedEmail:$('invite-email').value.trim(),notes:$('invite-notes').value}); modal(`<h2>Invitation created</h2><p>Copy this code now. It is only displayed once.</p><pre style="white-space:pre-wrap;user-select:all">${esc(result.code)}</pre><button class="btn btn-primary" id="done-modal">Done</button>`); $('done-modal').onclick=()=>{closeModal();loadInvitations();}; notify('Invitation code created'); } catch(err){notify(err.message,true);} }
function openProfessorForm() { modal(`<h2>Create Professor</h2><form id="prof-form"><label>Username</label><input id="prof-user" required><label>Name</label><input id="prof-name" required><label>Email</label><input id="prof-email" type="email" required><label>University</label><input id="prof-university"><div class="modal-actions"><button class="btn btn-primary" type="submit">Create professor</button><button class="btn btn-secondary" type="button" id="cancel-modal">Cancel</button></div></form>`); $('cancel-modal').onclick=closeModal; $('prof-form').onsubmit=createProfessor; }
async function createProfessor(e) { e.preventDefault(); try { const r=await post('/professors/pre-create',{username:$('prof-user').value.trim(),name:$('prof-name').value.trim(),email:$('prof-email').value.trim(),universityName:$('prof-university').value.trim()}); modal(`<h2>Professor created</h2><p>Username: <strong>${esc(r.username)}</strong></p><p>Temporary password (show once):</p><pre style="user-select:all">${esc(r.temporaryPassword)}</pre><button class="btn btn-primary" id="done-modal">Done</button>`); $('done-modal').onclick=()=>{closeModal();loadProfessors();}; } catch(err){notify(err.message,true);} }
function manageProfessor(username) { modal(`<h2>Manage ${esc(username)}</h2><button class="btn btn-warning" id="reset-user">Require password reset</button> <button class="btn btn-danger" id="suspend-user">Suspend</button> <button class="btn btn-secondary" id="reactivate-user">Reactivate</button> <button class="btn" id="cancel-modal">Close</button>`); $('cancel-modal').onclick=closeModal; $('reset-user').onclick=()=>accountAction(username,'force-password-reset'); $('suspend-user').onclick=()=>accountAction(username,'suspend',{reason:'Owner console action'}); $('reactivate-user').onclick=()=>accountAction(username,'reactivate'); }
async function accountAction(user, action, body={}) { try { await post(`/users/${encodeURIComponent(user)}/${action}`,body); notify(`Account updated: ${action}`); closeModal(); loadProfessors(); } catch(err){notify(err.message,true);} }
async function navigate(view) { document.querySelectorAll('.view').forEach(v=>v.classList.toggle('active',v.id===view)); document.querySelectorAll('[data-nav]').forEach(a=>a.classList.toggle('active',a.dataset.nav===view)); const loaders={overview:loadOverview,professors:loadProfessors,invitations:loadInvitations,organizations:loadOrganizations,audit:loadAuditEvents}; try{await loaders[view]?.();}catch(e){notify(e.message,true);} }

document.addEventListener('DOMContentLoaded', async()=>{
  if(!token()){window.location.replace('/admin');return;}
  try { await get('/system/database-health'); } catch(e) { return; }
  document.querySelectorAll('[data-nav]').forEach(a=>a.addEventListener('click',e=>{e.preventDefault();navigate(a.dataset.nav);}));
  $('create-invitation-btn')?.addEventListener('click',openInvitationForm);
  $('create-professor-btn')?.addEventListener('click',openProfessorForm);
  $('modal-overlay')?.addEventListener('click',closeModal);
  $('logout-btn')?.addEventListener('click',async()=>{await post('/logout').catch(()=>{});localStorage.removeItem('token');window.location.replace('/admin');});
  navigate('overview');
});
