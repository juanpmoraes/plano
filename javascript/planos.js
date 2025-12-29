let pixCheckInterval;

async function selecionarPlano(plano) {
    if (plano === 'free') {
        if (confirm('Deseja ativar o plano gratuito?')) {
            try {
                const response = await fetch('/criar_pagamento', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ plano })
                });

                const data = await response.json();

                if (data.success) {
                    alert('Plano gratuito ativado com sucesso!');
                    window.location.href = '/dashboard';
                }
            } catch (error) {
                alert('Erro ao ativar plano. Tente novamente.');
            }
        }
        return;
    }

    try {
        const response = await fetch('/criar_pagamento', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ plano })
        });

        const data = await response.json();

        if (data.success) {
            mostrarModalPix(data);
        } else {
            alert(data.message);
        }
    } catch (error) {
        alert('Erro ao criar pagamento. Tente novamente.');
    }
}

function mostrarModalPix(data) {
    const modal = document.getElementById('pix-modal');
    const qrCodeImg = document.getElementById('qr-code-img');
    const valorPagamento = document.getElementById('valor-pagamento');
    const pixCodeText = document.getElementById('pix-code-text');

    qrCodeImg.src = 'data:image/png;base64,' + data.qr_code;
    valorPagamento.textContent = data.valor.toFixed(2);
    pixCodeText.value = data.pix_id;

    modal.style.display = 'block';

    pixCheckInterval = setInterval(() => {
        verificarPagamento(data.pix_id);
    }, 5000);
}

async function verificarPagamento(pixId) {
    try {
        const response = await fetch('/verificar_pagamento/' + pixId);
        const data = await response.json();

        if (data.success && data.status === 'confirmado') {
            clearInterval(pixCheckInterval);
            alert('Pagamento confirmado! Seu plano foi ativado.');
            window.location.href = '/dashboard';
        }
    } catch (error) {
        console.error('Erro ao verificar pagamento:', error);
    }
}

function fecharModal() {
    const modal = document.getElementById('pix-modal');
    modal.style.display = 'none';
    clearInterval(pixCheckInterval);
}

function copiarPix() {
    const pixCode = document.getElementById('pix-code-text');
    pixCode.select();
    document.execCommand('copy');
    alert('Código PIX copiado!');
}

window.onclick = function(event) {
    const modal = document.getElementById('pix-modal');
    if (event.target === modal) {
        fecharModal();
    }
}