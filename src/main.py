"""
Clipboard Queue - 主入口
系统托盘图标 + 卡片式队列管理窗口 + 全局热键 + 设置。
快捷键（默认）: Ctrl+Alt+C 加入 | Ctrl+Alt+V 粘贴 | Ctrl+Alt+Q 清空 | Ctrl+Alt+S 主窗口
所有快捷键可在「设置」中修改。
"""

import os
import sys
import ctypes
import time
import datetime
import threading
import atexit
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import pystray
from PIL import Image, ImageDraw

# 将 src 目录加入路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui_theme import (COLORS, font, mono, category_color, apply, ScrollableFrame,
                      glassify)
from queue_manager import QueueManager
from clipboard_helper import ClipboardHelper
from hotkey_manager import HotkeyManager
from notify_helper import NotifyHelper
from app_settings import AppSettings
from security import Security
from settings_window import SettingsWindow, _PasswordSetDialog


# ═══════════════════════════════════════════════════════════════
# 图标生成
# ═══════════════════════════════════════════════════════════════

def create_icon_image(count=0):
    """创建 64x64 剪贴板图标（带队列数字角标）。"""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = 8
    bx, by = margin, margin + 6
    bw, bh = size - margin * 2, size - margin * 2 - 6

    accent = (61, 225, 255, 255)     # #3DE1FF
    accent_dim = (27, 126, 147, 255)  # #1B7E93

    # 剪贴板主体
    draw.rounded_rectangle(
        [bx, by, bx + bw, by + bh], radius=6,
        fill=accent, outline=accent_dim, width=2,
    )

    # 顶部夹子
    clip_w, clip_h = 16, 8
    clip_x = (size - clip_w) // 2
    draw.rounded_rectangle(
        [clip_x, by - 2, clip_x + clip_w, by + clip_h], radius=4,
        fill=accent_dim, outline=accent_dim, width=2,
    )

    # 内部横线
    line_y_start = by + clip_h + 12
    for i in range(3):
        ly = line_y_start + i * 8
        draw.rectangle(
            [bx + 10, ly, bx + bw - 10, ly + 3],
            fill=(11, 16, 32, 220),
        )

    # 角标数字
    if count > 0:
        badge_size = 22
        badge_x, badge_y = size - badge_size - 2, size - badge_size - 2
        draw.ellipse(
            [badge_x, badge_y, badge_x + badge_size, badge_y + badge_size],
            fill=(255, 92, 108, 255), outline=(180, 30, 40, 255), width=1,
        )

        count_str = str(count) if count < 100 else "99+"
        try:
            from PIL import ImageFont
            font_size = 12 if len(count_str) <= 2 else 8
            fnt = ImageFont.truetype("segoeui.ttf", font_size)
            bbox = draw.textbbox((0, 0), count_str, font=fnt)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text(
                (badge_x + (badge_size - tw) // 2, badge_y + (badge_size - th) // 2 - 1),
                count_str, fill=(255, 255, 255, 255), font=fnt,
            )
        except Exception:
            cx = badge_x + (badge_size // 2)
            cy = badge_y + (badge_size // 2)
            draw.text((cx - 4, cy - 6), count_str, fill=(255, 255, 255, 255))

    return img


# ═══════════════════════════════════════════════════════════════
# 解锁对话框
# ═══════════════════════════════════════════════════════════════

class PasswordDialog:
    """模态解锁对话框：掩码输入、解锁/取消、错误反馈、Enter 提交、Esc 取消。"""

    def __init__(self, root, security):
        self.security = security
        self._result = False
        self.window = tk.Toplevel(root)
        self.window.title("解锁")
        self.window.configure(bg=COLORS["bg"])
        glassify(self.window, None, alpha=0.97)
        self.window.resizable(False, False)
        self.window.transient(root)
        self.window.grab_set()

        box = tk.Frame(self.window, bg=COLORS["card"],
                       highlightthickness=1, highlightbackground=COLORS["border"])
        box.pack(padx=20, pady=20)

        tk.Label(box, text="🔒 需要密码", bg=COLORS["card"], fg=COLORS["text"],
                 font=font(12, True)).pack(pady=(14, 4))
        tk.Label(box, text="该内容受密码保护，请输入访问密码", bg=COLORS["card"],
                 fg=COLORS["text_dim"], font=font(8)).pack(pady=(0, 10))

        self.entry = ttk.Entry(box, show="•", width=28)
        self.entry.pack(padx=20, pady=4)

        self.msg = tk.Label(box, text="", bg=COLORS["card"], fg=COLORS["danger"],
                            font=font(8))
        self.msg.pack(pady=4)

        btns = tk.Frame(box, bg=COLORS["card"])
        btns.pack(pady=(6, 14))
        ttk.Button(btns, text="取消", style="Ghost.TButton",
                   command=self._cancel).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="解锁", style="Accent.TButton",
                   command=self._ok).pack(side=tk.LEFT, padx=4)

        self.entry.bind("<Return>", lambda e: self._ok())
        self.window.bind("<Escape>", lambda e: self._cancel())

        self._center()
        self.entry.focus_force()
        self.window.wait_window()

    def _center(self):
        self.window.update_idletasks()
        w, h = 360, 240
        sw = self.window.winfo_screenwidth()
        sh = self.window.winfo_screenheight()
        self.window.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    def _ok(self):
        if self.security.verify_password(self.entry.get()):
            self._result = True
            self.window.destroy()
        else:
            self.msg.config(text="密码错误，请重试")
            self.entry.delete(0, tk.END)

    def _cancel(self):
        self._result = False
        self.window.destroy()

    def result(self):
        return self._result


# ═══════════════════════════════════════════════════════════════
# 卡片式队列列表窗口
# ═══════════════════════════════════════════════════════════════

class QueueListWindow:
    """深色卡片式主窗口，每条队列内容一张展示卡。"""

    def __init__(self, root, queue, settings=None, security=None,
                 clipboard=None, hotkeys=None, notify=None,
                 on_copy=None, on_paste=None, on_open_settings=None,
                 on_changed=None, confirm_delete=None):
        self._root = root
        self.queue = queue
        self.settings = settings
        self.security = security
        self.clipboard = clipboard
        self.hotkeys = hotkeys
        self.notify = notify
        self.on_copy = on_copy
        self.on_paste = on_paste
        self.on_open_settings = on_open_settings
        self.on_changed = on_changed
        self.confirm_delete = confirm_delete

        self.window = None
        self.count_lbl = None
        self._cat_bar = None
        self._scroll = None
        self._search_var = None
        self._search_after = None
        self._filter_category = "全部"
        self._selected_id = None
        self._cards = []          # [(card_frame, item)]
        self._thumbnails = {}     # item_id -> PhotoImage

    # ── 显示 ──

    def show(self):
        """显示或聚焦窗口（必须在主线程调用）。"""
        if self.window and self.window.winfo_exists():
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()
            self._refresh_list()
            return

        apply(self._root)
        self.window = tk.Toplevel(self._root)
        self.window.title("Clipboard Queue - 剪贴板队列")
        self.window.geometry("560x680")
        self.window.minsize(430, 420)
        self.window.configure(bg=COLORS["bg"])
        glassify(self.window, getattr(self, "settings", None))

        self._build_ui()
        self._refresh_list()

        self.window.protocol("WM_DELETE_WINDOW", self._on_close)
        self.window.bind("<Escape>", lambda e: self._on_close())
        self.window.bind("<F5>", lambda e: self._refresh_list())
        self.window.bind("<Delete>", lambda e: self._delete_selected())

        self.window.update_idletasks()
        w, h = 560, 680
        sw = self.window.winfo_screenwidth()
        sh = self.window.winfo_screenheight()
        self.window.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self.window.focus_force()

    def _on_close(self):
        if self.window and self.window.winfo_exists():
            self.window.destroy()
            self.window = None

    def destroy(self):
        self._on_close()

    # ── UI 构建 ──

    def _build_ui(self):
        # 顶栏
        header = tk.Frame(self.window, bg=COLORS["panel"])
        header.pack(fill=tk.X)

        title_box = tk.Frame(header, bg=COLORS["panel"])
        title_box.pack(side=tk.LEFT, padx=14, pady=12)
        tk.Label(title_box, text="◈", bg=COLORS["panel"], fg=COLORS["accent"],
                 font=font(15, True)).pack(side=tk.LEFT)
        tk.Label(title_box, text="剪贴板队列", bg=COLORS["panel"], fg=COLORS["text"],
                 font=font(13, True)).pack(side=tk.LEFT, padx=6)
        self.count_lbl = tk.Label(header, text="", bg=COLORS["card_active"],
                                  fg=COLORS["accent"], font=font(9, True), padx=8, pady=2)
        self.count_lbl.pack(side=tk.LEFT, pady=14)

        right = tk.Frame(header, bg=COLORS["panel"])
        right.pack(side=tk.RIGHT, padx=12, pady=10)
        self._search_var = tk.StringVar()
        search = ttk.Entry(right, textvariable=self._search_var, width=18)
        search.pack(side=tk.LEFT, padx=3)
        search.bind("<KeyRelease>", lambda e: self._on_search())
        ttk.Button(right, text="设置", style="Ghost.TButton",
                   command=self._open_settings).pack(side=tk.LEFT, padx=2)
        ttk.Button(right, text="刷新", style="Ghost.TButton",
                   command=self._refresh_list).pack(side=tk.LEFT, padx=2)

        # 分类筛选条
        self._cat_bar = tk.Frame(self.window, bg=COLORS["bg"])
        self._cat_bar.pack(fill=tk.X, padx=8, pady=(6, 2))

        # 列表滚动区
        self._scroll = ScrollableFrame(self.window, bg=COLORS["bg"])
        self._scroll.pack(fill=tk.BOTH, expand=True, padx=6, pady=(2, 8))

    def _open_settings(self):
        self._safe(self.on_open_settings)

    # ── 刷新 ──

    def _on_search(self):
        if self._search_after:
            try:
                self._root.after_cancel(self._search_after)
            except Exception:
                pass
        self._search_after = self._root.after(200, self._refresh_list)

    def _refresh_list(self):
        if not self.window:
            return
        self._safe(self._do_refresh)

    def _do_refresh(self):
        n = self.queue.count()
        self.count_lbl.config(text=f"{n} 项" if n else "0 项")

        # 重建分类 chips
        for w in self._cat_bar.winfo_children():
            w.destroy()
        counts = self.queue.counts_by_category()
        self._make_chip(self._cat_bar, "全部", COLORS["accent"], n,
                        self._filter_category == "全部")
        for name, cnt in counts.items():
            info = self.queue.get_category(name)
            color = info["color"] if info else category_color(name)
            self._make_chip(self._cat_bar, name, color, cnt,
                            self._filter_category == name)

        # 重建卡片
        self._scroll.clear()
        self._cards = []
        self._thumbnails = {}
        items = self._filtered_items()
        for idx, item in enumerate(items):
            self._make_card(self._scroll.inner, item, idx)

        # 选中项丢失则清除
        if self._selected_id and not self.queue.get_item(self._selected_id):
            self._selected_id = None
        self._apply_selection()
        self._scroll.scroll_to_top()

    def _filtered_items(self):
        items = self.queue.get_all()
        if self._filter_category != "全部":
            items = [it for it in items
                     if (it.get("category") or "未分类") == self._filter_category]
        q = (self._search_var.get() or "").strip().lower()
        if q:
            items = [it for it in items if q in " ".join([
                str(it.get("title", "")), str(it.get("content", "")),
                str(it.get("category", "")), " ".join(it.get("tags", []) or []),
            ]).lower()]
        return items

    def _make_chip(self, parent, name, color, count, selected):
        bg = COLORS["card_active"] if selected else COLORS["card"]
        fg = COLORS["text"] if selected else COLORS["text_dim"]
        chip = tk.Frame(parent, bg=bg, highlightthickness=1,
                        highlightbackground=color if selected else COLORS["border"])
        chip.pack(side=tk.LEFT, padx=3, pady=4)
        dot = tk.Label(chip, text="●", bg=bg, fg=color, font=font(8))
        dot.pack(side=tk.LEFT, padx=(8, 2), pady=3)
        lbl = tk.Label(chip, text=f"{name} {count}", bg=bg, fg=fg, font=font(9))
        lbl.pack(side=tk.LEFT, padx=(0, 8), pady=3)
        for w in (chip, dot, lbl):
            w.bind("<Button-1>", lambda e, n=name: self._set_filter(n))
        chip.bind("<Enter>", lambda e: self._chip_hover(chip, color, selected, True))
        chip.bind("<Leave>", lambda e: self._chip_hover(chip, color, selected, False))

    def _chip_hover(self, chip, color, selected, entering):
        try:
            if entering and not selected:
                chip.configure(bg=COLORS["card_hover"])
            elif not entering and not selected:
                chip.configure(bg=COLORS["card"])
        except Exception:
            pass

    def _set_filter(self, name):
        self._filter_category = name
        self._refresh_list()

    # ── 卡片 ──

    def _make_card(self, parent, item, index):
        protected = self.queue.is_protected(item)
        card = tk.Frame(parent, bg=COLORS["card"], highlightthickness=1,
                        highlightbackground=COLORS["border"])
        card.pack(fill=tk.X, padx=4, pady=4)
        self._cards.append((card, item))
        self._wire(card, item, card)

        # 图片缩略图
        if item.get("type") == "image":
            self._add_thumbnail(card, item)

        body = tk.Frame(card, bg=COLORS["card"])
        body.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=8)
        self._wire(body, item, card)

        # 标题行
        title_row = tk.Frame(body, bg=COLORS["card"])
        title_row.pack(fill=tk.X)
        title = item.get("title") or "（无标题）"
        t = tk.Label(title_row, text=title, bg=COLORS["card"], fg=COLORS["text"],
                     font=font(10, True), anchor=tk.W, justify=tk.LEFT)
        t.pack(side=tk.LEFT)
        self._wire(t, item, card)
        if protected:
            badge = tk.Label(title_row, text="🔒 密码", bg=COLORS["card"],
                             fg=COLORS["warn"], font=font(8))
            badge.pack(side=tk.LEFT, padx=6)
            self._wire(badge, item, card)

        # meta 行
        meta_row = tk.Frame(body, bg=COLORS["card"])
        meta_row.pack(fill=tk.X, pady=(2, 0))
        cat_name = item.get("category") or "未分类"
        info = self.queue.get_category(cat_name)
        cat_color = info["color"] if info else category_color(cat_name)
        cat_chip = tk.Label(meta_row, text=f"● {cat_name}", bg=COLORS["card"],
                            fg=cat_color, font=font(8))
        cat_chip.pack(side=tk.LEFT)
        self._wire(cat_chip, item, card)

        kind = {"text": "文本", "image": "图片", "file": "文件"}.get(item.get("type"), "文本")
        if protected:
            char_txt = "🔒 受保护"
        else:
            char_txt = f"{len(item.get('content') or '')} 字符"
        meta = tk.Label(meta_row, text=f"  #{index + 1} · {kind} · {char_txt} · {self._format_ts(item)}",
                        bg=COLORS["card"], fg=COLORS["text_mute"], font=font(8))
        meta.pack(side=tk.LEFT)
        self._wire(meta, item, card)

        # 正文预览
        if protected:
            preview = "••••••••"
            use_mono = False
        else:
            content = item.get("content", "")
            preview = self._truncate_preview(content)
            use_mono = self._looks_like_code(content)
        pv = tk.Label(body, text=preview, bg=COLORS["card"], fg=COLORS["text_dim"],
                      font=mono(8) if use_mono else font(9),
                      anchor=tk.W, justify=tk.LEFT, wraplength=500)
        pv.pack(fill=tk.X, pady=(4, 2))
        self._wire(pv, item, card)

        # 操作行
        actions = tk.Frame(body, bg=COLORS["card"])
        actions.pack(fill=tk.X, pady=(4, 0))
        self._ghost_btn(actions, "复制", lambda: self._copy_item(item))
        self._ghost_btn(actions, "粘贴", lambda: self._paste_item(item))
        self._ghost_btn(actions, "命名", lambda: self._rename_item(item))
        self._ghost_btn(actions, "分类", lambda: self._categorize_item(item))
        self._ghost_btn(actions, "置顶", lambda: self._move_front(item))
        self._ghost_btn(actions, "删除", lambda: self._delete_item(item))

    def _ghost_btn(self, parent, text, cmd):
        b = tk.Label(parent, text=text, bg=COLORS["card"], fg=COLORS["text_dim"],
                     font=font(8), padx=8, pady=2)
        b.pack(side=tk.LEFT, padx=2)
        b.bind("<Button-1>", lambda e: self._safe(cmd))
        b.bind("<Enter>", lambda e: b.configure(bg=COLORS["card_hover"], fg=COLORS["text"]))
        b.bind("<Leave>", lambda e: b.configure(bg=COLORS["card"], fg=COLORS["text_dim"]))

    def _wire(self, w, item, card):
        """为内容部件绑定选中/双击/右键/悬停。"""
        w.bind("<Button-1>", lambda e: self._select_card(item), add="+")
        w.bind("<Double-1>", lambda e: self._safe(lambda: self._copy_item(item)), add="+")
        w.bind("<Button-3>", lambda e: self._show_context_menu(e, item), add="+")
        w.bind("<Enter>", lambda e: self._on_card_enter(card, item), add="+")
        w.bind("<Leave>", lambda e: self._on_card_leave(card, item), add="+")

    def _on_card_enter(self, card, item):
        try:
            if item.get("id") == self._selected_id:
                return
            self._set_card_bg(card, COLORS["card_hover"])
            card.configure(highlightbackground=COLORS["border_light"])
        except Exception:
            pass

    def _on_card_leave(self, card, item):
        try:
            if item.get("id") == self._selected_id:
                self._set_card_bg(card, COLORS["card_active"])
                card.configure(highlightbackground=COLORS["border_light"])
            else:
                self._set_card_bg(card, COLORS["card"])
                card.configure(highlightbackground=COLORS["border"])
        except Exception:
            pass

    def _set_card_bg(self, card, bg):
        card.configure(bg=bg)
        for child in card.winfo_children():
            self._set_child_bg(child, bg)

    def _set_child_bg(self, w, bg):
        if isinstance(w, (tk.Frame, tk.Label)):
            try:
                w.configure(bg=bg)
            except Exception:
                pass
        for c in w.winfo_children():
            self._set_child_bg(c, bg)

    def _select_card(self, item):
        self._selected_id = item.get("id")
        self._apply_selection()

    def _apply_selection(self):
        for card, item in self._cards:
            try:
                if not card.winfo_exists():
                    continue
                if item.get("id") == self._selected_id:
                    self._set_card_bg(card, COLORS["card_active"])
                    card.configure(highlightbackground=COLORS["border_light"])
                else:
                    self._set_card_bg(card, COLORS["card"])
                    card.configure(highlightbackground=COLORS["border"])
            except Exception:
                pass

    def _add_thumbnail(self, card, item):
        path = item.get("content", "")
        if not path or not os.path.exists(path):
            return
        try:
            from PIL import Image as PILImage, ImageTk
            img = PILImage.open(path)
            img.thumbnail((64, 64))
            photo = ImageTk.PhotoImage(img)
            self._thumbnails[item.get("id")] = photo
            lbl = tk.Label(card, image=photo, bg=COLORS["card"], bd=0)
            lbl.pack(side=tk.LEFT, padx=(8, 0), pady=8)
            self._wire(lbl, item, card)
        except Exception:
            pass

    # ── 格式化辅助 ──

    @staticmethod
    def _format_ts(item):
        created = item.get("created_at") or ""
        try:
            return datetime.datetime.fromisoformat(created).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return created or item.get("time", "")

    @staticmethod
    def _truncate_preview(content):
        content = content or ""
        lines = content.splitlines()
        shown = []
        total = 0
        for line in lines[:3]:
            line = line.rstrip()
            if len(line) > 60:
                line = line[:60] + "…"
            shown.append(line)
            total += len(line)
            if total > 150:
                break
        result = "\n".join(shown)
        if len(content) > 150 or len(lines) > 3:
            result += " …"
        return result or "（空）"

    @staticmethod
    def _looks_like_code(content):
        c = content or ""
        if "\n" not in c:
            return False
        markers = ("def ", "class ", "import ", "{", "}", ";", "=>",
                   "if(", "for(", "#include", "function ", "return ")
        return any(m in c for m in markers)

    # ── 操作 ──

    def _copy_item(self, item):
        if self.on_copy:
            self._safe(lambda: self.on_copy(item))
        else:
            self._safe(lambda: self._local_copy(item))

    def _paste_item(self, item):
        if self.on_paste:
            self._safe(lambda: self.on_paste(item))
        else:
            self._safe(lambda: self._local_paste(item))

    def _local_copy(self, item):
        if self.clipboard:
            self.clipboard.write(item.get("content", ""))
        if self.notify:
            self.notify.show("已复制到剪贴板", (item.get("title") or "")[:40])

    def _local_paste(self, item):
        if self.clipboard:
            self.clipboard.write(item.get("content", ""))
        if self.hotkeys:
            self.hotkeys.send_paste()
        self.queue.remove_item(item.get("id"))
        self._refresh_list()
        self._notify_changed()

    def _rename_item(self, item):
        cur = item.get("title", "")
        new = simpledialog.askstring("命名", "输入新标题：", initialvalue=cur,
                                     parent=self.window)
        if new is None:
            return
        self.queue.update_item(item.get("id"), title=(new.strip() or cur))
        self._refresh_list()
        self._notify_changed()

    def _categorize_item(self, item):
        cats = self.queue.get_categories()
        names = [c["name"] for c in cats]
        if "未分类" not in names:
            names.insert(0, "未分类")

        result = {"name": None}
        win = tk.Toplevel(self.window)
        win.title("选择分类")
        win.configure(bg=COLORS["bg"])
        win.transient(self.window)
        win.grab_set()
        lb = tk.Listbox(win, bg=COLORS["input"], fg=COLORS["text"], font=font(9),
                        selectbackground=COLORS["card_active"],
                        selectforeground=COLORS["text"],
                        highlightthickness=1, highlightbackground=COLORS["border"],
                        height=8)
        lb.pack(padx=16, pady=12, fill=tk.BOTH, expand=True)
        for n in names:
            lb.insert(tk.END, n)
        btns = tk.Frame(win, bg=COLORS["bg"])
        btns.pack(pady=(0, 12))

        def ok():
            sel = lb.curselection()
            if sel:
                result["name"] = names[sel[0]]
            win.destroy()

        ttk.Button(btns, text="取消", style="Ghost.TButton",
                   command=win.destroy).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="确定", style="Accent.TButton",
                   command=ok).pack(side=tk.LEFT, padx=4)
        win.bind("<Escape>", lambda e: win.destroy())
        win.bind("<Return>", lambda e: ok())
        win.update_idletasks()
        win.geometry(f"+{self.window.winfo_rootx() + 90}+{self.window.winfo_rooty() + 90}")
        self.window.wait_window(win)

        if result["name"]:
            self.queue.update_item(item.get("id"), category=result["name"])
            self._refresh_list()
            self._notify_changed()

    def _move_front(self, item):
        self.queue.move_to_front(item.get("id"))
        self._refresh_list()
        self._notify_changed()

    def _delete_item(self, item):
        if self._should_confirm_delete():
            title = item.get("title") or "该条目"
            if not messagebox.askyesno("确认删除", f"确定删除「{title}」吗？\n此操作不可撤销。",
                                       parent=self.window):
                return
        self.queue.remove_item(item.get("id"))
        self._refresh_list()
        self._notify_changed()
        if self.queue.is_empty():
            self._on_close()

    def _should_confirm_delete(self) -> bool:
        """
        删除前是否需要二次确认。

        confirm_delete 支持两种传入方式：
        - 布尔值 / None（None 视为需要确认）
        - 回调（返回布尔值），例如读取设置项 general.confirm_before_delete
        """
        if self.confirm_delete is None:
            return True
        try:
            return bool(self.confirm_delete() if callable(self.confirm_delete)
                        else self.confirm_delete)
        except Exception:
            return True

    def _delete_selected(self):
        item = self.queue.get_item(self._selected_id) if self._selected_id else None
        if item:
            self._delete_item(item)

    def _show_context_menu(self, event, item):
        try:
            menu = tk.Menu(self.window, tearoff=0, bg=COLORS["panel"], fg=COLORS["text"],
                           activebackground=COLORS["card_active"],
                           activeforeground=COLORS["text"])
            menu.add_command(label="复制", command=lambda: self._copy_item(item))
            menu.add_command(label="粘贴", command=lambda: self._paste_item(item))
            menu.add_command(label="命名", command=lambda: self._rename_item(item))
            menu.add_command(label="分类", command=lambda: self._categorize_item(item))
            menu.add_command(label="置顶到队首", command=lambda: self._move_front(item))
            menu.add_separator()
            menu.add_command(label="删除", command=lambda: self._delete_item(item))
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                menu.grab_release()
            except Exception:
                pass

    def _notify_changed(self):
        if self.on_changed:
            try:
                self.on_changed()
            except Exception:
                pass

    def _safe(self, fn):
        try:
            fn()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
