// Invitation Creation UI

const API_BASE = '/api/owner';

document.addEventListener('DOMContentLoaded', () => {
    loadOrganizations();
    
    document.getElementById('invitation-form').addEventListener('submit', handleFormSubmit);
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
        
        const select = document.getElementById('organization');
        organizations.forEach(org => {
            const option = document.createElement('option');
            option.value = org.id;
            option.textContent = `${org.name} (${org.university_name || 'No university'})`;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading organizations:', error);
        document.getElementById('organization').innerHTML = '<option>Error loading organizations</option>';
    }
}

async function handleFormSubmit(e) {
    e.preventDefault();
    
    const formData = {
        organization_id: document.getElementById('organization').value,
        intended_email: document.getElementById('intended_email').value.trim().toLowerCase(),
        expires_in_hours: parseInt(document.getElementById('expires_in_hours').value) || 48,
        max_uses: parseInt(document.getElementById('max_uses').value) || 1,
        notes: document.getElementById('notes').value.trim() || null
    };
    
    try {
        const response = await fetch(`${API_BASE}/professor-invitations`, {
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
        
        // Show result
        document.getElementById('invitation-form').classList.add('hidden');
        const resultDiv = document.getElementById('result');
        resultDiv.classList.remove('hidden');
        
        document.getElementById('invitation_code').textContent = data.secret || 'N/A';
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}
