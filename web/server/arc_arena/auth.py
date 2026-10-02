from __future__ import annotations

import hashlib
import os
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .db import connect

COOKIE_NAME = "arc_session"
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 1 << 14, 8, 1


class AuthError(Exception):
    def __init__(self, message: str, status: int = 401, retry_after: int = 0):
        super().__init__(message)
        self.message = message
        self.status = status
        self.retry_after = retry_after


@dataclass
class User:
    id: int
    username: str
    is_admin: bool


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt,
        n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32,
    )
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.scrypt(
            password.encode("utf-8"), salt=bytes.fromhex(salt_hex),
            n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32,
        )
        return secrets.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AuthManager:
    """用户/会话管理：scrypt 口令 + SQLite 会话 + 失败锁定。"""

    LOCKOUT_THRESHOLD = 5
    LOCKOUT_SECONDS = 60

    def __init__(self, db_path, session_days: int = 7):
        self.db_path = db_path
        self.session_days = session_days
        self._fails: dict[str, tuple[int, float]] = {}

    # ---- users -----------------------------------------------------
    def create_user(self, username: str, password: str, is_admin: bool = False) -> User:
        username = username.strip()
        if not (2 <= len(username) <= 32) or not username.replace("_", "").replace("-", "").isalnum():
            raise AuthError("用户名需为 2-32 位字母/数字/下划线/连字符", status=400)
        if len(password) < 6:
            raise AuthError("密码至少 6 位", status=400)
        conn = connect(self.db_path)
        try:
            conn.execute(
                "INSERT INTO users(username, password_hash, is_admin, active, created_at) "
                "VALUES(?,?,?,?,?)",
                (username, hash_password(password), int(is_admin), 1, _now().isoformat()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT id, username, is_admin FROM users WHERE username=?", (username,)
            ).fetchone()
            return User(id=row["id"], username=row["username"], is_admin=bool(row["is_admin"]))
        finally:
            conn.close()

    def set_password(self, username: str, password: str) -> None:
        conn = connect(self.db_path)
        try:
            cur = conn.execute(
                "UPDATE users SET password_hash=? WHERE username=?",
                (hash_password(password), username),
            )
            conn.commit()
            if cur.rowcount == 0:
                raise AuthError(f"no such user: {username}", status=404)
            # 改密后踢掉该用户全部会话
            uid = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()["id"]
            conn.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
            conn.commit()
        finally:
            conn.close()

    def set_active(self, username: str, active: bool) -> None:
        conn = connect(self.db_path)
        try:
            cur = conn.execute(
                "UPDATE users SET active=? WHERE username=?", (int(active), username)
            )
            conn.commit()
            if cur.rowcount == 0:
                raise AuthError(f"no such user: {username}", status=404)
        finally:
            conn.close()

    def list_users(self) -> list[dict]:
        conn = connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT username, is_admin, active, created_at FROM users ORDER BY id"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ---- sessions ---------------------------------------------------
    def login(self, username: str, password: str) -> tuple[User, str]:
        username = username.strip()
        now = time.monotonic()
        fails, until = self._fails.get(username, (0, 0.0))
        if until > now:
            raise AuthError(
                f"失败次数过多，{int(until - now) + 1}s 后再试",
                status=429,
                retry_after=int(until - now) + 1,
            )

        conn = connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT id, username, password_hash, is_admin, active FROM users WHERE username=?",
                (username,),
            ).fetchone()
        finally:
            conn.close()

        if row is None or not verify_password(password, row["password_hash"]) or not row["active"]:
            self._fails[username] = (fails + 1, 0.0)
            if fails + 1 >= self.LOCKOUT_THRESHOLD:
                self._fails[username] = (0, now + self.LOCKOUT_SECONDS)
            raise AuthError("用户名或密码错误", status=401)

        self._fails.pop(username, None)
        user = User(id=row["id"], username=row["username"], is_admin=bool(row["is_admin"]))
        token = secrets.token_urlsafe(32)
        expires = _now() + timedelta(days=self.session_days)
        conn = connect(self.db_path)
        try:
            conn.execute(
                "INSERT INTO sessions(token, user_id, created_at, expires_at) VALUES(?,?,?,?)",
                (token, user.id, _now().isoformat(), expires.isoformat()),
            )
            conn.commit()
        finally:
            conn.close()
        return user, token

    def session_user(self, token: str) -> User | None:
        if not token:
            return None
        conn = connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT s.token, u.id, u.username, u.is_admin, u.active, s.expires_at "
                "FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token=?",
                (token,),
            ).fetchone()
        finally:
            conn.close()
        if row is None or not row["active"]:
            return None
        try:
            if datetime.fromisoformat(row["expires_at"]) < _now():
                return None
        except ValueError:
            return None
        return User(id=row["id"], username=row["username"], is_admin=bool(row["is_admin"]))

    def logout(self, token: str) -> None:
        conn = connect(self.db_path)
        try:
            conn.execute("DELETE FROM sessions WHERE token=?", (token,))
            conn.commit()
        finally:
            conn.close()

    def purge_expired_sessions(self) -> None:
        conn = connect(self.db_path)
        try:
            conn.execute("DELETE FROM sessions WHERE expires_at < ?", (_now().isoformat(),))
            conn.commit()
        finally:
            conn.close()


def new_admin_token() -> str:
    return secrets.token_urlsafe(16)
