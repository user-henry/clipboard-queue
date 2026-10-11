"""
Clipboard Queue - 统一主题模块
深色「科技感」主题配色、字体、ttk 样式、可滚动容器与 hover 辅助。
所有 ttk 样式配置均做降级处理（try/except），保证在 tkinter 8.6 / Python 3.13 下稳定运行。
"""

import hashlib
import tkinter as tk
from tkinter import ttk

# ─────────────────────────────────────────────────────────────
# 调色板（与兄弟项目保持一致）
# ─────────────────────────────────────────────────────────────
COLORS = {
    "bg": "#0B1020", "bg_alt": "#0E1526", "panel": "#121A2E",
    "card": "#16203A", "card_hover": "#1D2A4A", "card_active": "#22325A",
    "border": "#22304F", "border_light": "#2E4165",
    "text": "#E8F1FF", "text_dim": "#8CA0C4", "text_mute": "#5F719A",
    "accent": "#3DE1FF", "accent_dim": "#1B7E93", "accent2": "#7C5CFF",
    "success": "#35D07F", "warn": "#FFB020", "danger": "#FF5C6C",
    "input": "#0F1729",
}

FONT_FAMILY = "Microsoft YaHei UI"
FONT_MONO = "Consolas"

# 分类候选色（8 个强调色）
CATEGORY_COLORS = [
    "#3DE1FF", "#7C5CFF", "#35D07F", "#FFB020",
    "#FF5C6C", "#FF7AC6", "#5C8AFF", "#FFD23F",
]


def font(size, bold=False):
    """返回 tkinter 可用的字体元组。"""
    return (FONT_FAMILY, size, "bold") if bold else (FONT_FAMILY, size)


def mono(size, bold=False):
    """返回等宽字体元组。"""
    return (FONT_MONO, size, "bold") if bold else (FONT_MONO, size)


def category_color(name):
    """根据分类名稳定地选取一个颜色（跨进程稳定）。"""
    if not name:
        return CATEGORY_COLORS[0]
    digest = hashlib.md5(str(name).encode("utf-8")).digest()
    return CATEGORY_COLORS[digest[0] % len(CATEGORY_COLORS)]


# ─────────────────────────────────────────────────────────────
# ttk 样式
# ─────────────────────────────────────────────────────────────

def _configure(style, name, **kwargs):
    """带降级保护的 style.configure。"""
    try:
        style.configure(name, **kwargs)
    except Exception:
        # 某些选项在特定主题下不支持，忽略即可
        pass


def _map(style, name, **kwargs):
    """带降级保护的 style.map。"""
    try:
        style.map(name, **kwargs)
    except Exception:
        pass


