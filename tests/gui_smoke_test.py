r"""
Clipboard Queue 界面烟雾测试（会短暂弹出窗口后自动关闭）

覆盖：主题应用、卡片列表窗口、锁定/掩码展示、搜索与分类筛选、
选择与删除、设置窗口（5 个分页）、解锁对话框、设置密码对话框、托盘图标。

运行： python tests\gui_smoke_test.py
"""

import os
import sys
import tempfile

# 必须在导入项目模块前隔离数据目录
TEMP_APPDATA = tempfile.mkdtemp(prefix="clipqueue_gui_")
os.environ["APPDATA"] = TEMP_APPDATA

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, os.path.abspath(SRC))

import tkinter as tk  # noqa: E402
from tkinter import ttk  # noqa: E402

import ui_theme  # noqa: E402
import windows_fx  # noqa: E402
import settings_window as settings_window_module  # noqa: E402
from app_settings import AppSettings  # noqa: E402
from queue_manager import QueueManager  # noqa: E402
from security import Security  # noqa: E402
from main import QueueListWindow, PasswordDialog, create_icon_image  # noqa: E402
from settings_window import SettingsWindow, _PasswordSetDialog  # noqa: E402

PASS = []
FAIL = []


def check(name, condition, detail=""):
    if condition:
        PASS.append(name)
        print(f"  [PASS] {name}")
    else:
        FAIL.append(f"{name} — {detail}")
        print(f"  [FAIL] {name} — {detail}")


def pump(root, times=4):
    for _ in range(times):
        try:
            root.update_idletasks()
            root.update()
        except Exception:
            pass


def collect_texts(widget, out=None):
    """递归收集控件树中所有 Label/Button 的文本。"""
    out = [] if out is None else out
    try:
        text = widget.cget("text")
        if text:
            out.append(str(text))
    except Exception:
        pass
    for child in widget.winfo_children():
        collect_texts(child, out)
    return out


class NoWait:
    """让模态对话框的 wait_window 立即返回（测试专用）。"""

    def __enter__(self):
        self._orig = tk.Toplevel.wait_window
        tk.Toplevel.wait_window = lambda self_, *a, **k: None
        return self

    def __exit__(self, *exc):
        tk.Toplevel.wait_window = self._orig
        return False


