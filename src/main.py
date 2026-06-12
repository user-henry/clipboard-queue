"""
Clipboard Queue - 主入口
系统托盘图标 + 队列管理 + 全局热键
快捷键: Ctrl+Alt+C → 加入队列 | Ctrl+Alt+V → 粘贴 | Ctrl+Alt+Q → 清空
"""

import os
import sys
import ctypes
import time
import threading
import atexit
import tkinter as tk
from tkinter import ttk, messagebox
import pystray
from PIL import Image, ImageDraw

# 将 src 目录加入路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from queue_manager import QueueManager
from clipboard_helper import ClipboardHelper
from hotkey_manager import HotkeyManager
from notify_helper import NotifyHelper


# ═══════════════════════════════════════════════════════════════
# 图标生成
# ═══════════════════════════════════════════════════════════════

def create_icon_image(count=0):
    """创建 64x64 剪贴板图标（带队列数字角标）"""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = 8
    bx, by = margin, margin + 6
    bw, bh = size - margin * 2, size - margin * 2 - 6

    # 剪贴板主体
    draw.rounded_rectangle(
        [bx, by, bx + bw, by + bh], radius=6,
        fill=(64, 128, 200, 255), outline=(40, 100, 170, 255), width=2,
    )

    # 顶部夹子
    clip_w, clip_h = 16, 8
    clip_x = (size - clip_w) // 2
    draw.rounded_rectangle(
        [clip_x, by - 2, clip_x + clip_w, by + clip_h], radius=4,
        fill=(80, 150, 220, 255), outline=(40, 100, 170, 255), width=2,
    )

    # 内部横线
    line_y_start = by + clip_h + 12
    for i in range(3):
        ly = line_y_start + i * 8
        draw.rectangle(
            [bx + 10, ly, bx + bw - 10, ly + 3],
            fill=(255, 255, 255, 200),
        )

    # 角标数字
    if count > 0:
        badge_size = 22
        badge_x, badge_y = size - badge_size - 2, size - badge_size - 2
        draw.ellipse(
            [badge_x, badge_y, badge_x + badge_size, badge_y + badge_size],
            fill=(220, 60, 60, 255), outline=(180, 30, 30, 255), width=1,
        )

        count_str = str(count) if count < 100 else "99+"
        try:
            from PIL import ImageFont
            font_size = 12 if len(count_str) <= 2 else 8
            font = ImageFont.truetype("segoeui.ttf", font_size)
            bbox = draw.textbbox((0, 0), count_str, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text(
                (badge_x + (badge_size - tw) // 2, badge_y + (badge_size - th) // 2 - 1),
                count_str, fill=(255, 255, 255, 255), font=font,
            )
        except Exception:
            cx = badge_x + (badge_size // 2)
            cy = badge_y + (badge_size // 2)
            draw.text((cx - 4, cy - 6), count_str, fill=(255, 255, 255, 255))

    return img


# ═══════════════════════════════════════════════════════════════
# 队列列表窗口
# ═══════════════════════════════════════════════════════════════

class QueueListWindow:
    """点击托盘图标时弹出的队列列表窗口"""

    def __init__(self, root, queue_manager, on_copy=None, on_close=None):
        self._root = root          # tkinter 根窗口
        self.queue = queue_manager
        self.on_copy = on_copy
        self.on_close = on_close
        self.window = None
        self.tree = None
        self.count_lbl = None

    def show(self):
        """显示或聚焦窗口（必须在主线程调用）"""
        if self.window and self.window.winfo_exists():
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()
            self._refresh_list()
            return

        self.window = tk.Toplevel(self._root)
        self.window.title("Clipboard Queue - 队列列表")
        self.window.geometry("500x420")
        self.window.minsize(360, 260)
        self.window.configure(bg="#f2f2f2")

        # 居中
        self.window.update_idletasks()
        sw = self.window.winfo_screenwidth()
        sh = self.window.winfo_screenheight()
        self.window.geometry(f"+{(sw-500)//2}+{(sh-420)//2}")

        self._build_ui()
        self._refresh_list()

        self.window.protocol("WM_DELETE_WINDOW", self._on_window_close)
        self.window.bind("<Escape>", lambda e: self.window.destroy())
        self.window.bind("<F5>", lambda e: self._refresh_list())
        self.window.focus_force()

    def _on_window_close(self):
        if self.on_close:
            self.on_close()
        if self.window:
            self.window.destroy()
            self.window = None

    def _build_ui(self):
        # 标题栏
        header = tk.Frame(self.window, bg="#4080c8", height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header, text="剪贴板队列",
            fg="white", bg="#4080c8",
            font=("Microsoft YaHei UI", 12, "bold"),
        ).pack(side=tk.LEFT, padx=16, pady=12)

        self.count_lbl = tk.Label(
            header, text="", fg="white", bg="#4080c8",
            font=("Microsoft YaHei UI", 10),
        )
        self.count_lbl.pack(side=tk.RIGHT, padx=16, pady=12)

        # 列表区域
        list_frame = tk.Frame(self.window, bg="white")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 0))

        columns = ("time", "preview")
        self.tree = ttk.Treeview(
            list_frame, columns=columns, show="headings", selectmode="browse",
        )
        self.tree.heading("time", text="时间")
        self.tree.heading("preview", text="内容预览")
        self.tree.column("time", width=70, anchor="center")
        self.tree.column("preview", width=400, anchor="w")

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 双击复制到剪贴板
        self.tree.bind("<Double-1>", lambda e: self._copy_selected())

        # 按钮栏
        btn_frame = tk.Frame(self.window, bg="#f2f2f2")
        btn_frame.pack(fill=tk.X, padx=12, pady=10)

        style = ttk.Style()
        style.configure("Queue.TButton", font=("Microsoft YaHei UI", 9))

        ttk.Button(btn_frame, text="复制选中项", command=self._copy_selected,
                   style="Queue.TButton").pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="删除选中项", command=self._delete_selected,
                   style="Queue.TButton").pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="清空队列", command=self._clear_queue,
                   style="Queue.TButton").pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="关闭", command=self._on_window_close,
                   style="Queue.TButton").pack(side=tk.RIGHT, padx=3)

        # 提示文字
        hint = tk.Label(
            self.window, text="提示：双击或「复制选中项」将内容复制到剪贴板 | 按 F5 刷新列表",
            fg="#888", bg="#f2f2f2", font=("Microsoft YaHei UI", 8),
        )
        hint.pack(pady=(0, 4))

    def _refresh_list(self):
        if not self.tree:
            return
        for item in self.tree.get_children():
            self.tree.delete(item)

        items = self.queue.get_all()
        for i, item in enumerate(items):
            self.tree.insert("", tk.END, iid=str(i),
                             values=(item["time"], item["preview"]))

        count = self.queue.count()
        if self.count_lbl:
            self.count_lbl.config(text=f"共 {count} 项" if count > 0 else "队列为空")

    def _copy_selected(self):
        """将选中项复制到剪贴板，并从队列中移除"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("提示", "请先选择一项")
            return

        idx = int(selection[0])
        item = self.queue.remove_at(idx)
        if item is None:
            return

        if self.on_copy:
            self.on_copy(item["content"], item["preview"])

        self._refresh_list()
        if self.queue.is_empty():
            self._on_window_close()

    def _delete_selected(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("提示", "请先选择一项")
            return

        idx = int(selection[0])
        self.queue.remove_at(idx)
        self._refresh_list()

        if self.queue.is_empty():
            self._on_window_close()

    def _clear_queue(self):
        if self.queue.is_empty():
            return
        if messagebox.askyesno("确认清空", "确定要清空整个剪贴板队列吗？"):
            self.queue.clear()
            self._refresh_list()
            self._on_window_close()

    def destroy(self):
        if self.window and self.window.winfo_exists():
            self.window.destroy()
            self.window = None


# ═══════════════════════════════════════════════════════════════
# 主应用
# ═══════════════════════════════════════════════════════════════

class ClipboardQueueApp:
    """Clipboard Queue 主应用"""

    # 快捷键配置
    HK_COPY = "ctrl+alt+c"      # 加入队列
    HK_PASTE = "ctrl+alt+v"     # 从队列粘贴
    HK_CLEAR = "ctrl+alt+q"     # 清空队列

    def __init__(self):
        self.queue = QueueManager()
        self.clipboard = ClipboardHelper()
        self.hotkeys = HotkeyManager()
        self.notify = NotifyHelper()
        self.icon = None
        self.list_window = None
        self._root = None

    # ── 初始化 ──

    def _init_hotkeys(self):
        """注册全局热键"""
        self.hotkeys.register(self.HK_COPY, self._on_copy_to_queue)
        self.hotkeys.register(self.HK_PASTE, self._on_paste_from_queue)
        self.hotkeys.register(self.HK_CLEAR, self._on_clear_queue)
        self.hotkeys.start()

    # ── 热键回调（运行在独立 Timer 线程，已脱离 keyboard hook）──

    def _on_copy_to_queue(self):
        """Ctrl+Alt+C：先模拟 Ctrl+C 复制选中文本，再读剪贴板入队"""
        # 把当前选中的文本复制到系统剪贴板
        time.sleep(0.1)
        self.hotkeys.send_copy()
        # 等待剪贴板更新
        time.sleep(0.25)
        content = self.clipboard.read()
        if content and content.strip():
            self.queue.enqueue(content.strip(), "text")
            self._update_tray_icon()
            self.notify.show_enqueue(self.queue.count())
        else:
            self.notify.show("复制失败", "请先选中文字，再按 Ctrl+Alt+C")

    def _on_paste_from_queue(self):
        """Ctrl+Alt+V：从队列取出内容，写入剪贴板，模拟 Ctrl+V 粘贴"""
        if self.queue.is_empty():
            self.notify.show_empty()
            return
        item = self.queue.dequeue()
        if item is None:
            return
        self._do_paste(item)

    def _on_clear_queue(self):
        """Ctrl+Alt+Q：清空队列"""
        if self.queue.is_empty():
            return
        count = self.queue.count()
        self.queue.clear()
        self._update_tray_icon()
        self.notify.show(f"已清空 {count} 项", "队列为空")

    def _do_paste(self, item):
        """执行粘贴 + 自动恢复剪贴板"""
        self.clipboard.save_backup()
        self.clipboard.write(item["content"])
        # 等待剪贴板写入完成
        time.sleep(0.1)
        self.hotkeys.send_paste()
        self.clipboard.restore_after_delay(0.8)
        self._update_tray_icon()
        self.notify.show_paste(item["preview"])

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
                "显示队列列表",
                lambda: self._safe_call(self._show_queue_list),
                default=True,
            ),
            pystray.MenuItem(
                "清空队列",
                lambda: self._safe_call(self._tray_clear),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", lambda: self.shutdown()),
        )

    def _safe_call(self, func):
        """在主线程（tkinter 线程）中安全执行函数"""
        if self._root:
            self._root.after(0, func)

    def _tray_clear(self):
        if not self.queue.is_empty():
            cnt = self.queue.count()
            self.queue.clear()
            self._update_tray_icon()
            self.notify.show(f"已清空 {cnt} 项", "")

    def _show_queue_list(self):
        """打开/聚焦队列列表窗口（必须运行在主线程）"""
        if self.list_window and self.list_window.window and self.list_window.window.winfo_exists():
            self.list_window.show()
        else:
            self.list_window = QueueListWindow(
                self._root,
                self.queue,
                on_copy=lambda content, preview: self._list_copy(content, preview),
                on_close=lambda: setattr(self, "list_window", None),
            )
            self.list_window.show()

    def _list_copy(self, content, preview):
        """从列表窗口复制选中项到剪贴板"""
        self.clipboard.write(content)
        self._update_tray_icon()
        self.notify.show("已复制到剪贴板", preview[:40])

    # ── 生命周期 ──

    def run(self):
        """启动应用"""
        # 1. 创建隐藏的 tkinter 根窗口（必须在主线程）
        self._root = tk.Tk()
        self._root.withdraw()
        self._root.title("ClipboardQueue")

        # 2. 注册全局热键
        self._init_hotkeys()

        # 3. 创建托盘图标
        count = self.queue.count()
        self.icon = pystray.Icon(
            "ClipboardQueue",
            create_icon_image(count),
            f"Clipboard Queue - {'队列为空' if count == 0 else f'{count} 项'}",
            menu=self._create_tray_menu(),
        )

        # 4. 在独立线程中启动 pystray
        self.tray_thread = threading.Thread(target=self._run_tray, daemon=True)
        self.tray_thread.start()

        # 5. 注册清理
        atexit.register(self._cleanup)

        # 6. 运行 tkinter 主循环（在主线程）
        print(f"\n  Clipboard Queue 已启动")
        print(f"  {'─' * 40}")
        print(f"  Ctrl+Alt+C  →  加入队列")
        print(f"  Ctrl+Alt+V  →  从队列粘贴")
        print(f"  Ctrl+Alt+Q  →  清空队列")
        print(f"  点击托盘图标 →  查看/管理队列")
        print(f"  队列中有 {count} 项\n")

        try:
            self._root.mainloop()
        except KeyboardInterrupt:
            pass
        finally:
            self._cleanup()

    def _run_tray(self):
        """在独立线程中运行 pystray"""
        try:
            self.icon.run()
        except Exception:
            pass

    def shutdown(self):
        """优雅关闭"""
        print("[ClipboardQueue] 正在退出...")
        self._cleanup()
        if self._root:
            self._root.after(0, self._root.quit)

    def _cleanup(self):
        """清理资源"""
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
            if self.icon:
                self.icon.stop()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════════

def main():
    # 单实例互斥锁
    mutex_name = "Global\\ClipboardQueue_SingleInstance"
    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, False, mutex_name)
    if kernel32.GetLastError() == 183:
        kernel32.CloseHandle(mutex)
        # 尝试用窗口名找到已有实例
        try:
            hwnd = ctypes.windll.user32.FindWindowW(None, "ClipboardQueue")
            if hwnd:
                ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass
        print("[ClipboardQueue] 应用已在运行中，请查看系统托盘")
        return

    app = ClipboardQueueApp()
    app.run()
    kernel32.CloseHandle(mutex)


if __name__ == "__main__":
    main()
