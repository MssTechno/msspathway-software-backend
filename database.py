import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "postgresql://postgres:Venkatsai@localhost:5432/pathway_db"

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,     # checks connection before using it
    pool_recycle=300,       # recycles connection every 5 minutes
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
