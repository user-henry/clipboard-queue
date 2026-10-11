"""
Clipboard Queue - 设置窗口
深色科技感设置页：常规 / 队列 / 分类与密码 / 快捷键 / 存储。
保存即持久化并即时应用到运行中的程序。
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

from ui_theme import (COLORS, CATEGORY_COLORS, font, apply, glassify)
from app_settings import AppSettings
from security import Security


# ─────────────────────────────────────────────────────────────
# 开机自启（真实写注册表 HKCU Run）
# ─────────────────────────────────────────────────────────────

def set_autostart(enabled, app_name="ClipboardQueue", exe_path=None):
    """写入/删除 HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run。"""
    try:
        import winreg
        if exe_path is None:
            if getattr(sys, "frozen", False):
                exe_path = '"%s"' % sys.executable
            else:
                script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
                exe_path = '"%s" "%s"' % (sys.executable, script)
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE,
        )
        if enabled:
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
        else:
            try:
                winreg.DeleteValue(key, app_name)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


def _validate_hotkey(s):
    """校验热键格式；返回 (合法, 规范化字符串)。"""
    s = (s or "").strip().lower()
    if not s:
        return False, s
    try:
        import keyboard
        keyboard.parse_hotkey(s)
        return True, s
    except Exception:
        # 降级：基本字符检查
        if len(s) > 40:
            return False, s
        for ch in s:
            if not (ch.isalnum() or ch in "+- "):
                return False, s
        return True, s


# ─────────────────────────────────────────────────────────────
# 设置窗口
# ─────────────────────────────────────────────────────────────

class SettingsWindow:
    """主题化设置窗口（ttk.Notebook 分页）。"""

    def __init__(self, root, settings, security=None, queue=None, on_apply=None):
        self._root = root
        self.settings = settings if settings is not None else AppSettings()
        self.security = security if security is not None else Security(self.settings)
        self.queue = queue
        self.on_apply = on_apply  # 保存/应用后回调（重注册热键、刷新 UI）
        self.window = None
        self._vars = {}
        self._combo_values = {}
        self._combo_display = {}

    # ── 显示 ──

    def show(self):
        if self.window and self.window.winfo_exists():
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()
            return

        apply(self._root)
        self.window = tk.Toplevel(self._root)
        self.window.title("Clipboard Queue - 设置")
        self.window.geometry("700x580")
        self.window.minsize(640, 520)
        self.window.configure(bg=COLORS["bg"])
        glassify(self.window, self.settings)

        self._build_ui()
        self._load_values()

        self.window.protocol("WM_DELETE_WINDOW", self._on_close)
        self.window.bind("<Escape>", lambda e: self._on_close())
        self.window.focus_force()

    # ── UI 构建 ──

    def _build_ui(self):
        nb = ttk.Notebook(self.window)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 4))

        self._tab_general = self._make_tab(nb, "常规")
        self._tab_queue = self._make_tab(nb, "队列")
        self._tab_security = self._make_tab(nb, "分类与密码")
        self._tab_hotkeys = self._make_tab(nb, "快捷键")
        self._tab_storage = self._make_tab(nb, "存储")

        self._build_general()
        self._build_queue()
        self._build_security()
        self._build_hotkeys()
        self._build_storage()

        # 底部按钮
        bar = tk.Frame(self.window, bg=COLORS["panel"])
        bar.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=10)
        ttk.Button(bar, text="取消", command=self._on_close,
                   style="Ghost.TButton").pack(side=tk.RIGHT, padx=4)
        ttk.Button(bar, text="应用", command=self._save_and_apply,
                   style="TButton").pack(side=tk.RIGHT, padx=4)
        ttk.Button(bar, text="保存", command=self._save_and_apply,
                   style="Accent.TButton").pack(side=tk.RIGHT, padx=4)

    def _make_tab(self, nb, title):
        tab = tk.Frame(nb, bg=COLORS["bg"])
        nb.add(tab, text=title)
        return tab

    # ── 常规 ──

    def _build_general(self):
        tab = self._tab_general
        self._check(tab, "general.auto_start", "开机自动启动")
        self._check(tab, "general.single_instance", "单实例运行（防止重复启动）")
        self._check(tab, "general.show_notifications", "显示 Windows 通知")
        self._check(tab, "general.notification_sound", "通知提示音")
        self._check(tab, "general.confirm_before_delete", "删除前二次确认")

        tk.Frame(tab, bg=COLORS["border"], height=1).pack(fill=tk.X, padx=16, pady=(14, 6))
        tk.Label(tab, text="界面与特效", bg=COLORS["bg"], fg=COLORS["accent"],
                 font=font(9, True)).pack(anchor="w", padx=16)
        self._check(tab, "ui.glass_enabled", "毛玻璃背景（窗口背后真实模糊）")
        self._combo_row(tab, "玻璃模式", "ui.glass_mode", ["blur", "acrylic"],
                        ["blur（平滑，推荐）", "acrylic（更亮，可能掉帧）"])
        self._entry_row(tab, "窗口不透明度（0.80 - 1.00）", "ui.glass_alpha")
        self._entry_row(tab, "玻璃染色（#RRGGBB）", "ui.glass_tint")
        self._entry_row(tab, "染色浓度（0 - 255）", "ui.glass_tint_alpha")

    # ── 队列 ──

    def _build_queue(self):
        tab = self._tab_queue
        self._check(tab, "queue.persist", "本地保存记录（关闭后仅内存保留，退出即清空）")
        self._entry_row(tab, "队列上限（0 = 不限制）", "queue.max_items")
        self._check(tab, "queue.dedupe", "入队去重（跳过相同内容）")
        self._combo_row(tab, "弹出方向", "queue.pop_direction", ["head", "tail"],
                        ["队首（先进先出）", "队尾（后进先出）"])
        self._check(tab, "queue.clear_clipboard_after_paste", "粘贴后清空剪贴板")
        self._check(tab, "queue.restore_user_clipboard_after_paste", "粘贴后恢复用户原剪贴板")
        self._entry_row(tab, "恢复延迟（秒）", "queue.restore_delay_seconds")

    # ── 分类与密码 ──

    def _build_security(self):
        tab = self._tab_security

        # 密码区
        pwd_frame = tk.LabelFrame(tab, text="访问密码", bg=COLORS["bg"],
                                  fg=COLORS["text"], font=font(9, True),
                                  bd=1, relief="groove",
                                  highlightbackground=COLORS["border"],
                                  highlightthickness=1)
        pwd_frame.pack(fill=tk.X, padx=16, pady=8)

        self._pwd_status = tk.Label(pwd_frame, text="", bg=COLORS["bg"],
                                    fg=COLORS["text_dim"], font=font(9))
        self._pwd_status.pack(side=tk.LEFT, padx=10, pady=8)
        ttk.Button(pwd_frame, text="设置密码", style="Ghost.TButton",
                   command=self._set_password).pack(side=tk.RIGHT, padx=4, pady=6)
        ttk.Button(pwd_frame, text="清除密码", style="Danger.TButton",
                   command=self._clear_password).pack(side=tk.RIGHT, padx=4, pady=6)

        self._entry_row(tab, "解锁缓存超时（秒）", "security.unlock_ttl_seconds")
        self._entry_row(tab, "秘密内容自动清空剪贴板（秒，0=关）",
                        "security.auto_clear_clipboard_seconds")

        # 分类管理区
        cat_frame = tk.LabelFrame(tab, text="分类管理", bg=COLORS["bg"],
                                  fg=COLORS["text"], font=font(9, True),
                                  bd=1, relief="groove",
                                  highlightbackground=COLORS["border"],
                                  highlightthickness=1)
        cat_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)

        top = tk.Frame(cat_frame, bg=COLORS["bg"])
        top.pack(fill=tk.X, padx=8, pady=6)
        self._cat_list = tk.Listbox(top, bg=COLORS["input"], fg=COLORS["text"],
                                    selectbackground=COLORS["card_active"],
                                    selectforeground=COLORS["text"],
                                    highlightthickness=1,
                                    highlightbackground=COLORS["border"],
                                    height=7, font=font(9), exportselection=False)
        self._cat_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        btn_col = tk.Frame(top, bg=COLORS["bg"])
        btn_col.pack(side=tk.RIGHT, fill=tk.Y, padx=(6, 0))
        ttk.Button(btn_col, text="新增", style="Ghost.TButton",
                   command=self._add_category).pack(fill=tk.X, pady=1)
        ttk.Button(btn_col, text="重命名", style="Ghost.TButton",
                   command=self._rename_category).pack(fill=tk.X, pady=1)
        ttk.Button(btn_col, text="删除", style="Danger.TButton",
                   command=self._delete_category).pack(fill=tk.X, pady=1)
        ttk.Button(btn_col, text="锁定/解锁", style="Ghost.TButton",
                   command=self._toggle_lock).pack(fill=tk.X, pady=1)

        color_row = tk.Frame(cat_frame, bg=COLORS["bg"])
        color_row.pack(fill=tk.X, padx=8, pady=(0, 8))
        tk.Label(color_row, text="颜色", bg=COLORS["bg"], fg=COLORS["text_dim"],
                 font=font(9)).pack(side=tk.LEFT)
        self._cat_color = tk.StringVar(value=CATEGORY_COLORS[0])
        cb = ttk.Combobox(color_row, textvariable=self._cat_color, values=CATEGORY_COLORS,
                          state="readonly", width=12)
        cb.pack(side=tk.LEFT, padx=6)
        self._swatch = tk.Label(color_row, text="   ", bg=CATEGORY_COLORS[0],
                                width=4, relief="solid", bd=1)
        self._swatch.pack(side=tk.LEFT)
        self._cat_color.trace_add("write", lambda *a: self._update_swatch())
        ttk.Button(color_row, text="应用到选中分类", style="Ghost.TButton",
                   command=self._apply_color).pack(side=tk.LEFT, padx=8)

    # ── 快捷键 ──

    def _build_hotkeys(self):
        tab = self._tab_hotkeys
        self._entry_row(tab, "加入队列", "hotkeys.copy")
        self._entry_row(tab, "从队列粘贴", "hotkeys.paste")
        self._entry_row(tab, "清空队列", "hotkeys.clear")
        self._entry_row(tab, "打开主窗口", "hotkeys.show")
        tk.Label(tab, text="格式示例：ctrl+alt+c（使用 + 连接按键，保存后即时生效）",
                 bg=COLORS["bg"], fg=COLORS["text_mute"], font=font(8)).pack(
            anchor=tk.W, padx=16, pady=6)

    # ── 存储 ──

    def _build_storage(self):
        tab = self._tab_storage
        data_dir = os.path.dirname(self.settings._path)

        row = tk.Frame(tab, bg=COLORS["bg"])
        row.pack(fill=tk.X, padx=16, pady=8)
        tk.Label(row, text="数据目录", bg=COLORS["bg"], fg=COLORS["text_dim"],
                 font=font(9)).pack(side=tk.LEFT)
        self._dir_lbl = tk.Label(row, text=data_dir, bg=COLORS["bg"],
                                 fg=COLORS["text"], font=font(9), anchor=tk.E)
        self._dir_lbl.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=8)

        btn_row = tk.Frame(tab, bg=COLORS["bg"])
        btn_row.pack(fill=tk.X, padx=16, pady=6)
        ttk.Button(btn_row, text="打开数据目录", style="TButton",
                   command=self._open_data_dir).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_row, text="导出备份 JSON", style="TButton",
                   command=self._export_json).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_row, text="导入备份 JSON", style="TButton",
                   command=self._import_json).pack(side=tk.LEFT, padx=3)

        btn_row2 = tk.Frame(tab, bg=COLORS["bg"])
        btn_row2.pack(fill=tk.X, padx=16, pady=6)
        ttk.Button(btn_row2, text="清空全部记录", style="Danger.TButton",
                   command=self._clear_all).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_row2, text="恢复默认设置", style="TButton",
                   command=self._reset_defaults).pack(side=tk.LEFT, padx=3)

    # ── 通用控件辅助 ──

    def _check(self, parent, key, text):
        var = tk.BooleanVar(value=False)
        self._vars[key] = var
        row = tk.Frame(parent, bg=COLORS["bg"])
        row.pack(fill=tk.X, padx=16, pady=5)
        ttk.Checkbutton(row, text=text, variable=var, style="TCheckbutton").pack(anchor=tk.W)

    def _entry_row(self, parent, label, key):
        var = tk.StringVar(value="")
        self._vars[key] = var
        row = tk.Frame(parent, bg=COLORS["bg"])
        row.pack(fill=tk.X, padx=16, pady=5)
        tk.Label(row, text=label, bg=COLORS["bg"], fg=COLORS["text_dim"],
                 font=font(9)).pack(side=tk.LEFT)
        ent = ttk.Entry(row, textvariable=var, width=18)
        ent.pack(side=tk.RIGHT)

    def _combo_row(self, parent, label, key, values, display):
        self._combo_values[key] = values
        self._combo_display[key] = display
        var = tk.StringVar(value=display[0])
        self._vars[key] = var
        row = tk.Frame(parent, bg=COLORS["bg"])
        row.pack(fill=tk.X, padx=16, pady=5)
        tk.Label(row, text=label, bg=COLORS["bg"], fg=COLORS["text_dim"],
                 font=font(9)).pack(side=tk.LEFT)
        ttk.Combobox(row, textvariable=var, values=display,
                     state="readonly", width=22).pack(side=tk.RIGHT)

    # ── 读取/保存 ──

    def _load_values(self):
        s = self.settings
        for key, var in self._vars.items():
            val = s.get(key, None)
            if isinstance(var, tk.BooleanVar):
                var.set(bool(val))
            elif key in self._combo_values:
                vals = self._combo_values[key]
                disp = self._combo_display[key]
                idx = vals.index(str(val)) if str(val) in vals else 0
                var.set(disp[idx])
            else:
                var.set(str(val) if val is not None else "")
        self._refresh_password_status()
        self._refresh_categories()

    def _collect(self):
        data = {}
        for key, var in self._vars.items():
            if isinstance(var, tk.BooleanVar):
                data[key] = bool(var.get())
            elif key in self._combo_values:
                vals = self._combo_values[key]
                disp = self._combo_display[key]
                v = var.get()
                idx = disp.index(v) if v in disp else 0
                data[key] = vals[idx]
            else:
                data[key] = var.get()
        # 校验队列数值
        for k in ("queue.max_items", "security.unlock_ttl_seconds",
                  "security.auto_clear_clipboard_seconds", "queue.restore_delay_seconds",
                  "ui.glass_alpha", "ui.glass_tint_alpha"):
            try:
                v = data.get(k, "")
                if v == "":
                    data[k] = 0
                else:
                    data[k] = float(v) if k in ("queue.restore_delay_seconds",
                                                "ui.glass_alpha") else int(float(v))
            except Exception:
                data[k] = 0
        return data

    def _save_and_apply(self):
        # 校验热键
        for key in ("hotkeys.copy", "hotkeys.paste", "hotkeys.clear", "hotkeys.show"):
            ok, norm = _validate_hotkey(self._vars[key].get())
            if not ok:
                messagebox.showerror("快捷键无效",
                                     f"快捷键「{self._vars[key].get()}」格式不正确，请修改后再保存。")
                return
            self._vars[key].set(norm)

        data = self._collect()
        self.settings.update(data)
        try:
            set_autostart(bool(self.settings.get("general.auto_start", False)))
        except Exception:
            pass
        if self.on_apply:
            try:
                self.on_apply()
            except Exception as e:
                messagebox.showerror("应用失败", str(e))
                return
        messagebox.showinfo("已保存", "设置已保存并生效。")
        self._on_close()

    def _on_close(self):
        if self.window and self.window.winfo_exists():
            self.window.destroy()
            self.window = None

    # ── 密码 ──

    def _refresh_password_status(self):
        if hasattr(self, "_pwd_status"):
            if self.security.has_password():
                self._pwd_status.config(text="已设置密码", fg=COLORS["success"])
            else:
                self._pwd_status.config(text="未设置密码", fg=COLORS["text_dim"])

    def _set_password(self):
        dlg = _PasswordSetDialog(self._root)
        pw = dlg.result()
        if pw:
            if self.security.set_password(pw):
                self._refresh_password_status()
                messagebox.showinfo("成功", "访问密码已设置。")
            else:
                messagebox.showerror("失败", "密码至少需要 4 位。")

    def _clear_password(self):
        if not self.security.has_password():
            return
        if messagebox.askyesno("确认", "确定清除访问密码？"):
            self.security.clear_password()
            self._refresh_password_status()

    # ── 分类管理 ──

    def _refresh_categories(self):
        if not hasattr(self, "_cat_list"):
            return
        self._cat_list.delete(0, tk.END)
        if self.queue is None:
            return
        for cat in self.queue.get_categories():
            mark = "🔒 " if cat.get("locked") else ""
            self._cat_list.insert(tk.END, mark + cat["name"])

    def _selected_category(self):
        if self.queue is None or not hasattr(self, "_cat_list"):
            return None
        sel = self._cat_list.curselection()
        if not sel:
            return None
        cats = self.queue.get_categories()
        idx = sel[0]
        return cats[idx] if 0 <= idx < len(cats) else None

    def _add_category(self):
        if self.queue is None:
            return
        name = simpledialog.askstring("新增分类", "输入分类名称：", parent=self.window)
        if not name or not name.strip():
            return
        self.queue.add_category(name.strip())
        self._refresh_categories()

    def _rename_category(self):
        cat = self._selected_category()
        if not cat:
            messagebox.showinfo("提示", "请先选择一个分类")
            return
        new = simpledialog.askstring("重命名分类", "新名称：",
                                     initialvalue=cat["name"], parent=self.window)
        if not new or not new.strip():
            return
        self.queue.rename_category(cat["name"], new.strip())
        self._refresh_categories()

    def _delete_category(self):
        cat = self._selected_category()
        if not cat:
            messagebox.showinfo("提示", "请先选择一个分类")
            return
        if messagebox.askyesno("确认", f"删除分类「{cat['name']}」？其中的条目将归入「未分类」。"):
            self.queue.delete_category(cat["name"])
            self._refresh_categories()

    def _toggle_lock(self):
        cat = self._selected_category()
        if not cat:
            messagebox.showinfo("提示", "请先选择一个分类")
            return
        self.queue.set_category_locked(cat["name"], not cat.get("locked"))
        self._refresh_categories()

    def _update_swatch(self):
        try:
            self._swatch.config(bg=self._cat_color.get())
        except Exception:
            pass

    def _apply_color(self):
        cat = self._selected_category()
        if not cat:
            messagebox.showinfo("提示", "请先选择一个分类")
            return
        self.queue.add_category(cat["name"], color=self._cat_color.get(),
                                locked=cat.get("locked"))
        self._refresh_categories()

    # ── 存储操作 ──

    def _open_data_dir(self):
        data_dir = os.path.dirname(self.settings._path)
        try:
            os.startfile(data_dir)  # noqa: 仅在 Windows 可用
        except Exception:
            messagebox.showerror("错误", f"无法打开目录：{data_dir}")

    def _export_json(self):
        if self.queue is None:
            return
        path = filedialog.asksaveasfilename(
            parent=self.window, title="导出备份",
            defaultextension=".json",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")],
            initialfile="clipboard_queue_backup.json")
        if not path:
            return
        if self.queue.export_json(path):
            messagebox.showinfo("成功", f"已导出到：\n{path}")
        else:
            messagebox.showerror("失败", "导出失败。")

    def _import_json(self):
        if self.queue is None:
            return
        path = filedialog.askopenfilename(
            parent=self.window, title="导入备份",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")])
        if not path:
            return
        if messagebox.askyesno("确认", "导入将覆盖当前队列，是否继续？"):
            n = self.queue.import_json(path)
            messagebox.showinfo("完成", f"已导入 {n} 条记录。")
            if self.on_apply:
                try:
                    self.on_apply()
                except Exception:
                    pass

    def _clear_all(self):
        if self.queue is None:
            return
        if messagebox.askyesno("二次确认", "确定清空全部队列记录？此操作不可撤销。"):
            self.queue.clear()
            if self.on_apply:
                try:
                    self.on_apply()
                except Exception:
                    pass

    def _reset_defaults(self):
        if messagebox.askyesno("确认", "恢复默认设置？（访问密码会被保留）"):
            self.settings.reset()
            self._load_values()
            if self.on_apply:
                try:
                    self.on_apply()
                except Exception:
                    pass


# ─────────────────────────────────────────────────────────────
# 密码设置对话框（设置新密码 / 确认密码）
# ─────────────────────────────────────────────────────────────

class _PasswordSetDialog:
    """模态：新密码 / 确认密码，最少 4 位，两次不一致给出反馈。"""

    def __init__(self, root):
        self._result = None
        self.window = tk.Toplevel(root)
        self.window.title("设置访问密码")
        self.window.configure(bg=COLORS["bg"])
        self.window.resizable(False, False)
        self.window.transient(root)
        self.window.grab_set()

        box = tk.Frame(self.window, bg=COLORS["card"],
                       highlightthickness=1, highlightbackground=COLORS["border"])
        box.pack(padx=20, pady=20)

        tk.Label(box, text="设置访问密码", bg=COLORS["card"], fg=COLORS["text"],
                 font=font(12, True)).pack(pady=(14, 4))
        tk.Label(box, text="保护密码类条目的访问（最少 4 位）", bg=COLORS["card"],
                 fg=COLORS["text_dim"], font=font(8)).pack(pady=(0, 10))

        self.e1 = ttk.Entry(box, show="•", width=28)
        self.e1.pack(padx=20, pady=4)
        self.e2 = ttk.Entry(box, show="•", width=28)
        self.e2.pack(padx=20, pady=4)

        self.msg = tk.Label(box, text="", bg=COLORS["card"], fg=COLORS["danger"],
                            font=font(8))
        self.msg.pack(pady=4)

        btns = tk.Frame(box, bg=COLORS["card"])
        btns.pack(pady=(6, 14))
        ttk.Button(btns, text="取消", style="Ghost.TButton",
                   command=self._cancel).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="确定", style="Accent.TButton",
                   command=self._ok).pack(side=tk.LEFT, padx=4)

        self.e1.bind("<Return>", lambda e: self._ok())
        self.e2.bind("<Return>", lambda e: self._ok())
        self.window.bind("<Escape>", lambda e: self._cancel())

        self._center()
        self.e1.focus_force()
        self.window.wait_window()

    def _center(self):
        self.window.update_idletasks()
        w, h = 360, 260
        sw = self.window.winfo_screenwidth()
        sh = self.window.winfo_screenheight()
        self.window.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    def _ok(self):
        pw1 = self.e1.get()
        pw2 = self.e2.get()
        if len(pw1) < 4:
            self.msg.config(text="密码至少需要 4 位")
            return
        if pw1 != pw2:
            self.msg.config(text="两次输入的密码不一致")
            return
        self._result = pw1
        self.window.destroy()

    def _cancel(self):
        self._result = None
        self.window.destroy()

    def result(self):
        return self._result
