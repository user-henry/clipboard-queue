"""
Clipboard Queue - 队列管理器
实现先进先出 (FIFO) 队列逻辑 + JSON 持久化
"""

from collections import deque
import datetime
import json
import os
import threading


class QueueManager:
    """FIFO 剪贴板队列管理器"""

    def __init__(self, save_path=None):
        self._queue = deque()
        self._lock = threading.Lock()
        if save_path is None:
            appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
            save_dir = os.path.join(appdata, "ClipboardQueue")
            os.makedirs(save_dir, exist_ok=True)
            save_path = os.path.join(save_dir, "queue_data.json")
        self._save_path = save_path
        self._load()

    def enqueue(self, content, content_type="text"):
        """
        将内容加入队列尾部
        返回: {"type", "content", "preview", "time"}
        """
        with self._lock:
            preview = content[:50] + ("..." if len(content) > 50 else "")
            item = {
                "type": content_type,
                "content": content,
                "preview": preview,
                "time": datetime.datetime.now().strftime("%H:%M:%S"),
            }
            self._queue.append(item)
            self._save()
            return item

    def dequeue(self):
        """从队列头部取出并移除内容"""
        with self._lock:
            if self._queue:
                item = self._queue.popleft()
                self._save()
                return item
            return None

    def clear(self):
        """清空队列"""
        with self._lock:
            self._queue.clear()
            self._save()

    def count(self):
        """返回队列长度"""
        return len(self._queue)

    def is_empty(self):
        """队列是否为空"""
        return len(self._queue) == 0

    def get_all(self):
        """获取所有队列项（用于显示列表）"""
        with self._lock:
            return list(self._queue)

    def remove_at(self, index):
        """删除指定索引的项"""
        with self._lock:
            if 0 <= index < len(self._queue):
                items = list(self._queue)
                removed = items.pop(index)
                self._queue = deque(items)
                self._save()
                return removed
            return None

    def _save(self):
        """保存队列到文件（%APPDATA%/ClipboardQueue/queue_data.json）"""
        try:
            data = {
                "items": list(self._queue),
                "saved_at": datetime.datetime.now().isoformat(),
            }
            with open(self._save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load(self):
        """从文件加载队列"""
        try:
            if os.path.exists(self._save_path):
                with open(self._save_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._queue = deque(data.get("items", []))
        except Exception:
            pass
