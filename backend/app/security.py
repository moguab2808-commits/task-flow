import hashlib
import hmac
import secrets

from app.config import session_secret

_N, _R, _P = 2**14, 8, 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    # 해시가 없는 계정(이전용 계정)은 항상 실패한다.
    if not stored:
        return False
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p)
        )
        return hmac.compare_digest(actual, bytes.fromhex(digest))
    except ValueError:
        return False


def new_session_id() -> str:
    return secrets.token_urlsafe(32)


def _sign(session_id: str) -> str:
    return hmac.new(session_secret().encode(), session_id.encode(), "sha256").hexdigest()


def sign_session_id(session_id: str) -> str:
    return f"{session_id}.{_sign(session_id)}"


def read_session_cookie(value: str | None) -> str | None:
    """서명이 맞으면 세션 id 를, 아니면 None 을 돌려준다."""
    if not value or "." not in value:
        return None
    session_id, _, signature = value.rpartition(".")
    if not session_id or not hmac.compare_digest(signature, _sign(session_id)):
        return None
    return session_id
