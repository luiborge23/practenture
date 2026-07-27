// Owner Console Login JavaScript

const API_BASE = '/api/owner';

document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const errorMessage = document.getElementById('error-message');
    
    try {
        const response = await fetch(`${API_BASE}/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                provider: 'password',
                username: username,
                password: password
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Login failed');
        }
        
        const data = await response.json();
        
        // Store the token
        localStorage.setItem('token', data.accessToken);
        
        // Redirect to dashboard
        window.location.href = '/owner';
    } catch (error) {
        errorMessage.textContent = error.message || 'An error occurred during login';
    }
});
