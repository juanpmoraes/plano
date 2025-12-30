from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error
import hashlib
import secrets
from datetime import datetime, timedelta
import io
import base64
import uuid
import mercadopago  # ✅ PIX REAL
import qrcode  # ✅ Para QR Code
import os
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "jpbot.squareweb.app/webhook")

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
CORS(app)

# Configuração do MySQL no Square Cloud
DB_CONFIG = {
    'host': 'square-cloud-db-45ee9918389d44b3937fdb8e41f83048.squareweb.app',
    'user': 'squarecloud',
    'password': 'INNbhFE8vqhXzKTHUHLhLFWk',
    'port': 7102
}

# ✅ CONFIGURAÇÕES MERCADO PAGO (TESTE OK!)
# MERCADO_PAGO_ACCESS_TOKEN = "TEST-3798369418143337-122920-0cd50359605c7346d17426cef3ea0d31-496902134"
# MERCADO_PAGO_PUBLIC_KEY = "TEST-a90e5029-325b-471a-a380-e5ac5cbcc8a8"

# ✅ CONFIGURAÇÕES MERCADO PAGO (TESTE OK!)
MERCADO_PAGO_ACCESS_TOKEN = "APP_USR-5510745273548389-122922-053d1050455391a02eece2b5052a1b08-496902134"
MERCADO_PAGO_PUBLIC_KEY = "APP_USR-cd6283c6-f89b-4f57-94d3-a9d68b174a8a"

# Planos disponíveis
PLANOS = {
    'free': {'nome': 'Gratuito', 'preco': 0.00, 'recursos': ['Recurso básico', '5 projetos', 'Suporte por email']},
    'pro': {'nome': 'Pro', 'preco': 29.90, 'recursos': ['Todos recursos básicos', '50 projetos', 'Suporte prioritário', 'API Access']},
    'premium': {'nome': 'Premium', 'preco': 79.90, 'recursos': ['Recursos ilimitados', 'Projetos ilimitados', 'Suporte 24/7', 'API Access', 'Relatórios avançados']}
}

def ensure_column(cursor, table, column, ddl):
    cursor.execute(f"SHOW COLUMNS FROM {table} LIKE %s", (column,))
    if not cursor.fetchone():
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")
        print(f"✅ Coluna {table}.{column} adicionada")

def sanitize_cpf(cpf: str) -> str:
    if not cpf:
        return ""
    return "".join(ch for ch in str(cpf) if ch.isdigit())

def is_cpf_basic_valid(cpf_digits: str) -> bool:
    # validação mínima server-side
    if len(cpf_digits) != 11:
        return False
    if cpf_digits == cpf_digits[0] * 11:
        return False
    return True


def get_db_connection(database=None):
    """Conecta ao banco de dados MySQL"""
    config = DB_CONFIG.copy()
    if database:
        config['database'] = database
    try:
        connection = mysql.connector.connect(**config)
        return connection
    except Error as e:
        print(f"Erro ao conectar ao MySQL: {e}")
        return None

def create_database():
    """Cria a database se não existir"""
    print("🔄 Verificando se database 'sistema_assinaturas' existe...")
    
    conn = get_db_connection()
    if not conn:
        print("❌ Falha na conexão com o servidor MySQL")
        return False
    
    cursor = conn.cursor()
    cursor.execute("SHOW DATABASES LIKE 'sistema_assinaturas'")
    db_exists = cursor.fetchone()
    
    if not db_exists:
        print("📦 Criando database 'sistema_assinaturas'...")
        cursor.execute("CREATE DATABASE IF NOT EXISTS sistema_assinaturas")
        conn.commit()
        print("✅ Database 'sistema_assinaturas' criada com sucesso!")
    else:
        print("✅ Database 'sistema_assinaturas' já existe!")
    
    cursor.close()
    conn.close()
    return True

