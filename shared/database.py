from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from shared.models import Base, User
import secrets
import string
from config import DATABASE_NAME


class DatabaseManager:
    def __init__(self, database_url=f"sqlite:///{DATABASE_NAME}"):
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def init_db(self):
        """Initialize database tables"""
        Base.metadata.create_all(bind=self.engine)

    def get_session(self):
        """Get database session"""
        return self.SessionLocal()

    def create_user(self, telegram_id, telegram_username, email=None):
        """Create a new unverified user"""
        session = self.get_session()
        try:
            # Check if user already exists
            existing_user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if existing_user:
                return existing_user

            user = User(
                telegram_id=telegram_id,
                telegram_username=telegram_username,
                email=email,
                username_slug=None,  # Will be generated on verification
                is_verified=False
            )

            session.add(user)
            session.commit()
            session.refresh(user)
            return user
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def verify_user(self, telegram_id):
        """Verify a user and generate login credentials"""
        session = self.get_session()
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if not user:
                return None

            # Generate username slug
            username_slug = user.generate_username_slug()

            # Check for uniqueness and handle duplicates
            base_slug = username_slug
            counter = 1
            while session.query(User).filter_by(username_slug=username_slug).first():
                username_slug = f"{base_slug}_{counter}"
                counter += 1

            # Generate temporary password
            temp_password = self.generate_temp_password()

            user.username_slug = username_slug
            user.set_password(temp_password)
            user.verify_user()

            session.commit()
            return {
                'user': user,
                'temp_password': temp_password,
                'username': username_slug
            }
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def generate_temp_password(self, length=12):
        """Generate a temporary password"""
        characters = string.ascii_letters + string.digits
        return ''.join(secrets.choice(characters) for _ in range(length))

    def change_password(self, username_slug, new_password):
        """Change user password"""
        session = self.get_session()
        try:
            user = session.query(User).filter_by(username_slug=username_slug).first()
            if user:
                user.set_password(new_password)
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_user_by_telegram_id(self, telegram_id):
        """Get user by Telegram ID"""
        session = self.get_session()
        try:
            return session.query(User).filter_by(telegram_id=telegram_id).first()
        finally:
            session.close()

    def get_user_by_username(self, username_slug):
        """Get user by username slug"""
        session = self.get_session()
        try:
            return session.query(User).filter_by(username_slug=username_slug).first()
        finally:
            session.close()

    def get_verified_users(self):
        """Get all verified users"""
        session = self.get_session()
        try:
            return session.query(User).filter_by(is_verified=True).all()
        finally:
            session.close()

    def get_unverified_users(self):
        """Get all unverified users"""
        session = self.get_session()
        try:
            return session.query(User).filter_by(is_verified=False).all()
        finally:
            session.close()
