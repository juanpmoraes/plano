async function loadUserInfo() {
    try {
        const response = await fetch('/api/user_info');
        const data = await response.json();
        if (data.success) {
            document.getElementById('user-name').textContent = data.nome;
            document.getElementById('user-email').textContent = data.email;
            const badges = document.querySelectorAll('#user-plano, #plano-atual');
            badges.forEach(b => {
                b.textContent = data.plano.toUpperCase();
                b.className = `badge ${data.plano}`;
            });
        }
    } catch(e) { console.error('Erro:', e); }
}
loadUserInfo();
