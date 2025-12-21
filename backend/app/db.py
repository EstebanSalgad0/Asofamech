from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# Configurar encoding para PostgreSQL
os.environ['PGCLIENTENCODING'] = 'UTF8'

# Para desarrollo local, conectarse a localhost
# Para Docker, se usaría "db" en lugar de "localhost"
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://app_user:app_pass@localhost:5432/app_db"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    from fastapi import Depends
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
