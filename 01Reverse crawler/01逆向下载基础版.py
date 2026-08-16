import json
from curl_cffi import requests
import os
import re
import time
from datetime import datetime

# ============================================================
# 下载文件保存的目录
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
# 任务记录 JSON，格式：{链接: {"status": "pending"|"success"|"failed", "failed_at": "..."}}
TASKS_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stories.json")
# 登录账号
PASSWORD = "12345678"
# [1] 检查用户状态固定使用的邮箱（不参与登录轮换）
STATUS_CHECK_EMAIL = "mrtx0505@outlook.com"
# 邮箱列表 JSONL 文件，每行：{"email": "...", "status": "...", "url": "...", "failed_at": "..."}
EMAILS_JSONL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outlook.jsonl")
# ============================================================

os.makedirs(OUTPUT_DIR, exist_ok=True)

# 加载邮箱列表
if os.path.isfile(EMAILS_JSONL):
    email_list = []
    with open(EMAILS_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                email_list.append(json.loads(line))
else:
    print("outlook.jsonl 不存在，请先运行 00添加邮箱.py 生成邮箱列表文件。")
    exit()

today_str = datetime.now().strftime("%Y-%m-%d")


def pick_available_email():
    """返回第一个 failed_at 不是今天的邮箱，没有则返回 None"""
    for i, e in enumerate(email_list):
        failed = e.get("failed_at", "")
        if not failed.startswith(today_str):
            return i, e["email"]
    return None, None


email_index, EMAIL = pick_available_email()
if EMAIL is None:
    print("所有邮箱今天都已失败，请明天再试或添加新邮箱。")
    exit()

print(f"当前使用邮箱 [{email_index + 1}/{len(email_list)}]: {EMAIL}")

# 加载任务记录
if os.path.isfile(TASKS_JSON):
    with open(TASKS_JSON, "r", encoding="utf-8") as f:
        tasks = json.load(f)
else:
    print("stories.json 不存在，请先用 添加链接.py 添加链接。")
    exit()

# 获取待下载的链接（pending + failed 都重新下载）
pending_urls = [url for url, v in tasks.items() if v["status"] in ("pending", "failed")]
success_urls = [url for url, v in tasks.items() if v["status"] == "success"]

if success_urls:
    print(f"已跳过 {len(success_urls)} 个下载成功的链接")
if not pending_urls:
    print("所有链接均已下载成功，无需重复下载。")
    exit()

print(f"待下载: {len(pending_urls)} 个链接")

headers = {
    "accept": "*/*",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "cache-control": "no-cache",
    "origin": "https://storyweaver.org.in",
    "pragma": "no-cache",
    "referer": "https://storyweaver.org.in/en",
    "sec-ch-ua": '"Not=A?Brand";v="99", "Google Chrome";v="151", "Chromium";v="151"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
}


def do_login(session, email):
    """用指定邮箱登录，返回 True/False"""
    print(f"[0] 访问主站，获取 cookie...")
    resp = session.get("https://storyweaver.org.in/en", headers=headers)
    print(f"状态码: {resp.status_code}")

    print("[1] 检查用户状态...")
    resp = session.get(
        "https://storyweaver.org.in/node/api/v1/user/status",
        params={"email": STATUS_CHECK_EMAIL},
        headers=headers,
    )
    print(f"状态码: {resp.status_code}  |  响应: {resp.text}")

    print("[2] 发送登录请求...")
    data = {
        "user[email]": email,
        "user[password]": PASSWORD,
    }
    resp = session.post(
        "https://storyweaver.org.in/node/api/v1/users/sign_in",
        data=data,
        headers=headers,
    )
    print(f"状态码: {resp.status_code}  |  响应: {resp.text}")
    return True


def mark_email_failed():
    """记录当前邮箱的失败时间戳到 outlook.jsonl"""
    email_list[email_index]["failed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(EMAILS_JSONL, "w", encoding="utf-8") as f:
        for e in email_list:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"  已记录邮箱 {EMAIL} 的失败时间")


def switch_to_next_email():
    """切换到下一个今天未失败的邮箱，返回 (email, index) 或 (None, -1)"""
    global email_index, EMAIL
    idx, email = pick_available_email()
    if email is None:
        return None, -1
    email_index = idx
    EMAIL = email
    print(f"\n>>> 切换到邮箱 [{email_index + 1}/{len(email_list)}]: {EMAIL}")
    return EMAIL, email_index


# 创建会话，模拟 Chrome 110 TLS 指纹
session = requests.Session(impersonate="chrome110")

# ========== 自动登录 ==========
do_login(session, EMAIL)

# ========== 开始下载 ==========
DOWNLOAD_URL = "https://storyweaver.org.in/node/api/v1/download-story"

total = len(pending_urls)
success_count = 0

for index, story_url in enumerate(pending_urls, start=1):
    m = re.search(r"/stories/(\d+)(?:-([^/?#]+))?", story_url)
    if not m:
        print(f"[{index}/{total}] 无法从链接解析故事 ID，跳过: {story_url}")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tasks[story_url] = {"status": "failed", "failed_at": now_str}
        with open(TASKS_JSON, "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
        print("解析失败，停止下载。")
        exit()

    story_id = m.group(1)
    story_slug = f"{story_id}-{m.group(2)}" if m.group(2) else story_id

    print(f"[{index}/{total}] 正在下载: {story_slug}")

    try:
        # 第一步：换取内部 uid
        api_url = f"https://storyweaver.org.in/node/api/v1/stories/{story_id}/translations_and_videos"
        response = session.get(api_url, headers={"referer": story_url})
        data = response.json()
        if "uid" not in data.get("data", {}):
            raise RuntimeError(
                f"没有拿到 uid，可能是 cookie 失效或该故事不允许下载。"
                f"状态码: {response.status_code}，响应: {response.text[:300]}"
            )
        story_uid = data["data"]["uid"]

        # 第二步：下载 ZIP
        params = {
            "id": story_uid,
            "format": "pdf",
            "high_resolution": "false",
            "is_mobile": "false",
            "attribution_only": "false",
        }
        response1 = session.get(
            DOWNLOAD_URL, params=params, headers={"referer": story_url}, stream=True
        )
        if response1.status_code != 200:
            raise RuntimeError(
                f"下载失败，状态码: {response1.status_code}，响应: {response1.text[:300]}"
            )

        output_file = os.path.join(OUTPUT_DIR, f"{story_slug}.zip")
        with open(output_file, "wb") as f:
            for chunk in response1.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        print(f"[{index}/{total}] 完成: {output_file}")
        success_count += 1
        tasks[story_url] = {"status": "success"}
        with open(TASKS_JSON, "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"[{index}/{total}] 失败: {story_slug} -> {e}")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tasks[story_url] = {"status": "failed", "failed_at": now_str}
        with open(TASKS_JSON, "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)

        # 标记当前邮箱失败
        mark_email_failed()

        # 尝试切换到下一个邮箱，重新登录后重试本条
        next_email, next_idx = switch_to_next_email()
        if next_email is None:
            print("所有邮箱已用完，停止下载。")
            exit()

        # 重建会话，用新邮箱登录
        session = requests.Session(impersonate="chrome110")
        do_login(session, next_email)

        # 重试同一条链接
        print(f"[{index}/{total}] 重试下载: {story_slug}")
        try:
            api_url = f"https://storyweaver.org.in/node/api/v1/stories/{story_id}/translations_and_videos"
            response = session.get(api_url, headers={"referer": story_url})
            data = response.json()
            if "uid" not in data.get("data", {}):
                raise RuntimeError(
                    f"没有拿到 uid，可能是 cookie 失效或该故事不允许下载。"
                    f"状态码: {response.status_code}，响应: {response.text[:300]}"
                )
            story_uid = data["data"]["uid"]

            params = {
                "id": story_uid,
                "format": "pdf",
                "high_resolution": "false",
                "is_mobile": "false",
                "attribution_only": "false",
            }
            response1 = session.get(
                DOWNLOAD_URL, params=params, headers={"referer": story_url}, stream=True
            )
            if response1.status_code != 200:
                raise RuntimeError(
                    f"下载失败，状态码: {response1.status_code}，响应: {response1.text[:300]}"
                )

            output_file = os.path.join(OUTPUT_DIR, f"{story_slug}.zip")
            with open(output_file, "wb") as f:
                for chunk in response1.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            print(f"[{index}/{total}] 重试完成: {output_file}")
            success_count += 1
            tasks[story_url] = {"status": "success"}
            with open(TASKS_JSON, "w", encoding="utf-8") as f:
                json.dump(tasks, f, ensure_ascii=False, indent=2)

        except Exception as e2:
            print(f"[{index}/{total}] 重试也失败: {story_slug} -> {e2}")
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            tasks[story_url] = {"status": "failed", "failed_at": now_str}
            with open(TASKS_JSON, "w", encoding="utf-8") as f:
                json.dump(tasks, f, ensure_ascii=False, indent=2)
            mark_email_failed()
            print("换邮箱后仍然失败，停止后续下载。")
            exit()

    # 最后一本不等待
    if index < total:
        print(f"等待 10 秒...")
        time.sleep(10)

print(f"\n全部结束：成功 {success_count}/{total}")