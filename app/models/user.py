# ------------------------------------------
# SQLAlchemy User model definition
# Represents registered application users
# - Stores UUID as primary key
# - Tracks name, email, hashed password, and creation timestamp
# ------------------------------------------

from sqlalchemy import Column, String, TIMESTAMP
from datetime import datetime
import uuid
from app.db.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
