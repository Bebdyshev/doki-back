from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
from typing import Generator
from schemas.models import Base

load_dotenv()

POSTGRES_URL = os.getenv("POSTGRES_URL")

# Database setup
engine = create_engine(POSTGRES_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

print("Connecting to:", POSTGRES_URL)

def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    print("Initializing the database...")
    Base.metadata.create_all(bind=engine)

def reset_db():
    print("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    print("Recreating all tables...")
    Base.metadata.create_all(bind=engine)