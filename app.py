from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error
import hashlib
import secrets
from datetime import datetime, timedelta
import io
import base64
import mercadopago  # PIX REAL
import qrcode       # Para QR Code
import os
from functools import wraps

WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://jpbot.squareweb.app/webhook")

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
CORS(app)

# Configuração do MySQL no Square Cloud
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'square-cloud-db-45ee9918389d44b3937fdb8e41f83048.squareweb.app'),
    'user': os.getenv('DB_USER', 'squarecloud'),
    'password': os.getenv('DB_PASSWORD', 'INNbhFE8vqhXzKTHUHLhLFWk'),
    'port': int(os.getenv('DB_PORT', '7102'))
}

# Mercado Pago (use env vars)
MERCADO_PAGO_ACCESS_TOKEN = os.getenv("MERCADO_PAGO_ACCESS_TOKEN", "APP_USR-5510745273548389-122922-053d1050455391a02eece2b5052a1b08-496902134")
MERCADO_PAGO_PUBLIC_KEY = os.getenv("MERCADO_PAGO_PUBLIC_KEY", "APP_USR-cd6283c6-f89b-4f57-94d3-a9d68b174a8a")

# Planos disponíveis
PLANOS = {
    'free': {
        'nome': 'Gratuito',
        'preco': 0.00,
        'recursos': [
            'Recurso básico',
            '5 projetos',
            'Suporte por email'
        ],
        'limites': {
            'projetos': 5,
            'api_calls_mes': 0
        },
        'features': {
            'api_access': False,
            'relatorios_avancados': False,
            'suporte_prioritario': False
        }
    },
    'pro': {
        'nome': 'Pro',
        'preco': 1.00,
        'recursos': [
            'Todos recursos básicos',
            '50 projetos',
            'Suporte prioritário',
            'API Access'
        ],
        'limites': {
            'projetos': 50,
            'api_calls_mes': 10000
        },
        'features': {
            'api_access': True,
            'relatorios_avancados': False,
            'suporte_prioritario': True
        }
    },
    'premium': {
        'nome': 'Premium',
        'preco': 79.90,
        'recursos': [
            'Recursos ilimitados',
            'Projetos ilimitados',
            'Suporte 24/7',
            'API Access',
            'Relatórios avançados'
        ],
        'limites': {
            'projetos': None,  # None = ilimitado
            'api_calls_mes': 100000
        },
        'features': {
            'api_access': True,
            'relatorios_avancados': True,
            'suporte_prioritario': True
        }
    }
}


