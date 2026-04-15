# db.py
from sqlalchemy import create_engine, Column, Integer, String, JSON, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
import datetime
from pathlib import Path

Base = declarative_base()
DB_PATH = Path(__file__).resolve().with_name("cyber_hax.db")
engine = create_engine(f"sqlite:///{DB_PATH.as_posix()}", echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
DB_READY = False

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)  # store hash, not plaintext
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class MatchHistory(Base):
    __tablename__ = "matches"
    id = Column(Integer, primary_key=True, index=True)
    winner = Column(String)
    state_snapshot = Column(JSON)  # serialized JSON of final state
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

try:
    Base.metadata.create_all(bind=engine)
    DB_READY = True
except Exception as exc:
    print(f"[DB] Initialization skipped: {exc}")