def main():
    print("=" * 62)
    print("Clipboard Queue 界面烟雾测试")
    print(f"临时数据目录: {TEMP_APPDATA}")
    print("=" * 62)

    root = tk.Tk()
    root.withdraw()

    settings = AppSettings()
    queue = QueueManager(settings=settings)
    security = Security(settings)

    # 准备数据：普通 / 锁定分类 / 单条 secret / 代码
    queue.clear()
    queue.add_category("工作", color="#35D07F")
    items = [
        queue.enqueue("这是一条普通文本内容，用于测试卡片展示。",
                      title="普通内容", category="工作"),
        queue.enqueue("我的银行卡密码是 000000",
                      title="敏感信息", category="密码"),
        queue.enqueue("def hello():\n    return 'world'",
                      title="代码片段", category="代码", secret=True),
        queue.enqueue("https://www.luogu.com.cn/problem/P1001", title="题目链接"),
    ]

    # ── 1. 主题与图标 ──
    print("\n[1] 主题与托盘图标")
    style = ui_theme.apply(root)
    check("ttk 主题应用成功", style is not None)
    icon0 = create_icon_image(0)
    icon9 = create_icon_image(9)
    check("托盘图标尺寸与模式正确",
          icon0.size == (64, 64) and icon0.mode == "RGBA")
    check("角标图标可生成", icon9.size == (64, 64))

    # ── 2. 卡片列表窗口 ──
    print("\n[2] 卡片列表窗口")
    copied = []
    changed = []
    win = QueueListWindow(
        root, queue,
        settings=settings, security=security,
        on_copy=lambda it: copied.append(it),
        on_paste=lambda it: None,
        confirm_delete=lambda: False,
        on_changed=lambda: changed.append(True),
    )
    win.show()
    pump(root, 6)
    check("主窗口已打开", bool(win.window and win.window.winfo_exists()))
    check("每条内容一张卡片", len(win._cards) == len(items), str(len(win._cards)))
    check("计数标签正确", "4 项" in str(win.count_lbl.cget("text")), win.count_lbl.cget("text"))
    check("分类筛选条已生成", len(win._cat_bar.winfo_children()) >= 4,
          str(len(win._cat_bar.winfo_children())))

    protected_item = items[1]
    normal_item = items[0]
    card_map = {it.get("id"): card for card, it in win._cards}
    protected_texts = collect_texts(card_map[protected_item["id"]])
    normal_texts = collect_texts(card_map[normal_item["id"]])
    check("锁定条目显示密码徽章", any("🔒 密码" in t for t in protected_texts))
    check("锁定条目正文被掩码",
          any("••••••••" in t for t in protected_texts)
          and not any("000000" in t for t in protected_texts))
    check("锁定条目显示「受保护」提示", any("受保护" in t for t in protected_texts))
    check("普通条目正常显示正文",
          any("普通文本内容" in t for t in normal_texts)
          and not any("••••••••" in t for t in normal_texts))
    check("卡片按钮齐全",
          all(any(t == b for t in normal_texts) for b in ("复制", "粘贴", "命名", "分类", "置顶", "删除")))

    # ── 3. 搜索与筛选 ──
    print("\n[3] 搜索与分类筛选")
    win._filter_category = "全部"
    win._search_var.set("代码")
    win._do_refresh()
    pump(root)
    check("搜索命中标题/内容", len(win._cards) == 1, str(len(win._cards)))

    win._search_var.set("")
    win._set_filter("密码")
    pump(root)
    check("按锁定分类筛选", len(win._cards) == 1
          and win._cards[0][1]["id"] == protected_item["id"])

    win._set_filter("全部")
    pump(root)
    check("切回全部恢复 4 张卡", len(win._cards) == 4)

    # ── 4. 选择与操作 ──
    print("\n[4] 选择与操作")
    win._select_card(normal_item)
    pump(root)
    check("卡片可选中", win._selected_id == normal_item["id"])

    win._copy_item(normal_item)
    pump(root, 6)
    check("复制走外部回调", bool(copied) and copied[-1]["id"] == normal_item["id"])

    before = queue.count()
    win._delete_item(queue.get_item(items[3]["id"]))
    pump(root, 6)
    check("删除条目生效", queue.count() == before - 1)
    check("删除后卡片刷新", len(win._cards) == queue.count())

    # 删除前二次确认：需要确认时「取消」不删除、「确定」才删除
    import main as main_module
    real_ask = main_module.messagebox.askyesno
    win.confirm_delete = lambda: True
    target = queue.get_item(items[2]["id"])
    try:
        main_module.messagebox.askyesno = lambda *a, **k: False
        before = queue.count()
        win._delete_item(target)
        check("确认框取消时不删除", queue.count() == before)
        main_module.messagebox.askyesno = lambda *a, **k: True
        win._delete_item(target)
        pump(root, 6)
        check("确认框确定后删除", queue.count() == before - 1)
    finally:
        main_module.messagebox.askyesno = real_ask
    win.confirm_delete = lambda: False

    win._on_close()
    check("主窗口可关闭", win.window is None)

    # ── 5. 设置窗口 ──
    print("\n[5] 设置窗口")
    applied = []
    sw = SettingsWindow(root, settings, security, queue, on_apply=lambda: applied.append(True))
    sw.show()
    pump(root, 6)
    check("设置窗口已打开", bool(sw.window and sw.window.winfo_exists()))
    tabs = [w for w in sw.window.winfo_children() if isinstance(w, ttk.Notebook)]
    check("设置分页数为 5", bool(tabs) and len(tabs[0].tabs()) == 5,
          str(len(tabs[0].tabs()) if tabs else -1))
    check("分类列表已填充", sw._cat_list.size() >= 4, str(sw._cat_list.size()))
    check("锁定分类带锁标记",
          any(str(sw._cat_list.get(i)).startswith("🔒") for i in range(sw._cat_list.size())))

    data = sw._collect()
    check("设置项收集完整",
          {"queue.max_items", "queue.persist", "hotkeys.copy",
           "general.show_notifications"} <= set(data))
    check("含毛玻璃设置项",
          {"ui.glass_enabled", "ui.glass_mode", "ui.glass_alpha"} <= set(data))

    # ── 毛玻璃 / 原生特效 ──
    check("识别到 Windows 平台", windows_fx.IS_WINDOWS is True)
    geo = windows_fx.screen_geometry()
    check("屏幕尺寸有效", geo[2] > 0 and geo[3] > 0, str(geo))
    check("毛玻璃调用不抛异常", isinstance(windows_fx.enable_blur(root), bool))
    check("窗口查询返回结构正确",
          isinstance(windows_fx.window_under_cursor(), dict))
    check("glassify 返回布尔值", isinstance(ui_theme.glassify(sw.window, settings), bool))

    # 保存路径：拦掉真实的自启注册表写入与弹窗
    real_autostart = settings_window_module.set_autostart
    real_info = settings_window_module.messagebox.showinfo
    real_error = settings_window_module.messagebox.showerror
    settings_window_module.set_autostart = lambda *a, **k: True
    settings_window_module.messagebox.showinfo = lambda *a, **k: None
    settings_window_module.messagebox.showerror = lambda *a, **k: None
    try:
        sw._vars["queue.max_items"].set("25")
        sw._save_and_apply()
    finally:
        settings_window_module.set_autostart = real_autostart
        settings_window_module.messagebox.showinfo = real_info
        settings_window_module.messagebox.showerror = real_error
    pump(root)
    check("保存后写回设置", settings.get("queue.max_items") == 25)
    check("保存触发应用回调", bool(applied))

    sw.show()
    pump(root)
    sw._on_close()
    check("设置窗口可关闭", sw.window is None)

    # ── 6. 解锁对话框 ──
    print("\n[6] 解锁对话框")
    security.set_password("abcd1234")
    with NoWait():
        dlg = PasswordDialog(root, security)
    pump(root)
    check("解锁对话框已构建", bool(dlg.window and dlg.window.winfo_exists()))
    dlg.entry.insert(0, "错误密码")
    dlg._ok()
    check("错误密码给出提示", "错误" in str(dlg.msg.cget("text")))
    dlg.entry.delete(0, tk.END)
    dlg.entry.insert(0, "abcd1234")
    dlg._ok()
    check("正确密码解锁成功", dlg.result() is True)

    # ── 7. 设置密码对话框 ──
    print("\n[7] 设置密码对话框")
    with NoWait():
        pd = _PasswordSetDialog(root)
    pump(root)
    pd.e1.insert(0, "123")
    pd.e2.insert(0, "123")
    pd._ok()
    check("密码过短被拒绝", "至少" in str(pd.msg.cget("text")))
    pd.e1.delete(0, tk.END)
    pd.e2.delete(0, tk.END)
    pd.e1.insert(0, "good1234")
    pd.e2.insert(0, "good5678")
    pd._ok()
    check("两次输入不一致被拒绝", "不一致" in str(pd.msg.cget("text")))
    pd.e2.delete(0, tk.END)
    pd.e2.insert(0, "good1234")
    pd._ok()
    check("两次一致时返回密码", pd.result() == "good1234")

    # ── 收尾 ──
    try:
        root.destroy()
    except Exception:
        pass

    print("\n" + "=" * 62)
    print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    for item in FAIL:
        print(f"  [X] {item}")
    print("=" * 62)

    import shutil
    shutil.rmtree(TEMP_APPDATA, ignore_errors=True)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
