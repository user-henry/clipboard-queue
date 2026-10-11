"""
Clipboard Queue - 安全模块
使用标准库 PBKDF2-HMAC-SHA256 进行密码哈希，不依赖任何第三方加密库。
密码记录写入 settings 文件（%APPDATA%/ClipboardQueue/settings.json），
绝不写入数据文件（queue_data.json），密码本身绝不记录/显示/落盘明文。
"""

import hashlib
import hmac
import secrets
import threading


class Security:
    """密码设置 / 校验 / 清除。"""

    ALGO = "pbkdf2_sha256"
    ITERATIONS = 200000
    KEY = "password"
    MIN_LENGTH = 4

    def __init__(self, settings=None):
        """
        settings: AppSettings 实例；为 None 时自动创建一个。
        """
        if settings is None:
            from app_settings import AppSettings
            settings = AppSettings()
        self._settings = settings
        self._lock = threading.RLock()

    # ── 对外接口 ──

    def has_password(self):
        """是否已设置访问密码。"""
        rec = self._get_record()
        return bool(rec and rec.get("salt") and rec.get("hash"))

    def set_password(self, pw):
        """设置新密码（最少 4 位）。成功返回 True。"""
        pw = pw or ""
        if len(pw) < self.MIN_LENGTH:
            return False
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, self.ITERATIONS)
        record = {
            "algo": self.ALGO,
            "iterations": self.ITERATIONS,
            "salt": salt.hex(),
            "hash": digest.hex(),
        }
        with self._lock:
            self._settings.set(self.KEY, record)
        return True

    def verify_password(self, pw):
        """校验密码是否正确。"""
        rec = self._get_record()
        if not rec:
            return False
        try:
            salt = bytes.fromhex(rec.get("salt", ""))
            expected = bytes.fromhex(rec.get("hash", ""))
            iterations = int(rec.get("iterations", self.ITERATIONS))
            digest = hashlib.pbkdf2_hmac("sha256", (pw or "").encode("utf-8"), salt, iterations)
            return hmac.compare_digest(digest, expected)
        except Exception:
            return False

    def clear_password(self):
        """清除已设置的访问密码。"""
        with self._lock:
            self._settings.set(self.KEY, None)

    # ── 内部 ──

    def _get_record(self):
        try:
            rec = self._settings.get(self.KEY)
            return rec if isinstance(rec, dict) else None
        except Exception:
            return None
