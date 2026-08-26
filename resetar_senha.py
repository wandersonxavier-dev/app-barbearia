from dotenv import load_dotenv

load_dotenv()  # Carrega automaticamente o que está no arquivo .env

from sqlalchemy.orm import Session
from database import SessionLocal
import models
import security


def redefinir_ou_criar_senha():
    db: Session = SessionLocal()
    try:
        print("=== REDEFINIÇÃO / CRIAÇÃO DE SENHA - INFINITY 027 ===")

        # Lista os usuários cadastrados
        usuarios = db.query(models.Usuario).all()
        if usuarios:
            print("\nUsuários cadastrados no banco atual:")
            for u in usuarios:
                print(f"- ID: {u.id} | Nome: {u.nome} | E-mail: {u.email}")
        else:
            print("\nNenhum usuário cadastrado neste banco.")

        email_alvo = input(
            "\nDigite o e-mail que você usa para fazer login: "
        ).strip()

        if not email_alvo:
            print("❌ E-mail inválido.")
            return

        usuario = (
            db.query(models.Usuario)
            .filter(models.Usuario.email == email_alvo)
            .first()
        )

        nova_senha = input("Digite a nova senha (ela aparecerá na tela): ")
        confirma_senha = input("Confirme a nova senha: ")

        if nova_senha != confirma_senha:
            print("❌ Erro: As senhas não conferem.")
            return

        if len(nova_senha) < 3:
            print("❌ Erro: A senha é muito curta.")
            return

        hash_senha = security.gerar_hash_senha(nova_senha)

        if usuario:
            # Se o usuário já existe, apenas atualiza a senha
            usuario.senha_hash = hash_senha
            db.commit()
            print(
                f"✔ Senha do usuário '{usuario.nome}' ({usuario.email}) redefinida com sucesso!"
            )
        else:
            # Se o usuário não existe neste banco, cria ele agora mesmo
            nome_usuario = (
                input("Usuário não encontrado. Digite o nome para criá-lo: ")
                .strip()
                or "Administrador"
            )
            novo_usuario = models.Usuario(
                nome=nome_usuario, email=email_alvo, senha_hash=hash_senha
            )
            db.add(novo_usuario)
            db.commit()
            print(
                f"✔ Usuário '{email_alvo}' criado e senha configurada com sucesso!"
            )

    except Exception as e:
        db.rollback()
        print(f"❌ Ocorreu um erro: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    redefinir_ou_criar_senha()
