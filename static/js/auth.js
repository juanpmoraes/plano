function showTab(tab) {
    const tabs = document.querySelectorAll('.tab-btn');
    const forms = document.querySelectorAll('.auth-form');

    tabs.forEach(t => t.classList.remove('active'));
    forms.forEach(f => f.classList.remove('active'));

    event.target.classList.add('active');
    document.getElementById(tab + '-form').classList.add('active');
}

document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const email = document.getElementById('login-email').value;
    const senha = document.getElementById('login-senha').value;
    const messageDiv = document.getElementById('login-message');

    try {
        const response = await fetch('/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email, senha })
        });

        const data = await response.json();

        if (data.success) {
            messageDiv.className = 'message success';
            messageDiv.textContent = 'Login realizado! Redirecionando...';
            setTimeout(() => {
                window.location.href = data.redirect;
            }, 1000);
        } else {
            messageDiv.className = 'message error';
            messageDiv.textContent = data.message;
        }
    } catch (error) {
        messageDiv.className = 'message error';
        messageDiv.textContent = 'Erro ao fazer login. Tente novamente.';
    }
});

document.getElementById('register-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const nome = document.getElementById('register-nome').value;
    const email = document.getElementById('register-email').value;
    const senha = document.getElementById('register-senha').value;
    const messageDiv = document.getElementById('register-message');

    if (senha.length < 6) {
        messageDiv.className = 'message error';
        messageDiv.textContent = 'A senha deve ter no mínimo 6 caracteres';
        return;
    }

    try {
        const response = await fetch('/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ nome, email, senha })
        });

        const data = await response.json();

        if (data.success) {
            messageDiv.className = 'message success';
            messageDiv.textContent = data.message + ' Faça login para continuar.';
            setTimeout(() => {
                showTab('login');
                document.getElementById('login-email').value = email;
            }, 2000);
        } else {
            messageDiv.className = 'message error';
            messageDiv.textContent = data.message;
        }
    } catch (error) {
        messageDiv.className = 'message error';
        messageDiv.textContent = 'Erro ao criar conta. Tente novamente.';
    }
});