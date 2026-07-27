// Professor Pre-create UI

const API_BASE = '/api/owner';

document.addEventListener('DOMContentLoaded', () => {
    loadOrganizations();
    
    document.getElementById('precreate-form').addEventListener('submit', handleFormSubmit);
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
        username: document.getElementById('username').value.trim(),
        name: document.getElementById('name').value.trim(),
        email: document.getElementById('email').value.trim().toLowerCase(),
        organization_id: document.getElementById('organization').value
    };
    
    try {
        const response = await fetch(`${API_BASE}/professors/pre-create`, {
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
        document.getElementById('precreate-form').classList.add('hidden');
        const resultDiv = document.getElementById('result');
        resultDiv.classList.remove('hidden');
        
        document.getElementById('precreated_username').textContent = data.username;
        document.getElementById('precreated_name').textContent = data.name;
        document.getElementById('precreated_email').textContent = data.email;
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}
