"""
往 stories.json 中添加未下载的链接（控制台输入）
自动过滤已存在、已成功、已失败的链接
"""
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TASKS_JSON = os.path.join(BASE_DIR, "stories.json")


def main():
    if os.path.isfile(TASKS_JSON):
        with open(TASKS_JSON, "r", encoding="utf-8") as f:
            tasks = json.load(f)
    else:
        tasks = {}

    print("请输入要添加的链接，每行一个，输入空行结束：")
    lines = []
    while True:
        line = input().strip()
        if not line:
            break
        lines.append(line)

    if not lines:
        print("没有输入任何链接。")
        return

    to_add = []
    skipped = 0
    for url in lines:
        if url in tasks:
            skipped += 1
        elif url not in to_add:
            to_add.append(url)

    if not to_add:
        print("没有新的链接需要添加。")
        if skipped:
            print(f"  {skipped} 个链接已存在，跳过")
        return

    for url in to_add:
        tasks[url] = {"status": "pending"}

    with open(TASKS_JSON, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)

    print(f"\n已添加 {len(to_add)} 个新链接:")
    for url in to_add:
        print(f"  + {url}")
    if skipped:
        print(f"跳过 {skipped} 个已存在的链接")


if __name__ == "__main__":
    main()