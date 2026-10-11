# 📋 Clipboard Queue v2

> 把复制粘贴变成「先进先出队列」的 Windows 工具，v2 升级为**科技感卡片界面**，
> 支持标题命名、分类管理、搜索、**密码保护**，所有记录默认本地保存，重启不丢。

## 核心逻辑

| 普通剪贴板 | Clipboard Queue |
|-----------|----------------|
| 每次覆盖上一次 | 先进先出队列，全部保留 |
| 只能粘贴最后一次复制 | 按顺序依次粘贴 |
| 复制新内容即丢失旧内容 | 退出后队列仍在，重启自动恢复 |

## v2 新增

| 能力 | 说明 |
|------|------|
| 卡片式界面 | 每条内容一张展示卡：标题、分类徽章、时间、字符数、正文预览、图片缩略图 |
| 命名与分类 | 卡片内直接「命名」「分类」，支持自定义分类与配色；分类可新增 / 重命名 / 删除 / 锁定 |
| 搜索与筛选 | 顶部搜索框（标题 / 内容 / 分类 / 标签）+ 分类筛选条 |
| 密码保护 | 锁定分类（默认已提供「密码」分类）或单条标记为受保护；PBKDF2-HMAC-SHA256 加盐哈希存储，解锁后缓存一段时间 |
| 敏感内容保护 | 受保护内容复制到剪贴板后可按设置自动清空；退出时可清空剪贴板 |
| 置顶与排序 | 一键把需要的条目置顶到队首 |
| 设置页 | 5 个分页：常规 / 队列 / 分类与密码 / 快捷键 / 存储，保存即持久化并即时生效 |
| 备份 | 导出 / 导入 JSON 备份 |
| 毛玻璃界面 | 原生 blur-behind 真实模糊背景，主窗口 / 设置页 / 解锁框统一质感；可在「设置 → 常规 → 界面与特效」调整模式与不透明度 |

## 快捷键（默认，可在「设置 → 快捷键」中修改）

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+Alt+C` | 复制选中内容并加入队列 |
| `Ctrl+Alt+V` | 从队列取出并粘贴 |
| `Ctrl+Alt+Q` | 清空队列 |
| `Ctrl+Alt+S` | 打开主窗口 |
| 托盘图标单击 | 查看 / 管理队列 |

## 数据与隐私

| 内容 | 位置 |
|------|------|
| 队列与分类 | `%APPDATA%\ClipboardQueue\queue_data.json` |
| 偏好与密码哈希 | `%APPDATA%\ClipboardQueue\settings.json` |

- 默认开启本地保存；可在 **设置 → 队列** 中限制队列上限，或在 **设置 → 存储** 中清空全部记录。
- 密码只保存 PBKDF2 哈希与随机盐，**绝不保存明文**，也不写入队列数据文件。

## 安装与运行

### 方式一：直接运行（推荐）

1. 下载 `release/ClipboardQueue.exe`
2. 双击运行，图标出现在系统托盘

### 方式二：源码运行

```bash
pip install -r requirements.txt
python src/main.py
```

### 方式三：自行打包

```bash
pip install pyinstaller
pyinstaller --clean --noconfirm ClipboardQueue.spec
```

## 测试

```bash
python tests\smoke_test.py       # 数据层：设置、密码、FIFO、分类锁定、搜索、限额、迁移、导入导出
python tests\gui_smoke_test.py   # 界面层：卡片窗口、掩码展示、筛选、删除确认、设置页、密码对话框
```

## 系统要求

- Windows 10 / 11（64 位）
- 源码运行需要 Python 3.8+

## 项目结构

```text
ClipboardQueue/
├── src/
│   ├── main.py            # 入口：托盘、热键、卡片式主窗口、解锁对话框
│   ├── queue_manager.py   # FIFO 队列 + 分类 / 标题 / 密码标记 + 持久化与迁移
│   ├── app_settings.py    # 偏好设置（JSON 原子写入）
│   ├── security.py        # PBKDF2 密码设置与校验
│   ├── settings_window.py # 设置页（5 个分页）+ 开机自启
│   ├── ui_theme.py        # 暗色科技风主题与组件
│   ├── clipboard_helper.py、hotkey_manager.py、notify_helper.py
├── tests/                 # 数据层与界面层冒烟测试
└── ClipboardQueue.spec    # PyInstaller 打包配置
```

## 许可

MIT License
