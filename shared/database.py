# database.py
import logging
import ipaddress
from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from shared.models import Base, User, Profile
from shared.wireguard import WireGuardManager
import secrets
import string
from config import DATABASE_NAME, MAX_PROFILES_PER_USER

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, database_url=f"sqlite:///{DATABASE_NAME}"):
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.wireguard = WireGuardManager()
        self.init_db()

    def init_db(self):
        """Initialize database tables"""
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database initialized")

    def get_session(self):
        """Get database session"""
        return self.SessionLocal()

    # User management methods
    def add_user(self, telegram_id, telegram_username):
        """Add a new user (unverified by default)"""
        session = self.get_session()
        try:
            existing_user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if existing_user:
                return existing_user

            user = User(
                telegram_id=telegram_id,
                telegram_username=telegram_username,
                is_verified=False,
                ignored=False
            )

            session.add(user)
            session.commit()
            session.refresh(user)
            logger.info(f"User added: {telegram_id}, {telegram_username}")
            return user
        except Exception as e:
            session.rollback()
            logger.error(f"Error adding user: {e}")
            raise e
        finally:
            session.close()

    def get_user(self, telegram_id):
        """Get user by Telegram ID"""
        session = self.get_session()
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if user:
                return {
                    'id': user.id,
                    'telegram_id': user.telegram_id,
                    'username': user.telegram_username,
                    'is_verified': user.is_verified,
                    'ignored': user.ignored,
                    'site_password': user.site_password
                }
            return None
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            return None
        finally:
            session.close()

    def approve_user(self, telegram_id):
        """Approve user (make verified)"""
        session = self.get_session()
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if user:
                user.verify_user()
                # Generate site password if not exists
                if not user.site_password:
                    user.site_password = self.generate_password()
                session.commit()
                logger.info(f"User {telegram_id} approved")
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Error approving user: {e}")
            return False
        finally:
            session.close()

    def reject_user(self, telegram_id):
        """Reject user (mark as ignored)"""
        session = self.get_session()
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if user:
                user.ban_user()
                session.commit()
                logger.info(f"User {telegram_id} rejected")
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Error rejecting user: {e}")
            return False
        finally:
            session.close()

    def unban_user(self, telegram_id):
        """Unban user (remove ignored status)"""
        session = self.get_session()
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if user:
                user.unban_user()
                session.commit()
                logger.info(f"User {telegram_id} unbanned")
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Error unbanning user: {e}")
            return False
        finally:
            session.close()

    def get_pending_users(self):
        """Get all pending users (not verified and not ignored)"""
        session = self.get_session()
        try:
            users = session.query(User).filter(
                and_(User.is_verified == False, User.ignored == False)
            ).all()
            return [{
                'user_id': user.telegram_id,
                'username': user.telegram_username
            } for user in users]
        except Exception as e:
            logger.error(f"Error getting pending users: {e}")
            return []
        finally:
            session.close()

    def get_ignored_users(self):
        """Get all ignored users"""
        session = self.get_session()
        try:
            users = session.query(User).filter_by(ignored=True).all()
            return [{
                'user_id': user.telegram_id,
                'username': user.telegram_username
            } for user in users]
        except Exception as e:
            logger.error(f"Error getting ignored users: {e}")
            return []
        finally:
            session.close()

    def set_site_password(self, telegram_id, password):
        """Set site password for user"""
        session = self.get_session()
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if user:
                user.site_password = password
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Error setting site password: {e}")
            return False
        finally:
            session.close()

    def set_user_password(self, telegram_id, password):
        """Set hashed password for user using set_password() method"""
        session = self.get_session()
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if user:
                user.set_password(password)
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Error setting user password: {e}")
            return False
        finally:
            session.close()

    def check_user_password(self, telegram_id, password):
        """Check if provided password matches stored hash"""
        session = self.get_session()
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if user and user.password_hash:
                return user.check_password(password)
            return False
        except Exception as e:
            logger.error(f"Error checking user password: {e}")
            return False
        finally:
            session.close()

    # Profile management methods with WireGuard
    def add_profile(self, telegram_id, profile_name, profile_type):
        """Add a new WireGuard profile for user"""
        session = self.get_session()
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if not user:
                return False, "User not found"

            # Check profile limit
            profile_count = self.get_profile_count(telegram_id)
            if profile_count >= MAX_PROFILES_PER_USER:
                return False, f"Maximum {MAX_PROFILES_PER_USER} profiles allowed"

            # Check if profile name already exists for this user
            existing_profile = session.query(Profile).filter(
                and_(
                    Profile.user_id == user.id,
                    Profile.profile_name == profile_name
                )
            ).first()

            if existing_profile:
                return False, "Profile name already exists"

            # Generate WireGuard keys
            private_key, public_key = self.wireguard.generate_keypair()

            # Assign IP based on profile type
            assigned_ip = self._get_next_available_ip(profile_type, session)
            if not assigned_ip:
                return False, "No available IP addresses"

            # Generate config content
            config_content = self.wireguard.generate_config_content(
                private_key, assigned_ip
            )

            # Create profile
            profile = Profile(
                user_id=user.id,
                profile_name=profile_name,
                profile_type=profile_type,
                private_key=private_key,
                public_key=public_key,
                assigned_ip=assigned_ip,
                config_content=config_content
            )

            session.add(profile)
            session.commit()

            # Add peer to WireGuard server
            if not self.wireguard.add_peer_to_server(public_key, assigned_ip):
                session.rollback()
                return False, "Failed to add peer to WireGuard server"

            logger.info(f"Profile added: {profile_name} for user {telegram_id} with IP {assigned_ip}")
            return True, "Profile created successfully"
        except IntegrityError:
            session.rollback()
            return False, "Profile creation failed"
        except Exception as e:
            session.rollback()
            logger.error(f"Error adding profile: {e}")
            return False, f"Error: {str(e)}"
        finally:
            session.close()

    def _get_next_available_ip(self, profile_type: str, session) -> str:
        """Get next available IP based on profile type rules"""
        if profile_type == "Webserver":
            # 10.8.10.0/24 - 10.8.25.0/24
            subnet_start = 10
            subnet_end = 25
            base_ip = "10.8.{}.{}"
        else:  # Personal
            # 10.8.100.0/24 - 10.8.255.0/24
            subnet_start = 100
            subnet_end = 255
            base_ip = "10.8.{}.{}"

        # Try to find available IP
        for subnet in range(subnet_start, subnet_end + 1):
            for host in range(1, 255):  # Skip .0 (network) and .255 (broadcast)
                test_ip = base_ip.format(subnet, host)

                # Check if IP is already assigned
                existing_profile = session.query(Profile).filter_by(assigned_ip=test_ip).first()
                if not existing_profile:
                    return test_ip

        return None

    def get_user_profiles(self, telegram_id):
        """Get all profiles for a user"""
        session = self.get_session()
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if not user:
                return []

            profiles = session.query(Profile).filter_by(user_id=user.id).all()
            return [{
                'id': p.id,
                'profile_name': p.profile_name,
                'profile_type': p.profile_type,
                'assigned_ip': p.assigned_ip,
                'public_key': p.public_key,
                'created_at': p.created_at
            } for p in profiles]
        except Exception as e:
            logger.error(f"Error getting user profiles: {e}")
            return []
        finally:
            session.close()

    def get_profile_count(self, telegram_id):
        """Get profile count for a user"""
        session = self.get_session()
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if not user:
                return 0
            return session.query(Profile).filter_by(user_id=user.id).count()
        except Exception as e:
            logger.error(f"Error getting profile count: {e}")
            return 0
        finally:
            session.close()

    def get_profile_config(self, profile_id):
        """Get profile config content"""
        session = self.get_session()
        try:
            profile = session.query(Profile).filter_by(id=profile_id).first()
            if profile:
                return profile.config_content
            return None
        except Exception as e:
            logger.error(f"Error getting profile config: {e}")
            return None
        finally:
            session.close()

    def delete_profile(self, profile_id):
        """Delete profile and remove from WireGuard"""
        session = self.get_session()
        try:
            profile = session.query(Profile).filter_by(id=profile_id).first()
            if profile:
                # Remove from WireGuard server first
                self.wireguard.remove_peer_from_server(profile.public_key)
                # Then delete from database
                session.delete(profile)
                session.commit()
                logger.info(f"Profile {profile_id} deleted")
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Error deleting profile: {e}")
            return False
        finally:
            session.close()

    def rename_profile(self, profile_id, new_name):
        """Rename a profile"""
        session = self.get_session()
        try:
            profile = session.query(Profile).filter_by(id=profile_id).first()
            if not profile:
                return False

            # Check if new name already exists for this user
            existing_profile = session.query(Profile).filter(
                and_(
                    Profile.user_id == profile.user_id,
                    Profile.profile_name == new_name,
                    Profile.id != profile_id
                )
            ).first()

            if existing_profile:
                return False

            profile.profile_name = new_name
            session.commit()
            logger.info(f"Profile {profile_id} renamed to {new_name}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Error renaming profile: {e}")
            return False
        finally:
            session.close()

    # Utility methods
    def generate_password(self, length=12):
        """Generate a random password"""
        characters = string.ascii_letters + string.digits
        return ''.join(secrets.choice(characters) for _ in range(length))