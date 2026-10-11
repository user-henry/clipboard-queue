r"""
Clipboard Queue 数据层烟雾测试

覆盖：设置持久化、密码哈希与校验、队列 FIFO 语义、
标题/分类/标签、分类锁定与密码保护、限额与去重、
搜索、旧格式迁移、重启后数据恢复、导出/导入。

运行： python tests\smoke_test.py
"""

import json
import os
import shutil
import sys
import tempfile

# 必须在导入项目模块前隔离数据目录
TEMP_APPDATA = tempfile.mkdtemp(prefix="clipqueue_smoke_")
os.environ["APPDATA"] = TEMP_APPDATA

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, os.path.abspath(SRC))

from app_settings import AppSettings  # noqa: E402
from queue_manager import QueueManager  # noqa: E402
from security import Security  # noqa: E402

PASS = []
FAIL = []


def check(name, condition, detail=""):
    if condition:
        PASS.append(name)
        print(f"  [PASS] {name}")
    else:
        FAIL.append(f"{name} — {detail}")
        print(f"  [FAIL] {name} — {detail}")


def main():
    print("=" * 62)
    print("Clipboard Queue 数据层烟雾测试")
    print(f"临时数据目录: {TEMP_APPDATA}")
    print("=" * 62)

    # ── 1. 设置 ──
    print("\n[1] 设置读写与持久化")
    settings = AppSettings()
    check("默认值为队首弹出", settings.get("queue.pop_direction") == "head")
    check("默认通知开启", settings.get("general.show_notifications") is True)
    settings.set("queue.max_items", 42)
    check("点号路径写入生效", settings.get("queue.max_items") == 42)
    check("设置文件位于临时目录", settings._path.startswith(TEMP_APPDATA), settings._path)

    settings2 = AppSettings()
    check("重启后设置恢复", settings2.get("queue.max_items") == 42)

    settings2.update({"queue": {"dedupe": True}})
    check("深合并保留同组其他键",
          settings2.get("queue.dedupe") is True and settings2.get("queue.max_items") == 42)

    # 历史版本把设置写成了顶层点号键，重新载入时必须迁移进嵌套结构
    legacy_settings_path = os.path.join(TEMP_APPDATA, "legacy_settings.json")
    with open(legacy_settings_path, "w", encoding="utf-8") as f:
        json.dump({"queue.max_items": 99, "hotkeys.copy": "ctrl+alt+j"}, f)
    migrated = AppSettings(path=legacy_settings_path)
    check("顶层点号键迁移为嵌套值",
          migrated.get("queue.max_items") == 99
          and migrated.get("hotkeys.copy") == "ctrl+alt+j")
    check("迁移后不再残留点号顶层键",
          "queue.max_items" not in migrated.as_dict())
    migrated_reopened = AppSettings(path=legacy_settings_path)
    check("迁移结果已落盘", migrated_reopened.get("queue.max_items") == 99)

    # ── 2. 密码 ──
    print("\n[2] 访问密码（PBKDF2）")
    security = Security(settings2)
    check("初始未设置密码", security.has_password() is False)
    check("过短密码被拒绝", security.set_password("12") is False)
    check("设置密码成功", security.set_password("abcd1234") is True)
    check("正确密码校验通过", security.verify_password("abcd1234") is True)
    check("错误密码校验失败", security.verify_password("abcd12345") is False)

    with open(settings2._path, "r", encoding="utf-8") as f:
        raw_text = f.read()
    check("设置文件不含明文密码", "abcd1234" not in raw_text)
    check("设置文件含哈希记录", '"pbkdf2_sha256"' in raw_text)

    # ── 3. 队列基础语义 ──
    print("\n[3] 队列基础语义")
    queue = QueueManager(settings=settings2)
    settings2.set("queue.dedupe", False)
    settings2.set("queue.max_items", 0)

    first = queue.enqueue("第一条内容", title="标题一", category="工作", tags=["a"])
    queue.enqueue("第二条内容")
    check("入队返回完整条目",
          first and first.get("id") and first.get("title") == "标题一"
          and first.get("category") == "工作" and first.get("tags") == ["a"])
    check("无标题时自动派生标题", queue.get_all()[1].get("title") == "第二条内容")
    check("队列长度为 2", queue.count() == 2)

    head = queue.dequeue()
    check("队首先进先出", head.get("content") == "第一条内容")
    check("出队后长度为 1", queue.count() == 1)

    item = queue.get_all()[0]
    queue.update_item(item["id"], title="改名后", category="代码")
    got = queue.get_item(item["id"])
    check("条目可更新标题与分类",
          got.get("title") == "改名后" and got.get("category") == "代码")

    queue.enqueue("准备置顶")
    last_id = queue.get_all()[-1]["id"]
    queue.move_to_front(last_id)
    check("置顶生效", queue.get_all()[0]["id"] == last_id)

    removed = queue.remove_item(got["id"])
    check("按 id 删除条目", removed is True and queue.get_item(got["id"]) is None)

    idx_item = queue.get_all()[0]
    queue.remove_at(0)
    check("按下标删除条目", queue.get_item(idx_item["id"]) is None)

    # ── 4. 分类与密码保护 ──
    print("\n[4] 分类与密码保护")
    names = [c["name"] for c in queue.get_categories()]
    check("默认分类已创建", "未分类" in names and "密码" in names, str(names))
    check("「密码」分类默认锁定", queue.category_locked("密码") is True)
    check("普通分类默认不锁定", queue.category_locked("工作") is False)

    queue.add_category("项目", color="#FF00AA")
    check("新增分类可指定颜色", queue.get_category("项目")["color"] == "#FF00AA")
    queue.set_category_locked("项目", True)
    check("可单独锁定分类", queue.category_locked("项目") is True)
    queue.rename_category("项目", "项目A")
    check("分类重命名同时更新条目归属",
          queue.category_locked("项目A") is True and queue.get_category("项目") is None)

    secret_item = queue.enqueue("我的密码是 123456", category="密码")
    normal_item = queue.enqueue("公开内容", category="工作")
    marked_item = queue.enqueue("单条加密内容", category="工作", secret=True)
    check("锁定分类中的条目受保护", queue.is_protected(secret_item) is True)
    check("普通条目不受保护", queue.is_protected(normal_item) is False)
    check("单条 secret 标记受保护", queue.is_protected(marked_item) is True)
    check("条目可改归属到锁定分类",
          queue.update_item(normal_item["id"], category="密码")
          and queue.is_protected(queue.get_item(normal_item["id"])) is True)

    counts = queue.counts_by_category()
    check("分类计数包含空分类", "工作" in counts and counts["密码"] >= 2, str(counts))
    queue.clear_category("密码")
    check("清空分类只删除该分类条目",
          queue.counts_by_category().get("密码", 0) == 0)

    # ── 5. 搜索 ──
    print("\n[5] 搜索")
    queue.clear()
    queue.enqueue("print('hello world')", title="Python 片段", category="代码", tags=["py"])
    queue.enqueue("https://www.luogu.com.cn", title="洛谷", category="网址")
    check("按标题搜索", len(queue.search("洛谷")) == 1)
    check("按内容搜索", len(queue.search("hello")) == 1)
    check("按分类搜索", len(queue.search("代码")) == 1)
    check("按标签搜索", len(queue.search("py")) == 1)
    check("无匹配返回空", queue.search("不存在的关键词") == [])

    # ── 6. 设置联动（限额 / 去重 / 弹出方向）──
    print("\n[6] 设置联动")
    queue.clear()
    settings2.set("queue.max_items", 3)
    for i in range(5):
        queue.enqueue(f"第{i}条")
    check("超出上限自动裁剪旧条目",
          queue.count() == 3 and queue.get_all()[0]["content"] == "第2条", str(queue.count()))

    settings2.set("queue.max_items", 0)
    settings2.set("queue.dedupe", True)
    queue.clear()
    queue.enqueue("重复内容")
    dup = queue.enqueue("重复内容")
    check("开启去重后重复内容被跳过", dup is None and queue.count() == 1)
    settings2.set("queue.dedupe", False)

    queue.clear()
    queue.enqueue("A")
    queue.enqueue("B")
    settings2.set("queue.pop_direction", "tail")
    check("弹出方向可切换为队尾", queue.dequeue()["content"] == "B")
    settings2.set("queue.pop_direction", "head")

    # 关闭「本地保存」后只留在内存：不写盘、重启为空；重新开启后旧数据仍在
    queue.clear()
    queue.enqueue("关闭保存前的内容")
    QueueManager(settings=settings2)          # 确保已落盘
    settings2.set("queue.persist", False)
    memory_only = QueueManager(settings=settings2)
    memory_only.enqueue("仅内存内容")
    check("关闭保存后不读取历史记录", memory_only.count() == 1)
    check("关闭保存后重启为空", QueueManager(settings=settings2).count() == 0)
    settings2.set("queue.persist", True)
    check("重新开启保存后旧数据仍在", QueueManager(settings=settings2).count() >= 1)

    # ── 7. 持久化与迁移 ──
    print("\n[7] 持久化与旧格式迁移")
    queue.clear()
    queue.enqueue("重启前的内容", title="持久化测试", category="工作")
    queue.add_category("新分类", color="#123456")
    reopened = QueueManager(settings=settings2)
    check("重启后条目恢复", reopened.count() == 1
          and reopened.get_all()[0]["title"] == "持久化测试")
    check("重启后分类恢复", reopened.get_category("新分类") is not None)
    check("重启后锁定状态恢复", reopened.category_locked("密码") is True)

    legacy_path = os.path.join(TEMP_APPDATA, "legacy_queue.json")
    with open(legacy_path, "w", encoding="utf-8") as f:
        json.dump([
            {"type": "text", "content": "旧格式内容", "preview": "旧格式内容", "time": "10:00:00"},
        ], f, ensure_ascii=False)
    legacy = QueueManager(save_path=legacy_path, settings=settings2)
    check("旧格式（纯数组）可加载", legacy.count() == 1)
    legacy_item = legacy.get_all()[0]
    check("旧条目自动补齐 id/标题/分类",
          bool(legacy_item.get("id")) and legacy_item.get("title") == "旧格式内容"
          and legacy_item.get("category") == "未分类", str(legacy_item))
    check("旧文件补写默认分类",
          any(c["name"] == "密码" for c in legacy.get_categories()))

    broken_path = os.path.join(TEMP_APPDATA, "broken_queue.json")
    with open(broken_path, "w", encoding="utf-8") as f:
        f.write("{ 这不是合法 JSON")
    broken = QueueManager(save_path=broken_path, settings=settings2)
    check("损坏数据文件不崩溃且回退为空", broken.count() == 0 and len(broken.get_categories()) > 0)

    # ── 8. 导出 / 导入 ──
    print("\n[8] 导出与导入")
    export_path = os.path.join(TEMP_APPDATA, "backup.json")
    check("导出成功", queue.export_json(export_path) is True and os.path.exists(export_path))
    queue.clear()
    check("清空后为空", queue.count() == 0)
    n = queue.import_json(export_path)
    check("导入恢复条目", n >= 1 and queue.count() == n, f"n={n}")
    check("导入后标题一致", queue.get_all()[0]["title"] == "持久化测试")

    # ── 汇总 ──
    print("\n" + "=" * 62)
    print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    for item in FAIL:
        print(f"  [X] {item}")
    print("=" * 62)

    shutil.rmtree(TEMP_APPDATA, ignore_errors=True)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
