// Backup & Cleanup UI

const API_BASE = '/api/owner';

document.addEventListener('DOMContentLoaded', () => {
    loadOrganizations();
    loadBackupHistory();
    loadRestoreDrillHistory();
    
    document.getElementById('cleanup-form').addEventListener('submit', handleCleanupPreview);
    document.getElementById('execute-cleanup-btn').addEventListener('click', handleExecuteCleanup);
});

async function loadOrganizations() {
    try {
        const response = await fetch(`${API_BASE}/organizations`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
        });
        
        if (!response.ok) {
            throw new Error(`API error: ${response.statusText}`);
        }
        
        const data = await response.json();
        const organizations = data.organizations || [];
        
        const select = document.getElementById('organization-select');
        organizations.forEach(org => {
            const option = document.createElement('option');
            option.value = org.id;
            option.textContent = `${org.name} (${org.university_name || 'No university'})`;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading organizations:', error);
    }
}

async function loadBackupHistory() {
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
        
        // This would need a separate endpoint for full history
        const container = document.getElementById('backup-history');
        
        if (data.status === 'no_backups') {
            container.innerHTML = '<tr><td colspan="4" class="text-center">No backups found</td></tr>';
        } else {
            container.innerHTML = `
                <tr>
                    <td>${data.last_backup_id || 'N/A'}</td>
                    <td>${formatTime(data.last_backup_at)}</td>
                    <td><span class="health-status ${getStatusClass(data.status)}">${data.status}</span></td>
                    <td>${data.object_key || 'N/A'}</td>
                </tr>
            `;
        }
    } catch (error) {
        console.error('Error loading backup history:', error);
    }
}

async function loadRestoreDrillHistory() {
    try {
        // This would need a separate endpoint
        const container = document.getElementById('restore-drill-history');
        container.innerHTML = '<tr><td colspan="4" class="text-center">No restore drills found</td></tr>';
    } catch (error) {
        console.error('Error loading restore drill history:', error);
    }
}

async function handleCleanupPreview(e) {
    e.preventDefault();
    
    const formData = {
        organization_id: document.getElementById('organization-select').value,
        is_test: document.getElementById('is-test-checkbox').checked
    };
    
    try {
        const response = await fetch(`${API_BASE}/cleanup-plans`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify(formData)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || `API error: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        // Show preview
        document.getElementById('cleanup-preview').classList.remove('hidden');
        
        const list = document.getElementById('cleanup-preview-list');
        let html = '';
        
        if (data.preview && data.preview.table_counts) {
            Object.entries(data.preview.table_counts).forEach(([table, count]) => {
                html += `<li>${table}: ${count} rows</li>`;
            });
        }
        
        list.innerHTML = html;
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}

async function handleExecuteCleanup() {
    const confirmation = document.getElementById('cleanup-confirmation').value;
    
    if (confirmation !== 'DELETE TEST DATA') {
        alert('Confirmation phrase does not match');
        return;
    }
    
    // Get the plan ID from the preview
    const planId = document.getElementById('cleanup-preview').dataset.planId;
    
    if (!planId) {
        alert('No cleanup plan found');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/cleanup-plans/${planId}/execute`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify({ confirmation })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || `API error: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        alert(`Cleanup completed: ${data.rows_deleted} rows deleted`);
        
        // Hide preview
        document.getElementById('cleanup-preview').classList.add('hidden');
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}

function getStatusClass(status) {
    const classes = {
        'ok': 'ok',
        'healthy': 'ok',
        'warning': 'warning',
        'failed': 'danger'
    };
    
    return classes[status] || 'ok';
}

function formatTime(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString();
}
