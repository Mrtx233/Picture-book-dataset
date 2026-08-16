"""
往 outlook.jsonl 中添加邮箱（控制台输入）
支持两种输入格式：
  1. 四字段制表符分隔：序号<TAB>邮箱<TAB>状态<TAB>注册链接
  2. 纯邮箱
自动过滤已存在的邮箱，首次运行自动从旧 outlook.json 迁移
"""
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EMAILS_JSONL = os.path.join(BASE_DIR, "outlook.jsonl")
OLD_EMAILS_JSON = os.path.join(BASE_DIR, "outlook.json")


def load_emails():
    """返回 (邮箱列表, 是否从旧 outlook.json 迁移)"""
    emails = []
    if os.path.isfile(EMAILS_JSONL):
        with open(EMAILS_JSONL, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    emails.append(json.loads(line))
        return emails, False

    if os.path.isfile(OLD_EMAILS_JSON):
        with open(OLD_EMAILS_JSON, "r", encoding="utf-8") as f:
            raw = json.load(f)
        for item in raw:
            if isinstance(item, str):
                emails.append({"email": item, "failed_at": "1970-01-01 00:00:00"})
            else:
                emails.append(item)
        return emails, True

    return emails, False


def parse_line(line):
    """解析一行输入，返回 (email, status, url) 或 None"""
    parts = line.split()
    if len(parts) >= 4:
        return parts[1], parts[2], parts[3]
    if len(parts) == 3 and "@" in parts[0]:
        return parts[0], parts[1], parts[2]
    if len(parts) == 1 and "@" in parts[0]:
        return parts[0], "未注册", ""
    return None


def save_emails(emails):
    with open(EMAILS_JSONL, "w", encoding="utf-8") as f:
        for e in emails:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def main():
    emails, migrated = load_emails()
    existing = {e["email"] for e in emails}

    print("请输入要添加的邮箱（格式: 序号<TAB>邮箱<TAB>状态<TAB>链接，或纯邮箱），每行一个，输入空行结束：")
    lines = []
    while True:
        try:
            line = input().strip()
        except EOFError:
            break
        if not line:
            break
        lines.append(line)

    if not lines:
        print("没有输入任何邮箱。")
        return

    to_add = []
    skipped = 0
    invalid = 0
    for line in lines:
        parsed = parse_line(line)
        if parsed is None:
            invalid += 1
            print(f"  ! 无法解析，跳过: {line}")
            continue
        email, status, url = parsed
        if email in existing:
            skipped += 1
        elif email not in [e["email"] for e in to_add]:
            to_add.append({
                "email": email,
                "status": status,
                "url": url,
                "failed_at": "1970-01-01 00:00:00",
            })

    if not to_add:
        print("没有新的邮箱需要添加。")
        if skipped:
            print(f"  {skipped} 个邮箱已存在，跳过")
        if invalid:
            print(f"  {invalid} 行无法解析")
        return

    emails.extend(to_add)
    save_emails(emails)
    if migrated:
        os.rename(OLD_EMAILS_JSON, OLD_EMAILS_JSON + ".bak")
        print("已将旧 outlook.json 迁移为 outlook.jsonl（原文件备份为 outlook.json.bak）")

    print(f"\n已添加 {len(to_add)} 个新邮箱:")
    for e in to_add:
        print(f"  + {e['email']}  {e['url']}")
    if skipped:
        print(f"跳过 {skipped} 个已存在的邮箱")
    if invalid:
        print(f"{invalid} 行无法解析")


if __name__ == "__main__":
    main()
