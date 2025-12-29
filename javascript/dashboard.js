async function loadUserInfo() {
    try {
        const response = await fetch('/api/user_info');
        const data = await response.json();

        if (data.success) {
            document.getElementById('user-name').textContent = data.nome;
            document.getElementById('user-email').textContent = data.email;

            const planoBadges = document.querySelectorAll('#user-plano, #plano-atual');
            planoBadges.forEach(badge => {
                badge.textContent = data.plano.toUpperCase();
                badge.className = 'badge ' + data.plano;
            });
        }
    } catch (error) {
        console.error('Erro ao carregar informações:', error);
    }
}

loadUserInfo();