def init_database():
    """Inicializa as tabelas do banco de dados COM VERIFICAÇÃO DE COLUNAS"""
    print("🛠️ Inicializando tabelas...")
    
    if not create_database():
        print("❌ Falha ao criar database")
        return
    
    conn = get_db_connection('sistema_assinaturas')
    if not conn:
        print("❌ Falha ao conectar na database")
        return
    
    cursor = conn.cursor()
    
    # Tabela de usuários
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nome VARCHAR(100) NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            senha VARCHAR(255) NOT NULL,
            plano VARCHAR(20) DEFAULT 'free',
            data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ativo BOOLEAN DEFAULT TRUE,
            INDEX idx_email (email),
            INDEX idx_plano (plano)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    
    # Tabela de pagamentos (COMPLETA)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pagamentos (
            id INT AUTO_INCREMENT PRIMARY KEY,
            usuario_id INT NOT NULL,
            plano VARCHAR(20) NOT NULL,
            valor DECIMAL(10,2) NOT NULL,
            pix_id VARCHAR(100) UNIQUE NOT NULL,
            mp_payment_id VARCHAR(100),
            qr_code TEXT,
            qr_string TEXT,
            status VARCHAR(20) DEFAULT 'pendente',
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            data_expiracao TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            INDEX idx_usuario (usuario_id),
            INDEX idx_status (status),
            INDEX idx_pix (pix_id),
            INDEX idx_mp (mp_payment_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    ensure_column(cursor, "usuarios", "cpf", "cpf VARCHAR(11) NULL")
    ensure_column(cursor, "pagamentos", "cpf", "cpf VARCHAR(11) NULL")
    
    # ✅ VERIFICAR E ADICIONAR COLUNAS SE FALTAREM
    cursor.execute("SHOW COLUMNS FROM pagamentos LIKE 'mp_payment_id'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE pagamentos ADD COLUMN mp_payment_id VARCHAR(100)")
        print("✅ Coluna mp_payment_id adicionada")
    
    cursor.execute("SHOW COLUMNS FROM pagamentos LIKE 'qr_string'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE pagamentos ADD COLUMN qr_string TEXT")
        print("✅ Coluna qr_string adicionada")
    
    # Usuário de teste
    cursor.execute("SELECT COUNT(*) FROM usuarios WHERE email = 'teste@email.com'")
    if cursor.fetchone()[0] == 0:
        senha_teste = hashlib.sha256("teste123".encode()).hexdigest()
        cursor.execute(
            "INSERT INTO usuarios (nome, email, senha, plano) VALUES (%s, %s, %s, %s)",
            ("Usuário Teste", "teste@email.com", senha_teste, "free")
        )
        print("👤 Usuário de teste criado: teste@email.com / teste123")
    
    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Banco de dados inicializado completamente!")

def hash_password(password):
    """Hash de senha usando SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def gerar_pix_qrcode(valor, usuario_id, plano, cpf_digits):
    """✅ GERA PIX REAL com Mercado Pago (CPF dentro de payer.identification)"""
    try:
        print(f"💳 Criando PIX Mercado Pago: R${valor} - Plano {plano}")

        sdk = mercadopago.SDK(MERCADO_PAGO_ACCESS_TOKEN)

        # ✅ NÃO existe "identification" no nível raiz.
        # ✅ CPF deve ir em payer.identification (type/number).
        payment_data = {
            "transaction_amount": float(valor),
            "payment_method_id": "pix",
            "description": f"Assinatura JPBOT - {PLANOS[plano]['nome']}",
            "external_reference": f"{session['user_id']}_{plano}_{int(datetime.now().timestamp())}",

            # ✅ AQUI (mesmo nível de transaction_amount/payer)
            "notification_url": WEBHOOK_URL,

            "payer": {
                "email": session.get("user_email", "cliente@exemplo.com"),
                "first_name": session.get("user_name", "Cliente"),
                "last_name": "JPBOT",
                "identification": {
                    "type": "CPF",
                    "number": cpf_digits
                }
            }
        }

        # Debug durante testes
        print("➡️ payment_data =", payment_data)

        response = sdk.payment().create(payment_data)
        payment = response.get("response", {})

        # Se a API devolveu erro no body
        if isinstance(payment.get("status"), int) and payment.get("status") >= 400:
            print(f"❌ Mercado Pago ERROR BODY: {payment}")
            return {"success": False, "error": payment.get("message", "Erro Mercado Pago"), "details": payment}

        status = payment.get("status")
        print(f"📋 Mercado Pago Response status: {status}")

        if status != "pending":
            print(f"❌ Resposta inesperada: {payment}")
            return {
                "success": False,
                "error": f"Pagamento não ficou pendente: {payment.get('status_detail', status)}",
                "details": payment
            }

        pix_id = str(payment["id"])
        qr_data = None
        qr_string = None

        # Pega dados do PIX
        poi = payment.get("point_of_interaction") or {}
        tx = poi.get("transaction_data") or {}
        qr_string = tx.get("qr_code")
        qr_base64 = tx.get("qr_code_base64")

        # Se vier base64 do MP, usa direto; se não, gera imagem a partir do "copia e cola"
        if qr_base64:
            qr_data = qr_base64
        elif qr_string:
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(qr_string)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            qr_data = base64.b64encode(buffered.getvalue()).decode()

        # Salvar no banco (incluindo cpf)
        conn = get_db_connection("sistema_assinaturas")
        if conn:
            cursor = conn.cursor()
            data_expiracao = datetime.now() + timedelta(hours=1)
            cursor.execute(
                """INSERT INTO pagamentos
                   (usuario_id, plano, valor, pix_id, mp_payment_id, qr_code, qr_string, cpf, status, data_expiracao)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (usuario_id, plano, valor, pix_id, str(payment["id"]), qr_data, qr_string, cpf_digits, "pendente", data_expiracao)
            )
            conn.commit()
            cursor.close()
            conn.close()
            print(f"✅ PIX salvo no banco: ID {pix_id}")

        return {
            "success": True,
            "pix_id": pix_id,
            "qr_code": qr_data,
            "qr_string": qr_string,
            "valor": float(valor),
            "plano": plano,
            "payment_id": payment["id"]
        }

    except Exception as e:
        print(f"❌ Erro Mercado Pago: {e}")
        return {"success": False, "error": str(e)}


