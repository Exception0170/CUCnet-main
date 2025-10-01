from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import re
from werkzeug.security import generate_password_hash, check_password_hash

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    telegram_username = Column(String(100), nullable=True)

    # Authentication fields
    username_slug = Column(String(100), unique=True, nullable=True)
    password_hash = Column(String(255), nullable=True)
    site_password = Column(String(100), nullable=True)

    # User status - use is_verified for active users, ignored for rejected
    is_verified = Column(Boolean, default=False)
    ignored = Column(Boolean, default=False)  # True if user is rejected/banned
    verified_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    profiles = relationship("Profile", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_username_slug(self):
        if self.telegram_username:
            username = self.telegram_username.lstrip('@')
            slug = re.sub(r'[^a-zA-Z0-9_]', '_', username)
            return slug.lower()
        return f"user_{self.telegram_id}"

    def verify_user(self):
        self.is_verified = True
        self.ignored = False
        self.verified_at = datetime.now()

    def ban_user(self):
        self.ignored = True
        self.is_verified = False

    def unban_user(self):
        self.ignored = False

    def __repr__(self):
        return f'<User {self.telegram_username} ({self.telegram_id})>'


class Profile(Base):
    __tablename__ = 'profiles'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    profile_name = Column(String(100), nullable=False)
    profile_type = Column(String(20), nullable=False)  # 'Personal' or 'Webserver'

    # WireGuard specific fields
    private_key = Column(String(255), nullable=False)
    public_key = Column(String(255), nullable=False)
    assigned_ip = Column(String(15), nullable=False)  # e.g., "10.8.10.1"
    config_content = Column(Text, nullable=False)  # Full .conf file content

    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="profiles")

    def __repr__(self):
        return f'<Profile {self.profile_name} ({self.profile_type}) - {self.assigned_ip}>'