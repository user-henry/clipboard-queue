"""
Clipboard Queue - 应用设置
JSON 持久化到 %APPDATA%/ClipboardQueue/settings.json。
原子写入（tmp + os.replace）、线程安全、深合并默认值（未知/旧键得以保留）。
"""

import copy
import json
import os
import threading


class AppSettings:
    """应用设置管理（本地 JSON 持久化）。"""

    DEFAULTS = {
        "general": {
            "auto_start": False,               # 开机自启
            "single_instance": True,           # 单实例
            "show_notifications": True,        # 显示通知
            "notification_sound": False,       # 通知声音
            "confirm_before_delete": True,     # 删除前确认
        },
        "queue": {
            "persist": True,                   # 本地保存记录（关闭后仅内存保留，退出即清空）
            "max_items": 0,                    # 0 = 不限制
            "dedupe": False,                   # 入队去重
            "pop_direction": "head",           # head=队首 / tail=队尾
            "clear_clipboard_after_paste": False,
            "restore_user_clipboard_after_paste": True,
            "restore_delay_seconds": 0.8,
        },
        "security": {
            "unlock_ttl_seconds": 300,         # 解锁缓存窗口（秒）
            "auto_clear_clipboard_seconds": 0, # 0 = 关闭自动清空
            "clear_secret_on_exit": False,     # 退出时清空剪贴板
        },
        "hotkeys": {
            "copy": "ctrl+alt+c",              # 加入队列
            "paste": "ctrl+alt+v",             # 从队列粘贴
            "clear": "ctrl+alt+q",             # 清空队列
            "show": "ctrl+alt+s",              # 打开主窗口
        },
        "ui": {
            "glass_enabled": True,             # 原生毛玻璃背景
            "glass_mode": "blur",              # blur（平滑）/ acrylic（更亮）
            "glass_alpha": 0.97,               # 窗口整体不透明度
            "glass_tint": "#0B1020",           # 玻璃染色
            "glass_tint_alpha": 112,           # 染色浓度 0-255
        },
    }

    def __init__(self, path=None):
        if path is None:
            appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
            save_dir = os.path.join(appdata, "ClipboardQueue")
            os.makedirs(save_dir, exist_ok=True)
            path = os.path.join(save_dir, "settings.json")
        self._path = path
        self._lock = threading.RLock()
        self._data = {}
        self.load()

    # ── 持久化 ──

    def load(self):
        """从磁盘加载，并与默认值深合并（未知键保留）。"""
        with self._lock:
            loaded = {}
            try:
                if os.path.exists(self._path):
                    with open(self._path, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                if not isinstance(loaded, dict):
                    loaded = {}
            except Exception:
                loaded = {}
            self._data = self._deep_merge(copy.deepcopy(self.DEFAULTS), loaded)
            self._migrate_dotted_keys()

    def save(self):
        """原子写入到磁盘。"""
        with self._lock:
            try:
                tmp = self._path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, ensure_ascii=False, indent=2)
                os.replace(tmp, self._path)
                return True
            except Exception:
                return False

    # ── 读写接口（支持点号路径，如 "general.auto_start"）──

    def get(self, key, default=None):
        with self._lock:
            return self._get_path(self._data, key, default)

    def set(self, key, value):
        with self._lock:
            self._set_path(self._data, key, value)
            self.save()

    def update(self, mapping):
        """批量更新（支持 "a.b" 点号路径，也支持嵌套 dict 深合并）。"""
        with self._lock:
            for k, v in (mapping or {}).items():
                if isinstance(k, str) and "." in k:
                    self._set_path(self._data, k, v)
                elif isinstance(v, dict) and isinstance(self._data.get(k), dict):
                    self._data[k] = self._deep_merge(self._data[k], v)
                else:
                    self._data[k] = v
            self.save()

    def reset(self):
        """恢复默认设置（保留已设置的访问密码）。"""
        with self._lock:
            password = self._data.get("password")
            self._data = copy.deepcopy(self.DEFAULTS)
            if password is not None:
                self._data["password"] = password
            self.save()

    def as_dict(self):
        """返回设置的深拷贝。"""
        with self._lock:
            return copy.deepcopy(self._data)

    # ── 内部辅助 ──

    def _migrate_dotted_keys(self):
        """
        迁移历史版本误写的顶层点号键（如 "queue.max_items"）为嵌套结构，
        否则设置页保存的偏好会被写到顶层、读取时永远是默认值。
        """
        dotted = [k for k in list(self._data.keys())
                  if isinstance(k, str) and "." in k]
        if not dotted:
            return False
        for key in dotted:
            value = self._data.pop(key)
            self._set_path(self._data, key, value)
        self.save()
        return True

    @staticmethod
    def _deep_merge(base, override):
        result = copy.deepcopy(base)
        for k, v in (override or {}).items():
            if isinstance(v, dict) and isinstance(result.get(k), dict):
                result[k] = AppSettings._deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    @staticmethod
    def _get_path(data, key, default):
        if key is None:
            return data
        parts = key.split(".") if isinstance(key, str) else [key]
        cur = data
        for p in parts:
            if isinstance(cur, dict) and p in cur:
                cur = cur[p]
            else:
                return default
        return cur

    @staticmethod
    def _set_path(data, key, value):
        parts = key.split(".") if isinstance(key, str) else [key]
        cur = data
        for p in parts[:-1]:
            nxt = cur.get(p)
            if not isinstance(nxt, dict):
                nxt = {}
                cur[p] = nxt
            cur = nxt
        cur[parts[-1]] = value