# Rotas (todas iguais)
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        email = data.get('email')
        senha = hash_password(data.get('senha'))
        
        conn = get_db_connection('sistema_assinaturas')
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM usuarios WHERE email = %s AND senha = %s", (email, senha))
            usuario = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if usuario:
                session['user_id'] = usuario['id']
                session['user_name'] = usuario['nome']
                session['user_email'] = usuario['email']
                session['user_plano'] = usuario['plano']
                return jsonify({'success': True, 'redirect': '/dashboard'})
            else:
                return jsonify({'success': False, 'message': 'Email ou senha incorretos'})
    
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    nome = data.get('nome')
    email = data.get('email')
    senha = hash_password(data.get('senha'))
    
    conn = get_db_connection('sistema_assinaturas')
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO usuarios (nome, email, senha, plano) VALUES (%s, %s, %s, %s)",
                (nome, email, senha, 'free')
            )
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({'success': True, 'message': 'Cadastro realizado com sucesso!'})
        except Error as e:
            return jsonify({'success': False, 'message': 'Email já cadastrado'})
    
    return jsonify({'success': False, 'message': 'Erro ao conectar ao banco'})

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection('sistema_assinaturas')
    stats = {
        'projetos': 0,
        'armazenamento': '0 MB',
        'api_calls': 0
    }
    
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM usuarios WHERE ativo = TRUE")
        stats['total_usuarios'] = cursor.fetchone()[0]
        cursor.close()
        conn.close()
    
    return render_template('dashboard.html', stats=stats)

@app.route('/planos')
def planos():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('planos.html', planos=PLANOS)

