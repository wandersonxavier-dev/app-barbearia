from datetime import datetime, timedelta
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database import get_db
import models

SECRET_KEY = "CHAVE_SECRETA_MUDE_EM_PRODUCAO_123456"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 horas

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def verificar_senha(senha_plana: str, senha_hash: str) -> bool:
    return bcrypt.checkpw(
        senha_plana.encode("utf-8"), senha_hash.encode("utf-8")
    )


def gerar_hash_senha(senha: str) -> str:
    salt = bcrypt.gensalt()
    hash_bytes = bcrypt.hashpw(senha.encode("utf-8"), salt)
    return hash_bytes.decode("utf-8")


def criar_token_acesso(dados: dict) -> str:
    dados_para_codificar = dados.copy()
    expira_em = datetime.utcnow() + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    dados_para_codificar.update({"exp": expira_em})
    return jwt.encode(dados_para_codificar, SECRET_KEY, algorithm=ALGORITHM)


def obter_usuario_logado(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> models.Usuario:
    excecao_credenciais = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido ou expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise excecao_credenciais
    except JWTError:
        raise excecao_credenciais

    usuario = (
        db.query(models.Usuario).filter(models.Usuario.email == email).first()
    )
    if usuario is None:
        raise excecao_credenciais
    return usuario
