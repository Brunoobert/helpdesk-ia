import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/helpdesk")

# Inicializa o motor do banco de dados
engine = create_engine(DATABASE_URL)

# Configura a fábrica de sessões locais
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base declarativa para os modelos do ORM
Base = declarative_base()

def get_db():
    """
    Generator que fornece uma sessão do banco de dados e garante
    seu fechamento seguro após o término da requisição.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
