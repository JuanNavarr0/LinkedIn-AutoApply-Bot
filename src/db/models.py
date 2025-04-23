# src/db/models.py
"""
Database models for the LinkedIn job application bot.

Defines the SQLAlchemy models for storing job application data,
along with functions for database initialization and session management.
"""

import logging
import enum
from datetime import datetime
from typing import Optional, Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean, Enum as SQLEnum
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from sqlalchemy.sql import func

from ..config import Config


class ApplicationStatus(enum.Enum):
    """Status enum for job applications"""
    PENDING = "Pending"
    APPLIED = "Applied" 
    SKIPPED = "Skipped"
    FAILED = "Failed"
    ERROR = "Error"
    VIEWED = "Viewed"
    MANUAL_REVIEW = "Manual Review"


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models"""
    pass


class JobApplication(Base):
    """
    SQLAlchemy model representing a job application record.
    """
    __tablename__ = 'job_applications'

    id = Column(Integer, primary_key=True)
    linkedin_job_id = Column(String, unique=True, nullable=True, index=True)
    job_title = Column(String, nullable=False)
    company_name = Column(String, nullable=True)
    job_url = Column(String, unique=True, nullable=False)
    location = Column(String, nullable=True)
    status = Column(SQLEnum(ApplicationStatus), default=ApplicationStatus.PENDING, nullable=False, index=True)
    application_date = Column(DateTime(timezone=True), nullable=True)
    cover_letter_generated = Column(Boolean, default=False)
    cover_letter_text = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self) -> str:
        status_val = self.status.value if self.status else 'N/A'
        return f"<JobApplication(id={self.id}, title='{self.job_title}', status='{status_val}')>"


# Database setup
engine = None
SessionLocal = None
logger = logging.getLogger(__name__)

def init_db(config: Config) -> None:
    """Initialize the database engine and create tables if they don't exist."""
    global engine, SessionLocal
    if engine is None:
        db_url = config.DATABASE_URL
        assert db_url, "DATABASE_URL must be set."
        logger.info(f"Initializing DB: {db_url.split('@')[-1]}")
        try:
            engine = create_engine(db_url, echo=False)
            Base.metadata.create_all(bind=engine)
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            logger.info("Database initialized.")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}", exc_info=True)
            engine = None
            raise

@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Provide a database session generator compatible with 'with' statement."""
    if SessionLocal is None:
        logger.error("Database not initialized.")
        raise RuntimeError("SessionLocal not configured.")
    db: Optional[Session] = None
    try:
        db = SessionLocal()
        yield db
    except Exception:
        logger.error("Database session error, rolling back...", exc_info=True)
        db.rollback()
        raise
    finally:
        if db:
            db.close()