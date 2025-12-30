let planoSelecionado = null;

function selecionarPlano(plano) {
  planoSelecionado = plano;

  if (plano === "free") {
    confirmarCompraFree();
    return;
  }

  abrirCpfModal();
}

async function confirmarCompraFree() {
  if (!confirm("Ativar o plano FREE?")) return;

  const resp = await fetch("/criar_pagamento", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ plano: "free" }),
  });

  const data = await resp.json();
  if (data.success) window.location.href = "/dashboard";
  else alert(data.message || "Erro");
}

function abrirCpfModal() {
  document.getElementById("cpf-input").value = "";
  hideCpfError();
  document.getElementById("cpf-modal").style.display = "block";
  setTimeout(() => document.getElementById("cpf-input").focus(), 50);
}

function fecharCpfModal() {
  document.getElementById("cpf-modal").style.display = "none";
}

function abrirPixModal(qrBase64, qrString) {
  document.getElementById("pix-qr-img").src = "data:image/png;base64," + qrBase64;
  document.getElementById("pix-copy").value = qrString || "";
  document.getElementById("pix-modal").style.display = "block";
}

function fecharPixModal() {
  document.getElementById("pix-modal").style.display = "none";
}

function copiarPix() {
  const el = document.getElementById("pix-copy");
  el.select();
  el.setSelectionRange(0, 999999);
  document.execCommand("copy");
  alert("Código PIX copiado!");
}

function sanitizeCpf(cpf) {
  return (cpf || "").replace(/\D/g, "");
}

function formatCpf(value) {
  value = sanitizeCpf(value);
  value = value.replace(/(\d{3})(\d)/, "$1.$2");
  value = value.replace(/(\d{3})(\d)/, "$1.$2");
  value = value.replace(/(\d{3})(\d{1,2})$/, "$1-$2");
  return value;
}

// Validação completa (frontend)
function validarCpf(cpf) {
  cpf = sanitizeCpf(cpf);
  if (cpf.length !== 11) return false;
  if (/^(\d)\1{10}$/.test(cpf)) return false;

  let soma = 0;
  for (let i = 0; i < 9; i++) soma += parseInt(cpf[i]) * (10 - i);
  let resto = (soma * 10) % 11;
  if (resto === 10) resto = 0;
  if (resto !== parseInt(cpf[9])) return false;

  soma = 0;
  for (let i = 0; i < 10; i++) soma += parseInt(cpf[i]) * (11 - i);
  resto = (soma * 10) % 11;
  if (resto === 10) resto = 0;
  if (resto !== parseInt(cpf[10])) return false;

  return true;
}

function showCpfError(msg) {
  const el = document.getElementById("cpf-error");
  el.style.display = "block";
  el.textContent = msg;
}

function hideCpfError() {
  const el = document.getElementById("cpf-error");
  el.style.display = "none";
  el.textContent = "";
}

document.addEventListener("input", (e) => {
  if (e.target && e.target.id === "cpf-input") {
    e.target.value = formatCpf(e.target.value);
    hideCpfError();
  }
});

async function confirmarCompra() {
  const cpf = document.getElementById("cpf-input").value;

  if (!validarCpf(cpf)) {
    showCpfError("CPF inválido.");
    return;
  }

  fecharCpfModal();

  const resp = await fetch("/criar_pagamento", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ plano: planoSelecionado, cpf }),
  });

  const data = await resp.json();

  if (!data.success) {
    alert(data.message || "Erro ao gerar PIX.");
    return;
  }

  if (!data.qr_code || !data.qr_string) {
    alert("PIX gerado, mas sem QR retornado (verifique response do Mercado Pago).");
    return;
  }

  abrirPixModal(data.qr_code, data.qr_string);
  iniciarVerificacaoPix(data.pix_id);
}

let pollingTimer = null;

function mostrarSucesso(plano) {
  fecharPixModal();

  const modal = document.getElementById("success-modal");
  const txt = document.getElementById("success-plan-text");

  txt.textContent = `Seu novo plano: ${String(plano || "pro").toUpperCase()}`;
  modal.style.display = "block";
}

function iniciarVerificacaoPix(pixId) {
  if (pollingTimer) clearInterval(pollingTimer); // evita múltiplos intervals [web:324]

  pollingTimer = setInterval(async () => {
    try {
      const r = await fetch(`/verificar_pagamento/${pixId}`);
      const j = await r.json();

      if (j.success && j.status === "confirmado") {
        clearInterval(pollingTimer);
        pollingTimer = null;

        mostrarSucesso(j.plano);

        // Redireciona e o dashboard já mostra o plano atualizado
        setTimeout(() => (window.location.href = "/dashboard"), 2000);
      }
    } catch (e) {
      // ignora falhas temporárias
    }
  }, 4000);
}
