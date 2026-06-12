"""
Clipboard Queue - 剪贴板读写辅助
"""

import pyperclip
import time
import threading


class ClipboardHelper:
    """剪贴板读写 + 备份恢复"""

    def __init__(self):
        self._backup = None
        self._restore_timer = None

    def read(self):
        """读取当前剪贴板文本内容"""
        try:
            text = pyperclip.paste()
            return text if text else ""
        except Exception:
            return ""

    def write(self, text):
        """写入文本到剪贴板"""
        try:
            pyperclip.copy(text)
            return True
        except Exception:
            return False

    def save_backup(self):
        """备份当前剪贴板内容"""
        self._backup = self.read()

    def restore(self):
        """恢复之前备份的剪贴板内容"""
        if self._backup is not None:
            time.sleep(0.1)  # 微小延迟确保粘贴操作完成
            self.write(self._backup)
            self._backup = None

    def restore_after_delay(self, delay=0.8):
        """延迟恢复剪贴板（避免干扰当前粘贴操作）"""
        if self._restore_timer:
            self._restore_timer.cancel()
        self._restore_timer = threading.Timer(delay, self.restore)
        self._restore_timer.daemon = True
        self._restore_timer.start()