def apply(root=None):
    """
    配置全局 ttk 样式（clam 主题），应用到 root。
    幂等：可重复调用。
    """
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    bg = COLORS["bg"]
    panel = COLORS["panel"]
    card = COLORS["card"]
    border = COLORS["border"]
    text = COLORS["text"]
    dim = COLORS["text_dim"]
    mute = COLORS["text_mute"]
    accent = COLORS["accent"]
    input_bg = COLORS["input"]

    # 基础
    _configure(style, ".", background=bg, foreground=text,
               fieldbackground=input_bg, bordercolor=border,
               troughcolor=panel, focuscolor=accent,
               lightcolor=border, darkcolor=border, selectbackground=accent,
               selectforeground=bg, insertcolor=text)

    # 框架
    _configure(style, "TFrame", background=bg)
    _configure(style, "Panel.TFrame", background=panel)
    _configure(style, "Card.TFrame", background=card)

    # 标签
    _configure(style, "TLabel", background=bg, foreground=text)
    _configure(style, "Title.TLabel", background=bg, foreground=text,
               font=font(16, True))
    _configure(style, "Panel.TLabel", background=panel, foreground=text)
    _configure(style, "Dim.TLabel", background=bg, foreground=dim)
    _configure(style, "Card.TLabel", background=card, foreground=text)
    _configure(style, "Card.Dim.TLabel", background=card, foreground=dim)
    _configure(style, "Accent.TLabel", background=bg, foreground=accent)
    _configure(style, "Mute.TLabel", background=bg, foreground=mute)

    # 按钮
    _configure(style, "TButton", background=card, foreground=text,
               bordercolor=border, focuscolor=accent,
               relief="flat", padding=(10, 5), font=font(9))
    _map(style, "TButton",
         background=[("active", COLORS["card_hover"]), ("pressed", COLORS["card_active"])],
         foreground=[("disabled", mute)])

    _configure(style, "Accent.TButton", background=accent, foreground=bg,
               bordercolor=accent, focuscolor=accent,
               relief="flat", padding=(10, 5), font=font(9, True))
    _map(style, "Accent.TButton",
         background=[("active", "#5FE8FF"), ("pressed", COLORS["accent_dim"])],
         foreground=[("active", bg)])

    _configure(style, "Ghost.TButton", background=card, foreground=dim,
               bordercolor=border, focuscolor=accent,
               relief="flat", padding=(8, 4), font=font(8))
    _map(style, "Ghost.TButton",
         background=[("active", COLORS["card_hover"])],
         foreground=[("active", text)])

    _configure(style, "Danger.TButton", background=card, foreground=COLORS["danger"],
               bordercolor=border, focuscolor=COLORS["danger"],
               relief="flat", padding=(8, 4), font=font(8))
    _map(style, "Danger.TButton",
         background=[("active", COLORS["card_hover"])])

    # 输入框
    _configure(style, "TEntry", fieldbackground=input_bg, foreground=text,
               bordercolor=border, insertcolor=text, padding=5)

    # 下拉框
    _configure(style, "TCombobox", fieldbackground=input_bg, foreground=text,
               background=card, bordercolor=border, arrowcolor=text,
               padding=4)
    _map(style, "TCombobox",
         fieldbackground=[("readonly", input_bg)],
         foreground=[("readonly", text)],
         selectbackground=[("readonly", input_bg)],
         selectforeground=[("readonly", text)])

    # 复选
    _configure(style, "TCheckbutton", background=bg, foreground=text,
               focuscolor=accent, font=font(9))
    _map(style, "TCheckbutton",
         background=[("active", bg)],
         indicatorcolor=[("selected", accent), ("!selected", border)])
    _configure(style, "Card.TCheckbutton", background=card, foreground=text,
               focuscolor=accent, font=font(9))
    _map(style, "Card.TCheckbutton",
         background=[("active", card)],
         indicatorcolor=[("selected", accent), ("!selected", border)])

    # 滚动条
    _configure(style, "Vertical.TScrollbar", background=card, troughcolor=panel,
               bordercolor=panel, arrowcolor=dim, relief="flat")
    _map(style, "Vertical.TScrollbar",
         background=[("active", COLORS["card_hover"])])
    _configure(style, "Horizontal.TScrollbar", background=card, troughcolor=panel,
               bordercolor=panel, arrowcolor=dim, relief="flat")
    _map(style, "Horizontal.TScrollbar",
         background=[("active", COLORS["card_hover"])])

    # 分隔线
    _configure(style, "TSeparator", background=border)

    # 笔记本（设置页）
    _configure(style, "TNotebook", background=bg, bordercolor=border,
               tabmargins=(0, 0, 0, 0))
    _configure(style, "TNotebook.Tab", background=panel, foreground=dim,
               bordercolor=border, padding=(12, 6), font=font(9))
    _map(style, "TNotebook.Tab",
         background=[("selected", card), ("active", COLORS["card_hover"])],
         foreground=[("selected", text)])

    return style


# ─────────────────────────────────────────────────────────────
# 可滚动容器
# ─────────────────────────────────────────────────────────────

