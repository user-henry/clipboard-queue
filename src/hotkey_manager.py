"""
Clipboard Queue - 全局热键管理器
使用 keyboard 库注册系统级全局快捷键

关键设计：热键回调延迟 0.15s 执行，跳出 keyboard hook 上下文，
避免在 hook 回调内调用 keyboard.send() 导致的不稳定问题。
"""

import keyboard
import threading


class HotkeyManager:
    """全局热键注册与管理。"""

    DEFER_DELAY = 0.15  # 延迟执行时间（秒）

    def __init__(self):
        self._callbacks = {}
        self._running = False
        self._lock = threading.Lock()

    def register(self, hotkey, callback):
        """
        注册全局热键
        hotkey: 如 'ctrl+alt+c'
        callback: 触发时的回调函数（将在独立 Timer 线程中执行）
        """
        with self._lock:
            self._callbacks[hotkey] = callback

    def clear_registrations(self):
        """清空所有已登记的热键（不触发注销）。"""
        with self._lock:
            self._callbacks.clear()

    def configure(self, bindings):
        """
        一次性替换全部热键并重新注册。
        bindings: {hotkey: callback}
        """
        with self._lock:
            self._callbacks = dict(bindings or {})
        self.start()

    def start(self):
        """启动热键监听（先清理旧监听，再注册全部）。"""
        self.stop()
        self._running = True
        with self._lock:
            for hotkey, callback in self._callbacks.items():
                try:
                    # 延迟执行包装：hook 回调只启动 Timer，立即返回
                    # 实际工作在 Timer 线程中执行，此时已脱离 keyboard hook 上下文
                    def make_deferred(cb):
                        def wrapper():
                            threading.Timer(self.DEFER_DELAY, cb).start()
                        return wrapper

                    keyboard.add_hotkey(
                        hotkey,
                        make_deferred(callback),
                        suppress=True,
                    )
                    print(f"  [Hotkey] {hotkey} 已注册")
                except Exception as e:
                    print(f"  [Hotkey] 注册失败 {hotkey}: {e}")

    def stop(self):
        """停止所有热键监听。"""
        self._running = False
        try:
            keyboard.unhook_all()
        except Exception:
            pass

    def send_copy(self):
        """模拟 Ctrl+C（复制选中内容到剪贴板）。"""
        try:
            keyboard.send("ctrl+c")
        except Exception:
            pass

    def send_paste(self):
        """模拟 Ctrl+V（粘贴剪贴板内容）。"""
        try:
            keyboard.send("ctrl+v")
        except Exception:
            pass
