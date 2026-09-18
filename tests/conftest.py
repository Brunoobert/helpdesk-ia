import pytest
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.main import app

# Banco de dados SQLite em memoria para isolar os testes da base real
SQLALCHEMY_DATABASE_URL = "sqlite://"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Cria as tabelas na base SQLite de testes
Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

# Registra o override no FastAPI
app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(autouse=True)
def rate_limit_guard(request):
    yield
    if request.node.get_closest_marker("integration"):
        time.sleep(5)