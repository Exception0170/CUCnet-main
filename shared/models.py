from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.sql import func
import re
from werkzeug.security import generate_password_hash, check_password_hash

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    telegram_username = Column(String(100), nullable=True)
    email = Column(String(120), nullable=True)
    
    # Authentication fields
    username_slug = Column(String(100), unique=True, nullable=True)
    password_hash = Column(String(255), nullable=True)
    
    # Verification status
    is_verified = Column(Boolean, default=False)
    verified_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if the provided password matches the hash"""
        return check_password_hash(self.password_hash, password)
    
    def generate_username_slug(self):
        """Generate a slugified username from Telegram username"""
        if self.telegram_username:
            # Remove @ symbol if present and slugify
            username = self.telegram_username.lstrip('@')
            # Replace non-alphanumeric characters with underscores
            slug = re.sub(r'[^a-zA-Z0-9_]', '_', username)
            # Convert to lowercase
            slug = slug.lower()
            return slug
        return None
    
    def verify_user(self):
        """Mark user as verified"""
        self.is_verified = True
        self.verified_at = datetime.now()
    
    def __repr__(self):
        return f'<User {self.telegram_username} ({self.telegram_id})>'