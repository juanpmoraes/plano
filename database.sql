-- Script de criação do banco de dados
-- Execute este script no MySQL do Square Cloud

CREATE DATABASE IF NOT EXISTS sistema_assinaturas;
USE sistema_assinaturas;

-- Tabela de usuários
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabela de pagamentos
CREATE TABLE IF NOT EXISTS pagamentos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    plano VARCHAR(20) NOT NULL,
    valor DECIMAL(10,2) NOT NULL,
    pix_id VARCHAR(100) UNIQUE NOT NULL,
    qr_code TEXT,
    status VARCHAR(20) DEFAULT 'pendente',
    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_expiracao TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    INDEX idx_usuario (usuario_id),
    INDEX idx_status (status),
    INDEX idx_pix (pix_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Inserir usuário de teste (senha: teste123)
INSERT INTO usuarios (nome, email, senha, plano) VALUES 
('Usuário Teste', 'teste@email.com', 'ecd71870d1963316a97e3ac3408c9835ad8cf0f3c1bc703527c30265534f75ae', 'free');
