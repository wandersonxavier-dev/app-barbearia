from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

# Cria o arquivo local do banco SQLite
SQLALCHEMY_DATABASE_URL = "sqlite:///./barbearia.db"

# connect_args={"check_same_thread": False} é obrigatório apenas para SQLite no FastAPI
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# Função geradora de sessão do banco para usar com Depends() no FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()