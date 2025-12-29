from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error
import hashlib
import secrets
from datetime import datetime, timedelta
import qrcode
import io
import base64
import uuid

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
CORS(app)

# Configuração do MySQL no Square Cloud
DB_CONFIG = {
    'host': 'square-cloud-db-45ee9918389d44b3937fdb8e41f83048.squareweb.app',  # Substituir pelo host do Square Cloud
    'user': 'squarecloud',
    'password': 'INNbhFE8vqhXzKTHUHLhLFWk',
    'database': 'auth_2fa_db',
    'port': 7102
}

# Planos disponíveis
PLANOS = {
    'free': {'nome': 'Gratuito', 'preco': 0.00, 'recursos': ['Recurso básico', '5 projetos', 'Suporte por email']},
    'pro': {'nome': 'Pro', 'preco': 29.90, 'recursos': ['Todos recursos básicos', '50 projetos', 'Suporte prioritário', 'API Access']},
    'premium': {'nome': 'Premium', 'preco': 79.90, 'recursos': ['Recursos ilimitados', 'Projetos ilimitados', 'Suporte 24/7', 'API Access', 'Relatórios avançados']}
}

def get_db_connection():
    """Conecta ao banco de dados MySQL"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"Erro ao conectar ao MySQL: {e}")
        return None

def init_database():
    """Inicializa as tabelas do banco de dados"""
    conn = get_db_connection()
    if conn:
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
                ativo BOOLEAN DEFAULT TRUE
            )
        """)

        # Tabela de pagamentos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pagamentos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                usuario_id INT,
                plano VARCHAR(20),
                valor DECIMAL(10,2),
                pix_id VARCHAR(100) UNIQUE,
                qr_code TEXT,
                status VARCHAR(20) DEFAULT 'pendente',
                data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_expiracao TIMESTAMP,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
            )
        """)

        conn.commit()
        cursor.close()
        conn.close()
        print("Banco de dados inicializado!")

def hash_password(password):
    """Hash de senha usando SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def gerar_pix_qrcode(valor, usuario_id, plano):
    """Gera QR Code PIX para pagamento"""
    pix_id = str(uuid.uuid4())

    # Dados do PIX (em produção, usar API do banco)
    # Formato EMV simplificado para demonstração
    chave_pix = "juanpmoraes2@gmail.com"  # Substituir pela sua chave PIX
    merchant_name = "JPBOT"
    merchant_city = "Sao Paulo"

    # Payload PIX (simplificado - em produção usar biblioteca específica)
    payload = f"00020126{len(chave_pix):02d}{chave_pix}5204000053039865802BR5913{merchant_name}6009{merchant_city}62070503***6304"

    # Gerar QR Code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(payload)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Converter para base64
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()

    # Salvar no banco
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        data_expiracao = datetime.now() + timedelta(hours=1)
        cursor.execute(
            "INSERT INTO pagamentos (usuario_id, plano, valor, pix_id, qr_code, data_expiracao) VALUES (%s, %s, %s, %s, %s, %s)",
            (usuario_id, plano, valor, pix_id, img_str, data_expiracao)
        )
        conn.commit()
        cursor.close()
        conn.close()

    return {'pix_id': pix_id, 'qr_code': img_str, 'payload': payload}

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

        conn = get_db_connection()
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

    conn = get_db_connection()
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

    conn = get_db_connection()
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
        return jsonify({'success': False, 'message': 'Usuário não autenticado'})

    data = request.get_json()
    plano = data.get('plano')

    if plano not in PLANOS:
        return jsonify({'success': False, 'message': 'Plano inválido'})

    if plano == 'free':
        # Atualizar plano diretamente
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE usuarios SET plano = %s WHERE id = %s", (plano, session['user_id']))
            conn.commit()
            cursor.close()
            conn.close()
            session['user_plano'] = plano
        return jsonify({'success': True, 'plano': 'free'})

    # Gerar PIX para planos pagos
    valor = PLANOS[plano]['preco']
    pix_data = gerar_pix_qrcode(valor, session['user_id'], plano)

    return jsonify({
        'success': True,
        'pix_id': pix_data['pix_id'],
        'qr_code': pix_data['qr_code'],
        'valor': valor,
        'plano': plano
    })

@app.route('/verificar_pagamento/<pix_id>', methods=['GET'])
def verificar_pagamento(pix_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Usuário não autenticado'})

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM pagamentos WHERE pix_id = %s AND usuario_id = %s", (pix_id, session['user_id']))
        pagamento = cursor.fetchone()

        if pagamento:
            # Em produção, verificar com API do banco se pagamento foi confirmado
            # Por enquanto, simulação manual
            status = pagamento['status']

            if status == 'confirmado':
                # Atualizar plano do usuário
                cursor.execute("UPDATE usuarios SET plano = %s WHERE id = %s", (pagamento['plano'], session['user_id']))
                conn.commit()
                session['user_plano'] = pagamento['plano']
                cursor.close()
                conn.close()
                return jsonify({'success': True, 'status': 'confirmado', 'plano': pagamento['plano']})

        cursor.close()
        conn.close()

    return jsonify({'success': True, 'status': 'pendente'})

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
    init_database()
    app.run(debug=True, host='0.0.0.0', port=5000)
