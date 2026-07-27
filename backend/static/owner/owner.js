// Owner Console JavaScript

const API_BASE = '/api/owner';

// ── State Management ─────────────────────────────────────────────────────────

const state = {
    currentUser: null,
    currentView: 'overview',
    professors: [],
    invitations: [],
    organizations: [],
    auditEvents: []
};

// ── DOM Elements ─────────────────────────────────────────────────────────────

const elements = {
    views: document.querySelectorAll('.view'),
    navLinks: document.querySelectorAll('[data-nav]'),
    modalOverlay: document.getElementById('modal-overlay'),
    modalContent: document.getElementById('modal-content')
};

// ── Navigation ───────────────────────────────────────────────────────────────

function navigate(view) {
    // Hide all views
    elements.views.forEach(v => v.classList.remove('active'));
    
    // Show selected view
    const selectedView = document.getElementById(view);
    if (selectedView) {
        selectedView.classList.add('active');
    }
    
    // Update nav links
    elements.navLinks.forEach(link => {
        link.classList.remove('active');
        if (link.dataset.nav === view) {
            link.classList.add('active');
        }
    });
    
    state.currentView = view;
    
    // Load data for the view
    if (view === 'overview') loadOverview();
    if (view === 'professors') loadProfessors();
    if (view === 'invitations') loadInvitations();
    if (view === 'organizations') loadOrganizations();
    if (view === 'audit') loadAuditEvents();
}

// ── API Calls ────────────────────────────────────────────────────────────────

async function apiGet(endpoint) {
    const response = await fetch(`${API_BASE}${endpoint}`, {
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
    });
    
    if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
    }
    
    return await response.json();
}

async function apiPost(endpoint, data) {
    const response = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(data)
    });
    
    if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
    }
    
    return await response.json();
}

// ── Overview Section ─────────────────────────────────────────────────────────

async function loadOverview() {
    try {
        // Load summary stats
        const professors = await apiGet('/users?role=professor');
        document.getElementById('total-professors').textContent = professors.count || 0;
        
        const sessions = await apiGet('/sessions');
        document.getElementById('total-sessions').textContent = sessions.count || 0;
        
        const invitations = await apiGet('/professor-invitations?status=active');
        document.getElementById('active-invitations').textContent = invitations.count || 0;
        
        // Load database health
        const health = await apiGet('/system/database-health');
        document.getElementById('database-health').textContent = health.status || 'unknown';
        
        // Load recent activity
        const audit = await apiGet('/audit-events?limit=10');
        renderRecentActivity(audit.events || []);
    } catch (error) {
        console.error('Error loading overview:', error);
    }
}

function renderRecentActivity(events) {
    const container = document.getElementById('recent-activity');
    
    if (events.length === 0) {
        container.innerHTML = '<p class="text-muted">No recent activity</p>';
        return;
    }
    
    container.innerHTML = events.map(event => `
        <div class="activity-item">
            <span class="activity-time">${formatTime(event.occurred_at)}</span>
            <span class="activity-action">${event.action}</span>
            by ${event.actor_user_id}
        </div>
    `).join('');
}

function formatTime(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString();
}

// ── Professors Section ───────────────────────────────────────────────────────

async function loadProfessors() {
    try {
        const response = await apiGet('/users?role=professor');
        state.professors = response.users || [];
        
        renderProfessors();
    } catch (error) {
        console.error('Error loading professors:', error);
    }
}

function renderProfessors() {
    const container = document.getElementById('professors-list');
    
    if (state.professors.length === 0) {
        container.innerHTML = '<tr><td colspan="7" class="text-center">No professors found</td></tr>';
        return;
    }
    
    container.innerHTML = state.professors.map(p => `
        <tr>
            <td>${p.username}</td>
            <td>${p.name || '-'}</td>
            <td>${p.email || '-'}</td>
            <td><span class="health-status ${getStatusClass(p.status)}">${p.status}</span></td>
            <td>${p.created_by || '-'}</td>
            <td>${formatTime(p.last_login_at) || 'Never'}</td>
            <td>
                <button class="btn btn-secondary" onclick="showProfessorModal('${p.username}')">Manage</button>
            </td>
        </tr>
    `).join('');
}

function getStatusClass(status) {
    const classes = {
        'active': 'ok',
        'pending': 'warning',
        'suspended': 'danger',
        'disabled': 'danger'
    };
    
    return classes[status] || 'ok';
}

// ── Invitations Section ──────────────────────────────────────────────────────

async function loadInvitations() {
    try {
        const response = await apiGet('/professor-invitations');
        state.invitations = response.invitations || [];
        
        renderInvitations();
    } catch (error) {
        console.error('Error loading invitations:', error);
    }
}

