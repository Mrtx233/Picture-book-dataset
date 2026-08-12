"""
往 outlook.json 中添加邮箱（控制台输入）
自动过滤已存在的邮箱
"""
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EMAILS_JSON = os.path.join(BASE_DIR, "outlook.json")


def main():
    if os.path.isfile(EMAILS_JSON):
        with open(EMAILS_JSON, "r", encoding="utf-8") as f:
            raw = json.load(f)
        # 兼容旧格式（纯字符串列表）和新格式（对象列表）
        emails = []
        for item in raw:
            if isinstance(item, str):
                emails.append({"email": item, "failed_at": "1970-01-01 00:00:00"})
            else:
                emails.append(item)
    else:
        emails = []

    existing = {e["email"] for e in emails}

    print("请输入要添加的邮箱，每行一个，输入空行结束：")
    lines = []
    while True:
        line = input().strip()
        if not line:
            break
        lines.append(line)

    if not lines:
        print("没有输入任何邮箱。")
        return

    to_add = []
    skipped = 0
    for email in lines:
        if email in existing:
            skipped += 1
        elif email not in [e["email"] for e in to_add]:
            to_add.append({"email": email, "failed_at": "1970-01-01 00:00:00"})

    if not to_add:
        print("没有新的邮箱需要添加。")
        if skipped:
            print(f"  {skipped} 个邮箱已存在，跳过")
        return

    emails.extend(to_add)

    with open(EMAILS_JSON, "w", encoding="utf-8") as f:
        json.dump(emails, f, ensure_ascii=False, indent=2)

    print(f"\n已添加 {len(to_add)} 个新邮箱:")
    for e in to_add:
        print(f"  + {e['email']}")
    if skipped:
        print(f"跳过 {skipped} 个已存在的邮箱")


if __name__ == "__main__":
    main()