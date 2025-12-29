# Sistema de Assinatura com Pagamento PIX

Sistema completo de assinatura com autenticação, dashboard e pagamento via PIX.

## 🚀 Tecnologias

- **Backend**: Python + Flask
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla)
- **Banco de Dados**: MySQL (Square Cloud)
- **Pagamento**: PIX com QR Code

## 📋 Funcionalidades

- ✅ Sistema de login e registro
- ✅ Dashboard com informações do usuário
- ✅ 3 planos de assinatura (Gratuito, Pro, Premium)
- ✅ Pagamento via PIX com QR Code
- ✅ Verificação automática de pagamento
- ✅ Interface responsiva

## 🛠️ Configuração

### 1. Instalar Dependências

```bash
pip install -r requirements.txt
```

### 2. Configurar Banco de Dados MySQL no Square Cloud

Edite o arquivo `app.py` e configure suas credenciais MySQL:

```python
DB_CONFIG = {
    'host': 'seu-host.squarecloud.app',
    'user': 'seu_usuario',
    'password': 'sua_senha',
    'database': 'seu_banco',
    'port': 3306
}
```

### 3. Configurar Chave PIX

No arquivo `app.py`, na função `gerar_pix_qrcode()`, altere:

```python
chave_pix = "sua-chave-pix@banco.com"
merchant_name = "Seu Negócio"
merchant_city = "Sao Paulo"
```

### 4. Executar Aplicação

```bash
python app.py
```

A aplicação estará disponível em `http://localhost:5000`

## 📁 Estrutura do Projeto

```
project/
├── app.py                  # Backend Flask
├── requirements.txt        # Dependências Python
├── templates/
│   ├── login.html         # Página de login/registro
│   ├── dashboard.html     # Dashboard do usuário
│   └── planos.html        # Página de planos
├── static/
│   ├── css/
│   │   └── style.css      # Estilos CSS
│   └── js/
│       ├── auth.js        # Lógica de autenticação
│       ├── dashboard.js   # Lógica do dashboard
│       └── planos.js      # Lógica de planos e PIX
```

## 🗄️ Estrutura do Banco de Dados

### Tabela: usuarios
- `id` (INT, AUTO_INCREMENT, PRIMARY KEY)
- `nome` (VARCHAR(100))
- `email` (VARCHAR(100), UNIQUE)
- `senha` (VARCHAR(255))
- `plano` (VARCHAR(20), DEFAULT 'free')
- `data_cadastro` (TIMESTAMP)
- `ativo` (BOOLEAN)

### Tabela: pagamentos
- `id` (INT, AUTO_INCREMENT, PRIMARY KEY)
- `usuario_id` (INT, FOREIGN KEY)
- `plano` (VARCHAR(20))
- `valor` (DECIMAL(10,2))
- `pix_id` (VARCHAR(100), UNIQUE)
- `qr_code` (TEXT)
- `status` (VARCHAR(20), DEFAULT 'pendente')
- `data_criacao` (TIMESTAMP)
- `data_expiracao` (TIMESTAMP)

## 💰 Planos Disponíveis

### Gratuito
- Recurso básico
- 5 projetos
- Suporte por email
- **R$ 0,00/mês**

### Pro
- Todos recursos básicos
- 50 projetos
- Suporte prioritário
- API Access
- **R$ 29,90/mês**

### Premium
- Recursos ilimitados
- Projetos ilimitados
- Suporte 24/7
- API Access
- Relatórios avançados
- **R$ 79,90/mês**

## 🔒 Segurança

- Senhas criptografadas com SHA-256
- Sessões seguras com Flask
- Validação de dados no frontend e backend
- Proteção contra SQL Injection (usando parameterized queries)

## 🔄 Integração PIX

O sistema gera QR Codes PIX para pagamentos. Em produção, você deve:

1. **Integrar com API do seu banco** (Ex: Banco Inter, Itaú, etc.)
2. **Ou usar gateway de pagamento** (Ex: Mercado Pago, PagSeguro)
3. **Implementar webhook** para confirmação automática de pagamentos

### Exemplo de APIs PIX recomendadas:
- Mercado Pago API
- Cielo API PIX
- Banco Inter API
- PagSeguro PIX

## 📱 Deploy

### Opção 1: Square Cloud
1. Crie uma conta no Square Cloud
2. Configure o banco de dados MySQL
3. Faça upload dos arquivos
4. Configure as variáveis de ambiente
5. Inicie a aplicação

### Opção 2: Heroku
1. Instale Heroku CLI
2. Crie app: `heroku create nome-do-app`
3. Configure MySQL: `heroku addons:create cleardb:ignite`
4. Deploy: `git push heroku main`

### Opção 3: VPS (Digital Ocean, AWS, etc.)
1. Configure servidor com Python 3.8+
2. Instale dependências
3. Configure Nginx + Gunicorn
4. Configure SSL (Let's Encrypt)

## 🐛 Solução de Problemas

### Erro de conexão MySQL
- Verifique credenciais no `DB_CONFIG`
- Confirme se o IP está liberado no firewall do Square Cloud
- Teste conexão com MySQL Workbench

### QR Code não aparece
- Verifique se a biblioteca `qrcode` está instalada
- Confirme que o Pillow está instalado corretamente

### Sessão expira rápido
- Aumente `PERMANENT_SESSION_LIFETIME` no Flask
- Configure cookies seguros em produção

## 📝 Próximos Passos

- [ ] Integrar API real de pagamento PIX
- [ ] Implementar webhook para confirmação automática
- [ ] Adicionar recuperação de senha
- [ ] Implementar 2FA (autenticação de dois fatores)
- [ ] Dashboard com mais estatísticas
- [ ] Sistema de cancelamento de assinatura
- [ ] Histórico de pagamentos
- [ ] Notificações por email

## 📄 Licença

Este projeto é livre para uso pessoal e comercial.

## 👨‍💻 Desenvolvedor

Desenvolvido com 💜 em São Paulo, Brasil

## 🆘 Suporte

Para dúvidas ou problemas, abra uma issue no GitHub.