@app.route('/criar_pagamento', methods=['POST'])
def criar_pagamento():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Usuário não autenticado'}), 401

    data = request.get_json() or {}
    plano = data.get('plano')
    cpf = data.get('cpf', '')

    if plano not in PLANOS:
        return jsonify({'success': False, 'message': 'Plano inválido'}), 400

    # Plano free não precisa CPF
    if plano == 'free':
        conn = get_db_connection('sistema_assinaturas')
        if conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE usuarios SET plano = %s WHERE id = %s", (plano, session['user_id']))
            conn.commit()
            cursor.close()
            conn.close()
            session['user_plano'] = plano
        return jsonify({'success': True, 'plano': 'free'})

    # ✅ Planos pagos: CPF obrigatório
    cpf_digits = ''.join(ch for ch in str(cpf) if ch.isdigit())
    if len(cpf_digits) != 11 or cpf_digits == cpf_digits[0] * 11:
        return jsonify({'success': False, 'message': 'CPF inválido'}), 400

    # (Opcional) salvar cpf no usuário
    conn = get_db_connection('sistema_assinaturas')
    if conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE usuarios SET cpf = %s WHERE id = %s", (cpf_digits, session['user_id']))
        conn.commit()
        cursor.close()
        conn.close()

    valor = PLANOS[plano]['preco']
    pix_data = gerar_pix_qrcode(valor, session['user_id'], plano, cpf_digits)

    if pix_data.get('success'):
        return jsonify(pix_data)

    # devolve o erro real do MP para você depurar no front
    return jsonify({
        'success': False,
        'message': pix_data.get('error', 'Erro ao gerar PIX'),
        'details': pix_data.get('details')
    }), 400



@app.route('/verificar_pagamento/<pix_id>', methods=['GET'])
def verificar_pagamento(pix_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Usuário não autenticado'})
    
    conn = get_db_connection('sistema_assinaturas')
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM pagamentos WHERE pix_id = %s AND usuario_id = %s", (pix_id, session['user_id']))
        pagamento = cursor.fetchone()
        
        if pagamento and pagamento['status'] == 'confirmado':
            cursor.execute("UPDATE usuarios SET plano = %s WHERE id = %s", (pagamento['plano'], session['user_id']))
            conn.commit()
            session['user_plano'] = pagamento['plano']
            cursor.close()
            conn.close()
            return jsonify({'success': True, 'status': 'confirmado', 'plano': pagamento['plano']})
        
        cursor.close()
        conn.close()
    
    return jsonify({'success': True, 'status': 'pendente'})

@app.route('/webhook', methods=['POST'])
def webhook():
    """✅ Webhook Mercado Pago - atualiza status automaticamente"""
    try:
        data = request.get_json()
        payment_id = data.get('data', {}).get('id')
        
        if payment_id:
            sdk = mercadopago.SDK(MERCADO_PAGO_ACCESS_TOKEN)
            payment = sdk.payment().find_by_id(payment_id)['response']
            
            if payment.get('status') == 'approved':
                conn = get_db_connection('sistema_assinaturas')
                if conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE pagamentos SET status = 'confirmado' WHERE mp_payment_id = %s",
                        (payment_id,)
                    )
                    cursor.execute(
                        "UPDATE usuarios u JOIN pagamentos p ON u.id = p.usuario_id SET u.plano = p.plano WHERE p.mp_payment_id = %s",
                        (payment_id,)
                    )
                    conn.commit()
                    cursor.close()
                    conn.close()
                    print(f"✅ Pagamento {payment_id} aprovado automaticamente!")
        
        return jsonify({'status': 'ok'})
    except Exception as e:
        print(f"Erro webhook: {e}")
        return jsonify({'status': 'error'}), 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/user_info')
def user_info():
    if 'user_id' not in session:
        return jsonify({'success': False})
    
    return jsonify({
        'success': True,
        'nome': session.get('user_name'),
        'email': session.get('user_email'),
        'plano': session.get('user_plano')
    })

if __name__ == '__main__':
    print("🚀 Iniciando Sistema de Assinaturas com PIX REAL...")
    print("💳 Mercado Pago TESTE configurado!")
    init_database()
    print("🌐 Servidor Flask + PIX REAL em http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