# -------------------------
# Helpers
# -------------------------
def login_required_json(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Usuário não autenticado'}), 401
        return fn(*args, **kwargs)
    return wrapper


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
    if len(cpf_digits) != 11:
        return False
    if cpf_digits == cpf_digits[0] * 11:
        return False
    return True


def get_db_connection(database=None):
    config = DB_CONFIG.copy()
    if database:
        config['database'] = database
    try:
        return mysql.connector.connect(**config)
    except Error as e:
        print(f"Erro ao conectar ao MySQL: {e}")
        return None


def create_database():
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
            cpf VARCHAR(11) NULL,
            data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ativo BOOLEAN DEFAULT TRUE,
            INDEX idx_email (email),
            INDEX idx_plano (plano)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # Tabela de pagamentos
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
            cpf VARCHAR(11) NULL,
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

    # Projetos (para limite por plano)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projetos (
            id INT AUTO_INCREMENT PRIMARY KEY,
            usuario_id INT NOT NULL,
            nome VARCHAR(120) NOT NULL,
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            INDEX idx_usuario (usuario_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # Uso mensal API (pronto para usar depois)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_uso_mensal (
            usuario_id INT NOT NULL,
            ano_mes CHAR(7) NOT NULL,
            total INT NOT NULL DEFAULT 0,
            PRIMARY KEY (usuario_id, ano_mes),
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # Garante colunas antigas (caso já existam tabelas sem elas)
    ensure_column(cursor, "usuarios", "cpf", "cpf VARCHAR(11) NULL")
    ensure_column(cursor, "pagamentos", "cpf", "cpf VARCHAR(11) NULL")

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
    return hashlib.sha256(password.encode()).hexdigest()


# -------------------------
# Plano / Limites (projetos)
# -------------------------
def get_user_plano(usuario_id):
    conn = get_db_connection('sistema_assinaturas')
    if not conn:
        return "free"
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT plano FROM usuarios WHERE id=%s", (usuario_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row["plano"] if row else "free"


def can_create_project(usuario_id):
    plano = get_user_plano(usuario_id)
    limite = PLANOS[plano]["limites"]["projetos"]

    if limite is None:
        return True, None

    conn = get_db_connection('sistema_assinaturas')
    if not conn:
        return False, "Erro ao conectar ao banco."

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM projetos WHERE usuario_id=%s", (usuario_id,))
    qtd = cur.fetchone()[0]
    cur.close()
    conn.close()

    if qtd >= limite:
        return False, f"Limite do plano {plano}: {limite} projetos."
    return True, None


def get_ano_mes(dt=None):
    dt = dt or datetime.utcnow()
    return dt.strftime("%Y-%m")  # ex: '2025-12'


def get_api_quota_limit(plano: str):
    plano = plano if plano in PLANOS else "free"
    return PLANOS[plano]["limites"]["api_calls_mes"]


def get_api_usage(usuario_id: int, ano_mes: str):
    conn = get_db_connection("sistema_assinaturas")
    if not conn:
        return 0
    cur = conn.cursor()
    cur.execute(
        "SELECT total FROM api_uso_mensal WHERE usuario_id=%s AND ano_mes=%s",
        (usuario_id, ano_mes)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return int(row[0]) if row else 0


def try_consume_api_call(usuario_id: int):
    """
    Tenta consumir 1 API call do mês atual.
    Retorna (allowed, info_dict)
    """
    plano = get_user_plano(usuario_id)
    limit = get_api_quota_limit(plano)
    ano_mes = get_ano_mes()

    # Sem acesso a API no FREE (limit=0)
    if limit is not None and limit <= 0:
        return False, {"plano": plano, "limit": limit, "used": 0, "ano_mes": ano_mes}

    conn = get_db_connection("sistema_assinaturas")
    if not conn:
        return False, {"plano": plano, "limit": limit, "used": None, "ano_mes": ano_mes, "error": "db"}

    cur = conn.cursor()

    try:
        conn.start_transaction()

        # trava a linha do mês (se existir) para evitar corrida [web:396]
        cur.execute(
            "SELECT total FROM api_uso_mensal WHERE usuario_id=%s AND ano_mes=%s FOR UPDATE",
            (usuario_id, ano_mes)
        )
        row = cur.fetchone()

        if not row:
            # primeira chamada do mês
            used_after = 1
            if limit is not None and used_after > limit:
                conn.rollback()
                return False, {"plano": plano, "limit": limit, "used": 0, "ano_mes": ano_mes}

            cur.execute(
                "INSERT INTO api_uso_mensal (usuario_id, ano_mes, total) VALUES (%s, %s, %s)",
                (usuario_id, ano_mes, used_after)
            )
            conn.commit()
            return True, {"plano": plano, "limit": limit, "used": used_after, "ano_mes": ano_mes}

        used = int(row[0])

        # limite atingido
        if limit is not None and used >= limit:
            conn.rollback()
            return False, {"plano": plano, "limit": limit, "used": used, "ano_mes": ano_mes}

        used_after = used + 1
        cur.execute(
            "UPDATE api_uso_mensal SET total=%s WHERE usuario_id=%s AND ano_mes=%s",
            (used_after, usuario_id, ano_mes)
        )
        conn.commit()
        return True, {"plano": plano, "limit": limit, "used": used_after, "ano_mes": ano_mes}

    except Exception as e:
        conn.rollback()
        return False, {"plano": plano, "limit": limit, "used": None, "ano_mes": ano_mes, "error": str(e)}

    finally:
        cur.close()
        conn.close()


@app.route("/api/ping", methods=["GET"])
def api_ping():
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Usuário não autenticado"}), 401

    allowed, info = try_consume_api_call(session["user_id"])
    if not allowed:
        # 429 é o status mais usado para limite/quotas estouradas [web:398]
        return jsonify({
            "success": False,
            "message": "Quota mensal de API atingida.",
            "quota": info
        }), 429

    return jsonify({
        "success": True,
        "message": "pong",
        "quota": info
    })


@app.route("/api/quota", methods=["GET"])
def api_quota():
    if "user_id" not in session:
        return jsonify({"success": False}), 401

    plano = get_user_plano(session["user_id"])
    ano_mes = get_ano_mes()
    used = get_api_usage(session["user_id"], ano_mes)
    limit = get_api_quota_limit(plano)

    return jsonify({
        "success": True,
        "plano": plano,
        "ano_mes": ano_mes,
        "used": used,
        "limit": limit
    })








# -------------------------
# Mercado Pago / PIX
# -------------------------
def gerar_pix_qrcode(valor, usuario_id, plano, cpf_digits):
    try:
        if not MERCADO_PAGO_ACCESS_TOKEN:
            return {"success": False, "error": "MERCADO_PAGO_ACCESS_TOKEN não configurado."}

        print(f"💳 Criando PIX Mercado Pago: R${valor} - Plano {plano}")

        sdk = mercadopago.SDK(MERCADO_PAGO_ACCESS_TOKEN)

        payment_data = {
            "transaction_amount": float(valor),
            "payment_method_id": "pix",
            "description": f"Assinatura JPBOT - {PLANOS[plano]['nome']}",
            "external_reference": f"{session['user_id']}_{plano}_{int(datetime.now().timestamp())}",
            "notification_url": WEBHOOK_URL,
            "payer": {
                "email": session.get("user_email", "cliente@exemplo.com"),
                "first_name": session.get("user_name", "Cliente"),
                "last_name": "JPBOT",
                "identification": {"type": "CPF", "number": cpf_digits}
            }
        }

        print("➡️ payment_data =", payment_data)

        response = sdk.payment().create(payment_data)
        payment = response.get("response", {})

        status = payment.get("status")
        print(f"📋 Mercado Pago Response status: {status}")

        if status != "pending":
            return {
                "success": False,
                "error": f"Pagamento não ficou pendente: {payment.get('status_detail', status)}",
                "details": payment
            }

        pix_id = str(payment["id"])
        qr_data = None
        qr_string = None

        poi = payment.get("point_of_interaction") or {}
        tx = poi.get("transaction_data") or {}
        qr_string = tx.get("qr_code")
        qr_base64 = tx.get("qr_code_base64")

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


# -------------------------
# Rotas (páginas)
# -------------------------
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
        except Error:
            return jsonify({'success': False, 'message': 'Email já cadastrado'})

    return jsonify({'success': False, 'message': 'Erro ao conectar ao banco'})


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Sincroniza plano da sessão com o banco
    conn = get_db_connection('sistema_assinaturas')
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT plano FROM usuarios WHERE id = %s", (session['user_id'],))
        row = cursor.fetchone()
        if row and row.get('plano'):
            session['user_plano'] = row['plano']
        cursor.close()
        conn.close()

    plano_atual = session.get('user_plano', 'free')
    limite_projetos = PLANOS.get(plano_atual, PLANOS['free'])['limites']['projetos']

    stats = {
        'projetos': 0,
        'limite_projetos': limite_projetos,
        'armazenamento': '0 MB',
        'api_calls': 0,
        'total_usuarios': 0
    }

    conn = get_db_connection('sistema_assinaturas')
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM usuarios WHERE ativo = TRUE")
        stats['total_usuarios'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM projetos WHERE usuario_id=%s", (session['user_id'],))
        stats['projetos'] = cursor.fetchone()[0]

        cursor.close()
        conn.close()

    return render_template('dashboard.html', stats=stats)


@app.route('/planos')
def planos():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('planos.html', planos=PLANOS)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# -------------------------
# Pagamento / Webhook
# -------------------------
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

    # Planos pagos: CPF obrigatório
    cpf_digits = sanitize_cpf(cpf)
    if not is_cpf_basic_valid(cpf_digits):
        return jsonify({'success': False, 'message': 'CPF inválido'}), 400

    # Salvar cpf no usuário (opcional)
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

    return jsonify({
        'success': False,
        'message': pix_data.get('error', 'Erro ao gerar PIX'),
        'details': pix_data.get('details')
    }), 400


@app.route('/verificar_pagamento/<pix_id>', methods=['GET'])
def verificar_pagamento(pix_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Usuário não autenticado'}), 401

    conn = get_db_connection('sistema_assinaturas')
    if not conn:
        return jsonify({'success': False, 'message': 'Erro ao conectar ao banco'}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT * FROM pagamentos WHERE pix_id = %s AND usuario_id = %s",
            (pix_id, session['user_id'])
        )
        pagamento = cursor.fetchone()

        if not pagamento:
            return jsonify({'success': False, 'message': 'Pagamento não encontrado'}), 404

        if pagamento.get('status') == 'confirmado':
            cursor.execute(
                "UPDATE usuarios SET plano = %s WHERE id = %s",
                (pagamento['plano'], session['user_id'])
            )
            conn.commit()
            session['user_plano'] = pagamento['plano']
            return jsonify({'success': True, 'status': 'confirmado', 'plano': pagamento['plano']})

        mp_payment_id = pagamento.get('mp_payment_id')
        if not mp_payment_id:
            return jsonify({'success': True, 'status': 'pendente'})

        if not MERCADO_PAGO_ACCESS_TOKEN:
            return jsonify({'success': True, 'status': 'pendente', 'mp_status': None})

        sdk = mercadopago.SDK(MERCADO_PAGO_ACCESS_TOKEN)
        mp_resp = sdk.payment().get(str(mp_payment_id))
        mp_payment = mp_resp.get('response', {})
        mp_status = mp_payment.get('status')

        if mp_status == 'approved':
            cursor.execute(
                "UPDATE pagamentos SET status = 'confirmado' WHERE pix_id = %s AND usuario_id = %s",
                (pix_id, session['user_id'])
            )
            cursor.execute(
                "UPDATE usuarios SET plano = %s WHERE id = %s",
                (pagamento['plano'], session['user_id'])
            )
            conn.commit()
            session['user_plano'] = pagamento['plano']
            return jsonify({'success': True, 'status': 'confirmado', 'plano': pagamento['plano']})

        return jsonify({'success': True, 'status': 'pendente', 'mp_status': mp_status})

    finally:
        cursor.close()
        conn.close()


@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    try:
        payload = request.get_json(silent=True) or {}

        payment_id = (payload.get("data") or {}).get("id")
        if not payment_id:
            payment_id = request.args.get("id") or request.args.get("data.id")

        if not payment_id:
            return jsonify({"status": "ok", "message": "no payment id"}), 200

        if not MERCADO_PAGO_ACCESS_TOKEN:
            return jsonify({"status": "ok", "message": "no access token"}), 200

        sdk = mercadopago.SDK(MERCADO_PAGO_ACCESS_TOKEN)
        mp_resp = sdk.payment().get(str(payment_id))
        mp_payment = mp_resp.get("response", {})
        mp_status = mp_payment.get("status")

        print(f"🔔 Webhook recebido payment_id={payment_id} status={mp_status}")

        if mp_status == "approved":
            conn = get_db_connection("sistema_assinaturas")
            if conn:
                cursor = conn.cursor()

                cursor.execute(
                    "UPDATE pagamentos SET status='confirmado' WHERE mp_payment_id=%s OR pix_id=%s",
                    (str(payment_id), str(payment_id))
                )
                cursor.execute(
                    """UPDATE usuarios u
                       JOIN pagamentos p ON u.id = p.usuario_id
                       SET u.plano = p.plano
                       WHERE p.mp_payment_id=%s OR p.pix_id=%s""",
                    (str(payment_id), str(payment_id))
                )

                conn.commit()
                cursor.close()
                conn.close()
                print(f"✅ Pagamento {payment_id} confirmado no banco!")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"Erro webhook: {e}")
        return jsonify({"status": "ok"}), 200


# -------------------------
# API do usuário
# -------------------------
@app.route('/api/user_info')
def user_info():
    if 'user_id' not in session:
        return jsonify({'success': False})

    # sempre tenta refletir o plano real do banco
    plano_atual = get_user_plano(session['user_id'])
    session['user_plano'] = plano_atual

    return jsonify({
        'success': True,
        'nome': session.get('user_name'),
        'email': session.get('user_email'),
        'plano': plano_atual
    })


# -------------------------
# API de Projetos (limite por plano)
# -------------------------
@app.route('/api/projetos', methods=['GET'])
@login_required_json
def listar_projetos():
    conn = get_db_connection('sistema_assinaturas')
    if not conn:
        return jsonify({'success': False, 'message': 'Erro ao conectar ao banco'}), 500

    cur = conn.cursor(dictionary=True)
    cur.execute(
        "SELECT id, nome, data_criacao FROM projetos WHERE usuario_id=%s ORDER BY id DESC",
        (session['user_id'],)
    )
    projetos = cur.fetchall()
    cur.close()
    conn.close()

    plano = get_user_plano(session['user_id'])
    limite = PLANOS[plano]["limites"]["projetos"]

    return jsonify({
        'success': True,
        'plano': plano,
        'limite_projetos': limite,
        'total_projetos': len(projetos),
        'projetos': projetos
    })


@app.route('/api/projetos', methods=['POST'])
@login_required_json
def criar_projeto():
    data = request.get_json() or {}
    nome = (data.get('nome') or '').strip()

    if not nome:
        return jsonify({'success': False, 'message': 'Nome do projeto é obrigatório'}), 400

    ok, msg = can_create_project(session['user_id'])
    if not ok:
        return jsonify({'success': False, 'message': msg}), 403

    conn = get_db_connection('sistema_assinaturas')
    if not conn:
        return jsonify({'success': False, 'message': 'Erro ao conectar ao banco'}), 500

    cur = conn.cursor()
    cur.execute(
        "INSERT INTO projetos (usuario_id, nome) VALUES (%s, %s)",
        (session['user_id'], nome)
    )
    conn.commit()
    projeto_id = cur.lastrowid
    cur.close()
    conn.close()

    return jsonify({'success': True, 'id': projeto_id, 'nome': nome})


if __name__ == '__main__':
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))

    print("🚀 Iniciando Sistema de Assinaturas com PIX REAL...")
    init_database()
    print(f"🌐 Servidor em http://{host}:{port}")

    app.run(debug=False, host=host, port=port)