# 主应用
# ═══════════════════════════════════════════════════════════════

class ClipboardQueueApp:
    """Clipboard Queue 主应用。"""

    DEFAULT_HOTKEYS = {
        "copy": "ctrl+alt+c",
        "paste": "ctrl+alt+v",
        "clear": "ctrl+alt+q",
        "show": "ctrl+alt+s",
    }

    def __init__(self, settings=None):
        self.settings = settings if settings is not None else AppSettings()
        self.security = Security(self.settings)
        self.queue = QueueManager(settings=self.settings)
        self.clipboard = ClipboardHelper()
        self.hotkeys = HotkeyManager()
        self.notify = NotifyHelper()
        self.icon = None
        self.list_window = None
        self.settings_window = None
        self._root = None
        self._unlock_until = 0.0
        self._secret_on_clipboard = False

    # ── 快捷键 ──

    def _hk(self, key):
        return self.settings.get(f"hotkeys.{key}", self.DEFAULT_HOTKEYS[key]) or self.DEFAULT_HOTKEYS[key]

    def _init_hotkeys(self):
        """注册全局热键（从设置读取）。"""
        bindings = {
            self._hk("copy"): self._on_copy_to_queue,
            self._hk("paste"): self._on_paste_from_queue,
            self._hk("clear"): self._on_clear_queue,
            self._hk("show"): self._on_show_hotkey,
        }
        self.hotkeys.configure(bindings)

    def _reinit_hotkeys(self):
        self._init_hotkeys()

    # ── 主线程调度 ──

    def _ui(self, fn):
        """将 fn 调度到 tkinter 主线程执行（可从后台线程调用）。"""
        try:
            if self._root:
                self._root.after(0, fn)
        except Exception:
            pass

    def _notify(self, title, msg=""):
        try:
            if self.settings.get("general.show_notifications", True):
                self.notify.show(title, msg)
            if self.settings.get("general.notification_sound", False):
                self.notify.beep()
        except Exception:
            pass

    # ── 解锁缓存 ──

    def _is_unlocked(self):
        return time.time() < self._unlock_until

    def _mark_unlocked(self):
        ttl = int(self.settings.get("security.unlock_ttl_seconds", 300) or 300)
        self._unlock_until = time.time() + max(ttl, 0)

    def _lock_now(self):
        self._unlock_until = 0.0
        self._notify("已锁定", "密码类内容需要重新解锁")

    def _ensure_unlock(self):
        """确保已解锁（必要时弹出解锁/设置密码对话框）。"""
        if self._is_unlocked():
            return True
        if not self.security.has_password():
            dlg = _PasswordSetDialog(self._root)
            pw = dlg.result()
            if pw and self.security.set_password(pw):
                self._mark_unlocked()
                return True
            return False
        dlg = PasswordDialog(self._root, self.security)
        if dlg.result():
            self._mark_unlocked()
            return True
        return False

    # ── 剪贴板保护 ──

    def _schedule_secret_clear(self):
        if not self._secret_on_clipboard:
            return
        try:
            secs = int(self.settings.get("security.auto_clear_clipboard_seconds", 0) or 0)
            if secs > 0:
                self._root.after(secs * 1000, self._clear_clipboard_now)
        except Exception:
            pass

    def _clear_clipboard_now(self):
        try:
            self.clipboard.write("")
            self._secret_on_clipboard = False
            self._notify("剪贴板已清空", "受保护内容已从剪贴板移除")
        except Exception:
            pass

    # ── 复制 / 粘贴（供 UI 调用，主线程）──

    def copy_item(self, item):
        """复制条目内容到剪贴板（受保护则先解锁）。"""
        try:
            if self.queue.is_protected(item) and not self._is_unlocked():
                if not self._ensure_unlock():
                    return False
            self.clipboard.write(item.get("content", ""))
            self._secret_on_clipboard = self.queue.is_protected(item)
            self._schedule_secret_clear()
            self._notify("已复制到剪贴板", (item.get("title") or "")[:40])
            return True
        except Exception:
            return False

    def paste_item(self, item):
        """复制 + 模拟 Ctrl+V 粘贴，并移除该条目。"""
        try:
            if self.queue.is_protected(item) and not self._is_unlocked():
                if not self._ensure_unlock():
                    return False
            self.queue.remove_item(item.get("id"))
            self._do_paste_content(item.get("content", ""), item)
            return True
        except Exception:
            return False

    def _do_paste_content(self, content, item):
        """写入剪贴板并延迟模拟 Ctrl+V（主线程，非阻塞）。"""
        try:
            self.clipboard.save_backup()
            self.clipboard.write(content)
            self._secret_on_clipboard = self.queue.is_protected(item)

            def send():
                try:
                    self.hotkeys.send_paste()
                except Exception:
                    pass
                self._after_paste(item)

            self._root.after(120, send)
        except Exception:
            pass

    def _after_paste(self, item):
        try:
            clear_after = self.settings.get("queue.clear_clipboard_after_paste", False)
            restore = self.settings.get("queue.restore_user_clipboard_after_paste", True)
            if clear_after:
                self.clipboard.write("")
            elif restore:
                delay = float(self.settings.get("queue.restore_delay_seconds", 0.8) or 0.8)
                self.clipboard.restore_after_delay(delay)
            self._schedule_secret_clear()
            self._update_tray_icon()
            self._refresh_list_window()
            preview = (item or {}).get("preview") or (item or {}).get("title", "")
            self._notify("已粘贴", preview[:40])
        except Exception:
            pass

    # ── 热键回调（运行在独立 Timer 线程）──

    def _on_copy_to_queue(self):
        """Ctrl+Alt+C：先模拟 Ctrl+C 复制选中文本，再读剪贴板入队。"""
        try:
            time.sleep(0.1)
            self.hotkeys.send_copy()
            time.sleep(0.25)
            content = self.clipboard.read()
            if content and content.strip():
                item = self.queue.enqueue(content.strip(), "text")
                if item is None:
                    self._ui(lambda: self._notify("已跳过", "重复内容未重复入队"))
                    return
                self._ui(lambda: self._after_enqueue(item))
            else:
                self._ui(lambda: self._notify("复制失败", "请先选中文字，再按快捷键"))
        except Exception:
            pass

    def _after_enqueue(self, item):
        self._update_tray_icon()
        self._refresh_list_window()
        self._notify("已加入队列", f"队列长度: {self.queue.count()}")

    def _on_paste_from_queue(self):
        """Ctrl+Alt+V：从队列取出内容，写入剪贴板，模拟 Ctrl+V 粘贴。"""
        try:
            items = self.queue.get_all()
            if not items:
                self._ui(lambda: self._notify("队列为空", "没有可粘贴的内容，使用普通剪贴板"))
                return
            head = items[0]
            if self.queue.is_protected(head) and not self._is_unlocked():
                self._ui(self._prompt_unlock_then_paste)
                return
            item = self.queue.dequeue()
            if item:
                self._ui(lambda: self._do_paste_content(item.get("content", ""), item))
        except Exception:
            pass

    def _prompt_unlock_then_paste(self):
        """受保护队首：先解锁再粘贴（主线程）。"""
        try:
            items = self.queue.get_all()
            if not items:
                return
            if not self._ensure_unlock():
                return
            item = self.queue.dequeue()
            if item:
                self._do_paste_content(item.get("content", ""), item)
        except Exception:
            pass

    def _on_clear_queue(self):
        """Ctrl+Alt+Q：清空队列。"""
        try:
            if self.queue.is_empty():
                return
            cnt = self.queue.count()
            self.queue.clear()
            self._ui(lambda: self._after_clear(cnt))
        except Exception:
            pass

    def _after_clear(self, cnt):
        self._update_tray_icon()
        self._refresh_list_window()
        self._notify(f"已清空 {cnt} 项", "队列为空")

    def _on_show_hotkey(self):
        self._ui(self._show_queue_list)

    # ── 托盘图标 ──

    def _update_tray_icon(self):
        if self.icon:
            count = self.queue.count()
            self.icon.icon = create_icon_image(count)
            self.icon.title = (
                f"Clipboard Queue - {count} 项" if count > 0
                else "Clipboard Queue - 队列为空"
            )

    def _create_tray_menu(self):
        return pystray.Menu(
            pystray.MenuItem(
                "显示主窗口",
                lambda: self._safe_call(self._show_queue_list),
                default=True,
            ),
            pystray.MenuItem("设置", lambda: self._safe_call(self._show_settings)),
            pystray.MenuItem("清空队列", lambda: self._safe_call(self._tray_clear)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("立即锁定", lambda: self._safe_call(self._lock_now)),
            pystray.MenuItem("立即清空剪贴板",
                             lambda: self._safe_call(self._clear_clipboard_now)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("关于", lambda: self._safe_call(self._show_about)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", lambda: self.shutdown()),
        )

    def _safe_call(self, func):
        """在主线程（tkinter 线程）中安全执行函数。"""
        if self._root:
            self._root.after(0, func)

    def _tray_clear(self):
        if not self.queue.is_empty():
            cnt = self.queue.count()
            self.queue.clear()
            self._update_tray_icon()
            self._refresh_list_window()
            self._notify(f"已清空 {cnt} 项", "")

    def _show_about(self):
        messagebox.showinfo(
            "关于 Clipboard Queue",
            "剪贴板队列 v2.0\n\n"
            "把复制粘贴变成 FIFO 队列的 Windows 工具。\n"
            "支持分类、命名、密码保护、本地持久化。\n\n"
            "快捷键请在「设置」中查看/修改。",
        )

    # ── 窗口 ──

    def _show_queue_list(self):
        """打开/聚焦队列列表窗口（必须运行在主线程）。"""
        if self.list_window and self.list_window.window and self.list_window.window.winfo_exists():
            self.list_window.show()
        else:
            self.list_window = QueueListWindow(
                self._root, self.queue,
                settings=self.settings, security=self.security,
                clipboard=self.clipboard, hotkeys=self.hotkeys, notify=self.notify,
                on_copy=self.copy_item, on_paste=self.paste_item,
                on_open_settings=self._show_settings,
                on_changed=self._on_data_changed,
                confirm_delete=lambda: self.settings.get("general.confirm_before_delete", True),
            )
            self.list_window.show()

    def _show_settings(self):
        """打开/聚焦设置窗口（必须运行在主线程）。"""
        if self.settings_window and self.settings_window.window and self.settings_window.window.winfo_exists():
            self.settings_window.show()
        else:
            self.settings_window = SettingsWindow(
                self._root, self.settings, self.security, self.queue,
                on_apply=self._apply_settings_live,
            )
            self.settings_window.show()

    def _apply_settings_live(self):
        """设置保存后即时生效（重注册热键、刷新 UI）。"""
        try:
            self._reinit_hotkeys()
        except Exception as e:
            raise RuntimeError(f"热键注册失败: {e}")
        self._update_tray_icon()
        self._refresh_list_window()

    def _on_data_changed(self):
        self._update_tray_icon()

    def _refresh_list_window(self):
        try:
            if self.list_window and self.list_window.window and self.list_window.window.winfo_exists():
                self.list_window._refresh_list()
        except Exception:
            pass

    # ── 生命周期 ──

    def run(self):
        """启动应用。"""
        self._root = tk.Tk()
        self._root.withdraw()
        self._root.title("ClipboardQueue")
        apply(self._root)

        self._init_hotkeys()

        count = self.queue.count()
        self.icon = pystray.Icon(
            "ClipboardQueue",
            create_icon_image(count),
            f"Clipboard Queue - {'队列为空' if count == 0 else f'{count} 项'}",
            menu=self._create_tray_menu(),
        )

        self.tray_thread = threading.Thread(target=self._run_tray, daemon=True)
        self.tray_thread.start()

        atexit.register(self._cleanup)

        print("\n  Clipboard Queue 已启动")
        print(f"  {'─' * 44}")
        print(f"  {self._hk('copy')}  →  加入队列")
        print(f"  {self._hk('paste')}  →  从队列粘贴")
        print(f"  {self._hk('clear')}  →  清空队列")
        print(f"  {self._hk('show')}  →  打开主窗口")
        print("  点击托盘图标 →  查看/管理队列")
        print(f"  队列中有 {count} 项\n")

        try:
            self._root.mainloop()
        except KeyboardInterrupt:
            pass
        finally:
            self._cleanup()

    def _run_tray(self):
        try:
            self.icon.run()
        except Exception:
            pass

    def shutdown(self):
        print("[ClipboardQueue] 正在退出...")
        self._cleanup()
        if self._root:
            self._root.after(0, self._root.quit)

    def _cleanup(self):
        """清理资源。"""
        try:
            if self.settings.get("security.clear_secret_on_exit", False) and self._secret_on_clipboard:
                self.clipboard.write("")
        except Exception:
            pass
        try:
            self.hotkeys.stop()
        except Exception:
            pass
        try:
            if self.list_window:
                self.list_window.destroy()
        except Exception:
            pass
        try:
            if self.settings_window and self.settings_window.window:
                self.settings_window.window.destroy()
        except Exception:
            pass
        try:
            if self.icon:
                self.icon.stop()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════════

def main():
    settings = AppSettings()
    mutex = None
    kernel32 = None

    # 单实例互斥锁（可在设置中关闭）
    if settings.get("general.single_instance", True):
        try:
            kernel32 = ctypes.windll.kernel32
            mutex_name = "Global\\ClipboardQueue_SingleInstance"
            mutex = kernel32.CreateMutexW(None, False, mutex_name)
            if kernel32.GetLastError() == 183:
                kernel32.CloseHandle(mutex)
                try:
                    hwnd = ctypes.windll.user32.FindWindowW(None, "ClipboardQueue")
                    if hwnd:
                        ctypes.windll.user32.SetForegroundWindow(hwnd)
                except Exception:
                    pass
                print("[ClipboardQueue] 应用已在运行中，请查看系统托盘")
                return
        except Exception:
            mutex = None

    app = ClipboardQueueApp(settings)
    app.run()

    if mutex and kernel32:
        try:
            kernel32.CloseHandle(mutex)
        except Exception:
            pass


if __name__ == "__main__":
    main()
