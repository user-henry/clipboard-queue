"""
Clipboard Queue - 队列管理器
实现先进先出 (FIFO) 队列 + JSON 持久化 + 分类/标题/密码标记。
线程安全（RLock），所有写操作原子落盘（tmp + os.replace）。
兼容旧版数据格式并自动迁移，绝不丢数据。
"""

from collections import deque
import datetime
import json
import os
import threading
import uuid


def _default_category_color(name):
    """分类默认颜色（尽量复用主题模块，失败则本地降级）。"""
    try:
        from ui_theme import category_color
        return category_color(name)
    except Exception:
        colors = ["#3DE1FF", "#7C5CFF", "#35D07F", "#FFB020",
                  "#FF5C6C", "#FF7AC6", "#5C8AFF", "#FFD23F"]
        if not name:
            return colors[0]
        digest = 0
        for ch in str(name):
            digest = (digest * 31 + ord(ch)) & 0xFFFFFFFF
        return colors[digest % len(colors)]


class QueueManager:
    """FIFO 剪贴板队列管理器。"""

    DEFAULT_CATEGORY = "未分类"

    # 首次运行（或分类被清空）时自动建立的默认分类
    # locked=True 表示该分类下的条目需要访问密码才能复制/粘贴
    SEED_CATEGORIES = [
        ("未分类", False),
        ("密码", True),
        ("工作", False),
        ("代码", False),
        ("网址", False),
        ("临时", False),
    ]

    def __init__(self, save_path=None, settings=None):
        self._queue = deque()
        self._categories = []          # [{"name","color","locked"}]
        self._lock = threading.RLock()
        self._settings = settings      # 可选 AppSettings，用于 max_items/dedupe/pop_direction
        if save_path is None:
            appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
            save_dir = os.path.join(appdata, "ClipboardQueue")
            os.makedirs(save_dir, exist_ok=True)
            save_path = os.path.join(save_dir, "queue_data.json")
        self._save_path = save_path
        self._load()
        self._seed_categories()

    def _seed_categories(self):
        """没有任何分类时写入默认分类（含受密码保护的「密码」分类）。"""
        with self._lock:
            if self._categories:
                return False
            self._categories = [
                {"name": name, "color": _default_category_color(name), "locked": locked}
                for name, locked in self.SEED_CATEGORIES
            ]
            self._save()
            return True

    # ═══════════════════════════════════════════════════════════
    # 基础队列操作（保持原有语义）
    # ═══════════════════════════════════════════════════════════

    def enqueue(self, content, content_type="text", title=None,
                category=None, tags=None, secret=False):
        """
        将内容加入队列尾部。
        返回: 新条目 dict；去重命中时返回 None。
        """
        with self._lock:
            dedupe = self._get_setting("queue.dedupe", False)
            if dedupe:
                c = content or ""
                for it in self._queue:
                    if it.get("content") == c and it.get("type") == content_type:
                        return None

            item = self._normalize_item({
                "type": content_type,
                "content": content,
                "title": title,
                "category": category or self.DEFAULT_CATEGORY,
                "tags": tags,
                "secret": bool(secret),
            })
            self._queue.append(item)

            max_items = int(self._get_setting("queue.max_items", 0) or 0)
            if max_items > 0:
                while len(self._queue) > max_items:
                    self._queue.popleft()
            self._save()
            return item

    def dequeue(self):
        """从队列取出并移除内容（队首为默认，可配置队尾）。"""
        with self._lock:
            if not self._queue:
                return None
            direction = self._get_setting("queue.pop_direction", "head")
            item = self._queue.pop() if direction == "tail" else self._queue.popleft()
            self._save()
            return item

    def clear(self):
        """清空队列（保留分类定义）。"""
        with self._lock:
            self._queue.clear()
            self._save()

    def count(self):
        """返回队列长度。"""
        with self._lock:
            return len(self._queue)

    def is_empty(self):
        """队列是否为空。"""
        with self._lock:
            return len(self._queue) == 0

    def get_all(self):
        """获取所有队列项（浅拷贝，用于显示列表）。"""
        with self._lock:
            return list(self._queue)

    def remove_at(self, index):
        """删除指定索引的项。"""
        with self._lock:
            if 0 <= index < len(self._queue):
                items = list(self._queue)
                removed = items.pop(index)
                self._queue = deque(items)
                self._save()
                return removed
            return None

    # ═══════════════════════════════════════════════════════════
    # 条目操作
    # ═══════════════════════════════════════════════════════════

    def get_item(self, item_id):
        """按 id 获取条目（返回浅拷贝）。"""
        with self._lock:
            item = self._get_by_id(item_id)
            return dict(item) if item is not None else None

    def update_item(self, item_id, **fields):
        """按 id 更新条目字段。"""
        allowed = {"title", "content", "preview", "category",
                   "tags", "secret", "type", "created_at", "time"}
        with self._lock:
            item = self._get_by_id(item_id)
            if item is None:
                return None
            for k, v in fields.items():
                if k in allowed:
                    item[k] = v
            self._save()
            return item

    def remove_item(self, item_id):
        """按 id 删除条目。"""
        with self._lock:
            before = len(self._queue)
            self._queue = deque([it for it in self._queue if it.get("id") != item_id])
            removed = before - len(self._queue)
            if removed:
                self._save()
            return removed > 0

    def move_to_front(self, item_id):
        """将条目置顶到队首。"""
        with self._lock:
            for i, it in enumerate(self._queue):
                if it.get("id") == item_id:
                    item = self._queue[i]
                    del self._queue[i]
                    self._queue.appendleft(item)
                    self._save()
                    return True
            return False

    def is_protected(self, item):
        """条目是否受密码保护（单条 secret 或分类 locked）。"""
        if not item:
            return False
        if item.get("secret"):
            return True
        return self.category_locked(item.get("category"))

    # ═══════════════════════════════════════════════════════════
    # 分类
    # ═══════════════════════════════════════════════════════════

    def get_categories(self):
        """返回分类定义列表（浅拷贝）。"""
        with self._lock:
            return [dict(c) for c in self._categories]

    def get_category(self, name):
        with self._lock:
            for c in self._categories:
                if c.get("name") == name:
                    return dict(c)
            return None

    def category_locked(self, name):
        with self._lock:
            for c in self._categories:
                if c.get("name") == name:
                    return bool(c.get("locked"))
            return False

    def add_category(self, name, color=None, locked=False):
        """新增分类（已存在则更新颜色/锁定）。返回分类 dict。"""
        name = (name or "").strip() or self.DEFAULT_CATEGORY
        color = color or _default_category_color(name)
        with self._lock:
            for c in self._categories:
                if c.get("name") == name:
                    c["color"] = color
                    c["locked"] = bool(locked)
                    self._save()
                    return dict(c)
            cat = {"name": name, "color": color, "locked": bool(locked)}
            self._categories.append(cat)
            self._save()
            return dict(cat)

    def rename_category(self, old, new):
        """重命名分类，并同步更新条目所属分类。"""
        new = (new or "").strip()
        if not new:
            return False
        with self._lock:
            found = False
            for c in self._categories:
                if c.get("name") == old:
                    c["name"] = new
                    found = True
            if found:
                for it in self._queue:
                    if it.get("category") == old:
                        it["category"] = new
                self._save()
            return found

    def delete_category(self, name):
        """删除分类，条目回退到「未分类」。"""
        with self._lock:
            self._categories = [c for c in self._categories if c.get("name") != name]
            for it in self._queue:
                if it.get("category") == name:
                    it["category"] = self.DEFAULT_CATEGORY
            self._save()
            return True

    def set_category_locked(self, name, locked):
        """设置分类锁定状态。"""
        with self._lock:
            for c in self._categories:
                if c.get("name") == name:
                    c["locked"] = bool(locked)
                    self._save()
                    return True
            return False

    def counts_by_category(self):
        """统计每个分类的条目数量（含定义但为 0 的分类）。"""
        with self._lock:
            counts = {}
            for it in self._queue:
                c = it.get("category") or self.DEFAULT_CATEGORY
                counts[c] = counts.get(c, 0) + 1
            for c in self._categories:
                counts.setdefault(c.get("name"), 0)
            return counts

    def clear_category(self, name):
        """清空指定分类下的所有条目。返回移除数量。"""
        with self._lock:
            before = len(self._queue)
            self._queue = deque(
                [it for it in self._queue if it.get("category") != name]
            )
            removed = before - len(self._queue)
            if removed:
                self._save()
            return removed

    # ═══════════════════════════════════════════════════════════
    # 搜索 / 导入导出
    # ═══════════════════════════════════════════════════════════

    def search(self, query):
        """在标题/内容/分类/标签中模糊搜索。"""
        q = (query or "").strip().lower()
        with self._lock:
            if not q:
                return list(self._queue)
            results = []
            for it in self._queue:
                hay = " ".join([
                    str(it.get("title", "")),
                    str(it.get("content", "")),
                    str(it.get("category", "")),
                    " ".join(it.get("tags", []) or []),
                ]).lower()
                if q in hay:
                    results.append(it)
            return results

    def export_json(self, path):
        """导出全部数据到指定 JSON 文件。"""
        with self._lock:
            data = {
                "items": list(self._queue),
                "categories": [dict(c) for c in self._categories],
                "saved_at": datetime.datetime.now().isoformat(),
                "exported": True,
            }
            try:
                tmp = path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                os.replace(tmp, path)
                return True
            except Exception:
                return False

    def import_json(self, path):
        """从 JSON 文件导入（覆盖当前队列，合并分类）。返回导入条数。"""
        with self._lock:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                items, cats, saved_at = self._parse_raw(raw)
                imported = [self._normalize_item(it, saved_at) for it in items]
                imported = [it for it in imported if it]
                self._queue = deque(imported)
                existing = {c.get("name"): c for c in self._categories}
                for c in cats:
                    nc = self._normalize_category(c)
                    if nc:
                        existing[nc["name"]] = nc
                self._categories = list(existing.values())
                self._save()
                return len(imported)
            except Exception:
                return 0

    # ═══════════════════════════════════════════════════════════
    # 持久化 & 迁移
    # ═══════════════════════════════════════════════════════════

    def _save(self):
        """原子写入队列到文件。"""
        if not self._get_setting("queue.persist", True):
            return          # 已在设置中关闭本地保存：仅保留在内存中
        try:
            data = {
                "items": list(self._queue),
                "categories": [dict(c) for c in self._categories],
                "saved_at": datetime.datetime.now().isoformat(),
            }
            tmp = self._save_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._save_path)
        except Exception:
            # 持久化失败不应导致主流程崩溃
            pass

    def _load(self):
        """从文件加载，自动迁移旧格式。"""
        self._categories = []
        self._queue = deque()
        if not self._get_setting("queue.persist", True):
            return          # 本地保存已关闭：本次运行不读取历史数据
        try:
            if os.path.exists(self._save_path):
                with open(self._save_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                items, cats, saved_at = self._parse_raw(raw)
                self._categories = [
                    nc for nc in (self._normalize_category(c) for c in cats) if nc
                ]
                normalized = [self._normalize_item(it, saved_at) for it in items]
                self._queue = deque([it for it in normalized if it])
        except Exception:
            self._categories = []
            self._queue = deque()

    def _parse_raw(self, raw):
        """解析三种格式：flat list / dict(items,categories,saved_at)。"""
        if isinstance(raw, list):
            return raw, [], None
        if isinstance(raw, dict):
            return raw.get("items", []), raw.get("categories", []), raw.get("saved_at")
        return [], [], None

    def _normalize_category(self, cat):
        """规范化分类定义（兼容 str 与 dict）。"""
        if isinstance(cat, str):
            name = cat.strip() or self.DEFAULT_CATEGORY
            return {"name": name, "color": _default_category_color(name), "locked": False}
        if isinstance(cat, dict):
            name = (cat.get("name") or "").strip() or self.DEFAULT_CATEGORY
            return {
                "name": name,
                "color": cat.get("color") or _default_category_color(name),
                "locked": bool(cat.get("locked", False)),
            }
        return None

    def _normalize_item(self, item, saved_at=None):
        """规范化条目（兼容旧格式），确保所有字段齐全。"""
        if not isinstance(item, dict):
            return None
        content = item.get("content", "")
        ctype = item.get("type", "text")
        if ctype not in ("text", "image", "file"):
            ctype = "text"
        title = item.get("title") or self._derive_title(content, ctype, None)
        category = item.get("category") or self.DEFAULT_CATEGORY
        now = datetime.datetime.now()
        created_at = item.get("created_at") or saved_at or now.isoformat()
        return {
            "id": item.get("id") or uuid.uuid4().hex,
            "type": ctype,
            "title": title,
            "content": content,
            "preview": item.get("preview") or self._derive_preview(content, ctype),
            "category": category,
            "tags": list(item.get("tags") or []),
            "secret": bool(item.get("secret", False)),
            "created_at": created_at,
            "time": item.get("time") or now.strftime("%H:%M:%S"),
        }

    @staticmethod
    def _derive_title(content, content_type, title):
        if title:
            return title
        if content_type in ("image", "file"):
            base = os.path.basename(str(content or "")).strip()
            return base[:40] if base else "（文件）"
        first = (content or "").strip().splitlines()[0].strip() if content else ""
        return first[:40] if first else "（空内容）"

    @staticmethod
    def _derive_preview(content, content_type):
        if content_type in ("image", "file"):
            return str(content or "")
        text = content or ""
        return text[:50] + ("..." if len(text) > 50 else "")

    # ── 内部辅助 ──

    def _get_by_id(self, item_id):
        for it in self._queue:
            if it.get("id") == item_id:
                return it
        return None

    def _get_setting(self, key, default):
        if self._settings is None:
            return default
        try:
            return self._settings.get(key, default)
        except Exception:
            return default
