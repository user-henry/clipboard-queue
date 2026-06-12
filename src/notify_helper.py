"""
Clipboard Queue - 通知提示辅助
使用 Windows 原生 Toast 通知
"""

import subprocess
import sys
import os


def _show_ps_toast(title, message):
    """
    通过 PowerShell 调用 Windows Toast 通知
    这是最可靠的 Windows 原生通知方式，无需额外依赖
    """
    ps_script = f'''
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType = WindowsRuntime] | Out-Null

$template = @"
<toast>
    <visual>
        <binding template="ToastText02">
            <text id="1">{title}</text>
            <text id="2">{message}</text>
        </binding>
    </visual>
</toast>
"@

$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($template)
$toast = New-Object Windows.UI.Notifications.ToastNotification $xml
$notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("ClipboardQueue")
$notifier.Show($toast)
'''
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            timeout=5,
        )
    except Exception:
        pass


class NotifyHelper:
    """桌面右下角通知提示"""

    def __init__(self, app_name="ClipboardQueue"):
        self.app_name = app_name

    def show(self, title, message=""):
        """显示通知（2秒后自动消失）"""
        if sys.platform == "win32":
            _show_ps_toast(title, message)
        else:
            # 非 Windows 平台不做通知
            pass

    def show_paste(self, preview):
        """粘贴成功通知"""
        display = preview if len(preview) <= 40 else preview[:37] + "..."
        self.show("已粘贴", display)

    def show_enqueue(self, count):
        """入队成功通知"""
        self.show(f"已加入队列", f"队列长度: {count}")

    def show_empty(self):
        """队列为空通知"""
        self.show("队列为空", "没有可粘贴的内容，使用普通剪贴板")

    def show_cleared(self):
        """队列清空通知"""
        self.show("队列已清空", "")