function renderInvitations() {
    const container = document.getElementById('invitations-list');
    
    if (state.invitations.length === 0) {
        container.innerHTML = '<tr><td colspan="7" class="text-center">No invitations found</td></tr>';
        return;
    }
    
    container.innerHTML = state.invitations.map(i => `
        <tr>
            <td>${i.masked_code}</td>
            <td>${i.intended_email}</td>
            <td><span class="health-status ${getInvitationStatusClass(i.status)}">${i.status}</span></td>
            <td>${formatTime(i.expires_at)}</td>
            <td>${i.use_count}/${i.max_uses}</td>
            <td>${i.issued_by || '-'}</td>
            <td>
                <button class="btn btn-secondary" onclick="showInvitationModal('${i.id}')">Manage</button>
            </td>
        </tr>
    `).join('');
}

function getInvitationStatusClass(status) {
    const classes = {
        'active': 'ok',
        'revoked': 'danger',
        'consumed': 'warning'
    };
    
    return classes[status] || 'ok';
}

// ── Organizations Section ────────────────────────────────────────────────────

async function loadOrganizations() {
    try {
        const response = await apiGet('/organizations');
        state.organizations = response.organizations || [];
        
        renderOrganizations();
    } catch (error) {
        console.error('Error loading organizations:', error);
    }
}

function renderOrganizations() {
    const container = document.getElementById('organizations-list');
    
    if (state.organizations.length === 0) {
        container.innerHTML = '<tr><td colspan="4" class="text-center">No organizations found</td></tr>';
        return;
    }
    
    container.innerHTML = state.organizations.map(o => `
        <tr>
            <td>${o.name}</td>
            <td>${o.university_name || '-'}</td>
            <td>${o.created_by || '-'}</td>
            <td>${formatTime(o.created_at)}</td>
        </tr>
    `).join('');
}

// ── Audit Section ────────────────────────────────────────────────────────────

async function loadAuditEvents() {
    try {
        const response = await apiGet('/audit-events');
        state.auditEvents = response.events || [];
        
        renderAuditEvents();
    } catch (error) {
        console.error('Error loading audit events:', error);
    }
}

function renderAuditEvents() {
    const container = document.getElementById('audit-list');
    
    if (state.auditEvents.length === 0) {
        container.innerHTML = '<tr><td colspan="5" class="text-center">No audit events found</td></tr>';
        return;
    }
    
    container.innerHTML = state.auditEvents.map(e => `
        <tr>
            <td>${formatTime(e.occurred_at)}</td>
            <td>${e.actor_user_id}</td>
            <td>${e.action}</td>
            <td>${e.target_type || '-'}: ${e.target_id || '-'}</td>
            <td><span class="health-status ${getOutcomeClass(e.outcome)}">${e.outcome}</span></td>
        </tr>
    `).join('');
}

function getOutcomeClass(outcome) {
    const classes = {
        'success': 'ok',
        'failure': 'danger'
    };
    
    return classes[outcome] || 'warning';
}

// ── Modal Functions ──────────────────────────────────────────────────────────

function showModal(content) {
    elements.modalContent.innerHTML = content;
    elements.modalOverlay.classList.remove('hidden');
}

function hideModal() {
    elements.modalOverlay.classList.add('hidden');
    elements.modalContent.innerHTML = '';
}

// ── Event Listeners ──────────────────────────────────────────────────────────

async function checkAuth() {
    const token = localStorage.getItem('token');
    if (!token) {
        window.location.href = '/owner/login';
        return false;
    }
    
    // Verify token is valid
    try {
        const response = await fetch(`${API_BASE}/system/database-health`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) {
            localStorage.removeItem('token');
            window.location.href = '/owner/login';
            return false;
        }
        
        return true;
    } catch (error) {
        localStorage.removeItem('token');
        window.location.href = '/owner/login';
        return false;
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    // Check authentication
    const authenticated = await checkAuth();
    if (!authenticated) return;
    
    // Navigation
    elements.navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            navigate(link.dataset.nav);
        });
    });
    
    // Logout
    document.getElementById('logout-btn').addEventListener('click', () => {
        localStorage.removeItem('token');
        window.location.href = '/owner/login';
    });
    
    // Initial load
    navigate('overview');
});

// ── Global Functions for HTML onclick ────────────────────────────────────────

window.showProfessorModal = function(username) {
    showModal(`<h2>Manage Professor: ${username}</h2>
        <p>Actions:</p>
        <ul>
            <li>Suspend account</li>
            <li>Reactivate account</li>
            <li>Force password reset</li>
        </ul>
        <button class="btn btn-secondary" onclick="hideModal()">Close</button>`);
};

window.showInvitationModal = function(invitationId) {
    showModal(`<h2>Manage Invitation: ${invitationId}</h2>
        <p>Actions:</p>
        <ul>
            <li>Revoke invitation</li>
            <li>View redemption history</li>
        </ul>
        <button class="btn btn-secondary" onclick="hideModal()">Close</button>`);
};
