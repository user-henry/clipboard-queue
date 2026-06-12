# 📋 Clipboard Queue

> 让复制粘贴变成「先进先出队列」的 Windows 小工具。复制多个内容，依次粘贴，不覆盖、不丢失。

---

## 🎯 核心逻辑

| 普通剪贴板 | Clipboard Queue |
|-----------|----------------|
| 每次覆盖上一次 | 先进先出队列 |
| 只能粘贴最后一次复制 | 按顺序依次粘贴 |
| 复制新内容丢失旧的 | 全部保留，不丢失 |

---

## ⌨️ 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl + Shift + C` | 将当前剪贴板内容加入队列尾部 |
| `Ctrl + Shift + V` | 从队列头部取出内容并粘贴 |
| `Ctrl + Shift + Q` | 清空整个队列 |
| 点击托盘图标 | 查看 / 管理队列列表 |

---

## 📦 安装与运行

### 方式一：直接运行（推荐）

1. 下载 `release/ClipboardQueue.exe`
2. 双击运行，图标出现在系统托盘
3. 开始使用！

### 方式二：源码运行

```bash
# 安装依赖
pip install -r requirements.txt

# 运行
python src/main.py
```

### 方式三：自行打包

```bash
# 执行构建脚本
build\build.bat
```

---

## 🖥️ 系统要求

- Windows 10 / 11（64位）
- 如从源码运行：Python 3.8+

---

## 📁 项目结构

```
ClipboardQueue/
├── README.md
├── LICENSE              (MIT)
├── requirements.txt
├── src/
│   ├── main.py          # 入口 + 托盘图标 + 队列窗口
│   ├── queue_manager.py # FIFO 队列逻辑 + 持久化
│   ├── clipboard_helper.py # 剪贴板读写 + 备份恢复
│   ├── hotkey_manager.py   # 全局热键注册
│   └── notify_helper.py    # Windows Toast 通知
├── build/
│   └── build.bat        # 一键编译脚本
└── release/
    └── ClipboardQueue.exe
```

---

## ✨ 特性

- ✅ **系统托盘图标**：显示队列长度角标数字
- ✅ **队列持久化**：退出后队列数据保存，重启自动恢复
- ✅ **不污染剪贴板**：粘贴后自动恢复用户原本的剪贴板内容
- ✅ **队列管理窗口**：可视化查看、删除、选中粘贴
- ✅ **自动粘贴**：`Ctrl+Shift+V` 取出内容后自动模拟 `Ctrl+V`
- ✅ **Windows 原生通知**：粘贴/入队时弹出 Toast 提示
- ✅ **单实例运行**：防止重复启动
- ✅ **轻量级**：Python 实现，40KB 源码

---

## 🔧 技术栈

| 模块 | 方案 |
|------|------|
| 语言 | Python 3.8+ |
| 全局热键 | `keyboard` 库（系统级钩子） |
| 剪贴板 | `pyperclip` |
| 托盘图标 | `pystray` + `Pillow` |
| 通知 | 原生 Windows Toast（PowerShell） |
| GUI | `tkinter` |
| 打包 | `PyInstaller` → 单文件 EXE |
