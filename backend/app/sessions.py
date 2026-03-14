"""
Session management for multi-user platform.
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from app.vectorstore.metadata_db import User, UserSession, get_session
from app.utils.logger import app_logger


class SessionManager:
    """Manage user sessions without password authentication."""

    SESSION_EXPIRY_HOURS = 24

    @staticmethod
    def create_user(username: str) -> Tuple[str, str]:
        """
        Create a new user and session.

        Args:
            username: Display name for user

        Returns:
            Tuple of (user_id, session_token)
        """
        db_session = get_session()
        try:
            user_id = str(uuid.uuid4())
            session_token = str(uuid.uuid4())

            # Create user
            user = User(user_id=user_id, username=username)
            db_session.add(user)
            db_session.flush()  # Get the ID

            # Create session
            session = UserSession(
                user_id=user.id,
                session_token=session_token,
                expires_at=datetime.now()
                + timedelta(hours=SessionManager.SESSION_EXPIRY_HOURS),
            )
            db_session.add(session)
            db_session.commit()

            app_logger.info(f"Created user {username} with session {session_token[:8]}...")
            return user_id, session_token
        except Exception as e:
            db_session.rollback()
            app_logger.error(f"Error creating user: {e}")
            raise
        finally:
            db_session.close()

    @staticmethod
    def validate_session(session_token: str) -> Optional[str]:
        """
        Validate session token and return user_id if valid.

        Args:
            session_token: Session token to validate

        Returns:
            User ID if valid, None otherwise
        """
        db_session = get_session()
        try:
            session = (
                db_session.query(UserSession)
                .filter(
                    UserSession.session_token == session_token,
                    UserSession.is_active == True,
                    UserSession.expires_at > datetime.now(),
                )
                .first()
            )

            if session:
                # Update last activity
                session.last_activity = datetime.now()
                db_session.commit()

                # Get user_id from related user
                user = session.user
                return user.user_id
            return None
        except Exception as e:
            app_logger.error(f"Error validating session: {e}")
            return None
        finally:
            db_session.close()

    @staticmethod
    def get_user_by_session(session_token: str) -> Optional[dict]:
        """
        Get user details from session token.

        Args:
            session_token: Session token

        Returns:
            User info dict or None
        """
        db_session = get_session()
        try:
            session = (
                db_session.query(UserSession)
                .filter(
                    UserSession.session_token == session_token,
                    UserSession.is_active == True,
                    UserSession.expires_at > datetime.now(),
                )
                .first()
            )

            if session:
                user = session.user
                return {
                    "user_id": user.user_id,
                    "username": user.username,
                    "created_at": user.created_at.isoformat(),
                    "session_expires_at": session.expires_at.isoformat(),
                }
            return None
        except Exception as e:
            app_logger.error(f"Error getting user: {e}")
            return None
        finally:
            db_session.close()

    @staticmethod
    def get_user_id_from_token(session_token: str) -> Optional[int]:
        """
        Get database user ID from session token.

        Args:
            session_token: Session token

        Returns:
            Database user ID or None
        """
        db_session = get_session()
        try:
            session = (
                db_session.query(UserSession)
                .filter(
                    UserSession.session_token == session_token,
                    UserSession.is_active == True,
                    UserSession.expires_at > datetime.now(),
                )
                .first()
            )
            if session:
                return session.user_id
            return None
        except Exception as e:
            app_logger.error(f"Error getting user ID: {e}")
            return None
        finally:
            db_session.close()

    @staticmethod
    def invalidate_session(session_token: str) -> bool:
        """
        Invalidate/logout a session.

        Args:
            session_token: Session token to invalidate

        Returns:
            True if successful
        """
        db_session = get_session()
        try:
            session = db_session.query(UserSession).filter(
                UserSession.session_token == session_token
            ).first()

            if session:
                session.is_active = False
                db_session.commit()
                app_logger.info(f"Invalidated session {session_token[:8]}...")
                return True
            return False
        except Exception as e:
            db_session.rollback()
            app_logger.error(f"Error invalidating session: {e}")
            return False
        finally:
            db_session.close()

    @staticmethod
    def refresh_session(session_token: str) -> bool:
        """
        Extend session expiry.

        Args:
            session_token: Session token to refresh

        Returns:
            True if successful
        """
        db_session = get_session()
        try:
            session = db_session.query(UserSession).filter(
                UserSession.session_token == session_token,
                UserSession.is_active == True,
            ).first()

            if session:
                session.expires_at = datetime.now() + timedelta(
                    hours=SessionManager.SESSION_EXPIRY_HOURS
                )
                session.last_activity = datetime.now()
                db_session.commit()
                app_logger.info(f"Refreshed session {session_token[:8]}...")
                return True
            return False
        except Exception as e:
            db_session.rollback()
            app_logger.error(f"Error refreshing session: {e}")
            return False
        finally:
            db_session.close()
