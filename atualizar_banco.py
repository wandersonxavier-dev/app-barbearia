import os
from sqlalchemy import text
from database import engine


def atualizar_estrutura_banco():
    with engine.connect() as conn:
        print("Iniciando atualização da estrutura do banco...")

        # 1. Se for PostgreSQL, adiciona o novo valor 'FIADO' no ENUM do status_pagamento
        if "postgresql" in str(engine.url):
            try:
                conn.execute(text("ALTER TYPE statuspagamento ADD VALUE IF NOT EXISTS 'FIADO';"))
                conn.execute(text("ALTER TYPE statuspagamento ADD VALUE IF NOT EXISTS 'fiado';"))
                conn.commit()
                print("✔ Enum de status_pagamento atualizado no PostgreSQL.")
            except Exception as e:
                print(f"Aviso no enum (pode já existir): {e}")

        # 2. Lista das novas colunas para adicionar na tabela clientes
        colunas = [
            ("cpf", "VARCHAR(20)"),
            ("rg", "VARCHAR(20)"),
            ("data_nascimento", "VARCHAR(15)"),
            ("genero", "VARCHAR(20)"),
            ("estado_civil", "VARCHAR(30)"),
            ("profissao", "VARCHAR(100)"),
            ("telefone_residencial", "VARCHAR(20)"),
            ("email", "VARCHAR(100)"),
            ("instagram", "VARCHAR(100)"),
            ("endereco", "VARCHAR(255)"),
            ("numero", "VARCHAR(20)"),
            ("bairro", "VARCHAR(100)"),
            ("cidade", "VARCHAR(100)"),
            ("cep", "VARCHAR(20)")
        ]

        for nome_coluna, tipo_coluna in colunas:
            try:
                conn.execute(text(f"ALTER TABLE clientes ADD COLUMN IF NOT EXISTS {nome_coluna} {tipo_coluna};"))
                conn.commit()
                print(f"✔ Coluna '{nome_coluna}' verificada/adicionada com sucesso.")
            except Exception as e:
                print(f"Aviso na coluna '{nome_coluna}': {e}")

        print("Concluído!")


if __name__ == "__main__":
    atualizar_estrutura_banco()