def glassify(win, settings=None, *, alpha=None, no_activate: bool = False) -> bool:
    """
    给窗口套上原生毛玻璃（Windows 10 1803+ 的真实模糊背景）。

    Args:
        win: 任意 tkinter 窗口
        settings: AppSettings；None 表示使用默认参数
        alpha: 覆盖整体不透明度；None 表示读取设置
        no_activate: 点击不抢焦点（悬浮提示类窗口）
    """
    try:
        import windows_fx
    except Exception:
        return False
    if not windows_fx.IS_WINDOWS:
        return False

    enabled, mode = True, "blur"
    tint, tint_alpha, use_alpha = COLORS["bg"], 112, alpha
    if settings is not None:
        try:
            enabled = bool(settings.get("ui.glass_enabled", True))
            mode = settings.get("ui.glass_mode", "blur") or "blur"
            tint = settings.get("ui.glass_tint", COLORS["bg"]) or COLORS["bg"]
            tint_alpha = int(settings.get("ui.glass_tint_alpha", 112) or 112)
            if use_alpha is None:
                use_alpha = float(settings.get("ui.glass_alpha", 0.97) or 0.97)
        except Exception:
            pass
    if not enabled:
        return False
    try:
        return windows_fx.apply_glass(
            win, tint=tint, tint_alpha=tint_alpha, mode=mode,
            alpha=use_alpha, rounded=True, no_activate=no_activate)
    except Exception:
        return False


class ScrollableFrame(tk.Frame):
    """带垂直滚动条的滚动容器，内容较少时自动隐藏滚动条。"""

    def __init__(self, master, bg=None, **kwargs):
        bg = bg or COLORS["bg"]
        super().__init__(master, bg=bg, **kwargs)
        self._bg = bg
        self._vbar_visible = True

        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)

        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.canvas.configure(yscrollcommand=self.vbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vbar.pack(side="right", fill="y")

        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Enter>", self._bind_wheel)
        self.canvas.bind("<Leave>", self._unbind_wheel)
        self.inner.bind("<Enter>", self._bind_wheel)
        self.inner.bind("<Leave>", self._unbind_wheel)

    def _on_inner_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._sync_vbar()

    def _on_canvas_configure(self, event):
        try:
            self.canvas.itemconfigure(self._window, width=event.width)
        except Exception:
            pass
        self._sync_vbar()

    def _sync_vbar(self):
        """内容放得下时隐藏滚动条。"""
        try:
            inner_h = self.inner.winfo_reqheight()
            canvas_h = self.canvas.winfo_height()
            if inner_h <= canvas_h:
                if self._vbar_visible:
                    self.vbar.pack_forget()
                    self._vbar_visible = False
                self.canvas.yview_moveto(0)
            else:
                if not self._vbar_visible:
                    self.vbar.pack(side="right", fill="y")
                    self._vbar_visible = True
        except Exception:
            pass

    def _bind_wheel(self, event):
        """仅在指针位于容器内时绑定滚轮。"""
        try:
            self.canvas.bind_all("<MouseWheel>", self._on_wheel)
            self.canvas.bind_all("<Button-4>", self._on_wheel)
            self.canvas.bind_all("<Button-5>", self._on_wheel)
        except Exception:
            pass

    def _unbind_wheel(self, event):
        try:
            self.canvas.unbind_all("<MouseWheel>")
            self.canvas.unbind_all("<Button-4>")
            self.canvas.unbind_all("<Button-5>")
        except Exception:
            pass

    def _on_wheel(self, event):
        try:
            if getattr(event, "num", 0) == 4:
                self.canvas.yview_scroll(-1, "units")
            elif getattr(event, "num", 0) == 5:
                self.canvas.yview_scroll(1, "units")
            else:
                delta = -1 * (int(event.delta) // 120) if getattr(event, "delta", 0) else 0
                self.canvas.yview_scroll(delta, "units")
        except Exception:
            pass

    def clear(self):
        """清空内部所有卡片。"""
        for child in self.inner.winfo_children():
            child.destroy()

    def scroll_to_top(self):
        """滚动到顶部。"""
        try:
            self.canvas.yview_moveto(0)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────
# hover 辅助
# ─────────────────────────────────────────────────────────────

def hover(widget, normal, active):
    """为 tk widget 绑定鼠标悬停变色（bg 与 highlightbackground）。"""
    def on_enter(event):
        try:
            widget.configure(bg=active)
        except Exception:
            pass
        try:
            widget.configure(highlightbackground=active)
        except Exception:
            pass

    def on_leave(event):
        try:
            widget.configure(bg=normal)
        except Exception:
            pass
        try:
            widget.configure(highlightbackground=normal)
        except Exception:
            pass

    widget.bind("<Enter>", on_enter, add="+")
    widget.bind("<Leave>", on_leave, add="+")
