"""Password, session, and resource-authorization helpers."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets

from fastapi import Depends, HTTPException, Request, status
from pwdlib import PasswordHash
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import AuthSession, Novel, User

SESSION_COOKIE = "novel_session"
_password_hash = PasswordHash.recommended()
_dummy_hash = _password_hash.hash("not-a-real-password")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_email(email: str) -> str:
    value = email.strip().lower()
    if value.count("@") != 1 or value.startswith("@") or value.endswith("@"):
        raise HTTPException(status_code=422, detail="请输入有效的邮箱地址。")
    return value


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


def invalid_credentials(db: Session, password: str) -> None:
    # Keep failed-login timing similar when an account does not exist.
    verify_password(password, _dummy_hash)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="邮箱或密码错误。",
    )


def is_configured_admin(email: str) -> bool:
    return email in get_settings().admin_email_set


def sync_admin_role(db: Session, user: User) -> None:
    expected = is_configured_admin(user.email)
    if user.is_admin != expected:
        user.is_admin = expected


def claim_legacy_novels(db: Session, user: User) -> None:
    """Assign unowned historical novels exactly once to the first administrator."""
    if not user.is_admin:
        return
    existing_admin = db.scalars(
        select(User.id).where(User.is_admin.is_(True), User.id != user.id).limit(1)
    ).first()
    if existing_admin is None:
        db.execute(update(Novel).where(Novel.owner_id.is_(None)).values(owner_id=user.id))


def create_session(db: Session, user: User) -> str:
    settings = get_settings()
    db.execute(delete(AuthSession).where(AuthSession.expires_at <= utcnow()))
    token = secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=sha256(token.encode()).hexdigest(),
            expires_at=utcnow() + timedelta(days=settings.auth_session_days),
        )
    )
    return token


def set_session_cookie(response, token: str) -> None:
    settings = get_settings()
    max_age = settings.auth_session_days * 24 * 60 * 60
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=settings.auth_cookie_secure,
        path="/",
    )


def clear_session_cookie(response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录。")
    session = db.scalars(
        select(AuthSession)
        .where(AuthSession.token_hash == sha256(token.encode()).hexdigest())
        .where(AuthSession.expires_at > utcnow())
    ).first()
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已过期。")
    sync_admin_role(db, session.user)
    return session.user


def require_novel_access(db: Session, user: User, novel: Novel | None) -> Novel:
    if novel is None or (not user.is_admin and novel.owner_id != user.id):
        raise HTTPException(status_code=404, detail="小说不存在。")
    return novel
