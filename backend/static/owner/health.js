// System Health UI

const API_BASE = '/api/owner';

document.addEventListener('DOMContentLoaded', () => {
    loadHealthReport();
});

async function loadHealthReport() {
    try {
        const response = await fetch(`${API_BASE}/system/database-health`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
        });
        
        if (!response.ok) {
            throw new Error(`API error: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        // Render database health
        renderDatabaseHealth(data);
        
        // Render backup status
        await renderBackupStatus();
        
        // Render foreign key integrity
        renderForeignKeyIntegrity(data.relations || {});
        
        // Render domain invariants
        renderDomainInvariants(data.domain || {});
    } catch (error) {
        console.error('Error loading health report:', error);
        document.getElementById('database-health').innerHTML = '<p class="error">Error loading health report</p>';
    }
}

function renderDatabaseHealth(data) {
    const status = data.status || 'unknown';
    const statusClass = getStatusClass(status);
    
    let html = `
        <div class="health-status ${statusClass}">${status.toUpperCase()}</div>
        <p>Checked at: ${formatTime(data.checked_at)}</p>
    `;
    
    if (data.integrity) {
        html += `<p>Integrity: ${data.integrity.status}</p>`;
    }
    
    document.getElementById('database-health').innerHTML = html;
}

async function renderBackupStatus() {
    try {
        const response = await fetch(`${API_BASE}/system/backup-status`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
        });
        
        if (!response.ok) {
            throw new Error(`API error: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        let html = '';
        
        if (data.status === 'no_backups') {
            html = '<p>No backups found</p>';
        } else {
            const ageHours = Math.round(data.age_seconds / 3600);
            html = `
                <p>Status: ${data.status}</p>
                <p>Age: ${ageHours} hours</p>
                <p>Object Key: ${data.object_key}</p>
            `;
        }
        
        document.getElementById('backup-status').innerHTML = html;
    } catch (error) {
        console.error('Error loading backup status:', error);
        document.getElementById('backup-status').innerHTML = '<p>Error loading backup status</p>';
    }
}

function renderForeignKeyIntegrity(data) {
    const violations = data.violations || [];
    
    if (violations.length === 0) {
        document.getElementById('foreign-key-integrity').innerHTML = '<p class="ok">No violations found</p>';
        return;
    }
    
    let html = '<ul>';
    violations.forEach(v => {
        html += `<li>${v.table}.${v.foreign_key}: ${v.orphan_count} orphaned records</li>`;
    });
    html += '</ul>';
    
    document.getElementById('foreign-key-integrity').innerHTML = html;
}

function renderDomainInvariants(data) {
    const violations = data.violations || [];
    
    if (violations.length === 0) {
        document.getElementById('domain-invariants').innerHTML = '<p class="ok">All invariants satisfied</p>';
        return;
    }
    
    let html = '<ul>';
    violations.forEach(v => {
        html += `<li>${v.type}: ${v.count} records</li>`;
    });
    html += '</ul>';
    
    document.getElementById('domain-invariants').innerHTML = html;
}

function refreshHealth() {
    loadHealthReport();
}

function getStatusClass(status) {
    const classes = {
        'healthy': 'ok',
        'ok': 'ok',
        'warning': 'warning',
        'failed': 'danger'
    };
    
    return classes[status] || 'ok';
}

function formatTime(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString();
}
