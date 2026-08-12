from curl_cffi import requests
import os
import re
import time

# ============================================================
# 要下载哪些绘本，把链接放进下面这个列表即可
# ============================================================
STORY_URLS = [
    "https://storyweaver.org.in/en/stories/185349-waraabesootnii-maaliif-okkolan",
    "https://storyweaver.org.in/en/stories/130112-stories-before-bed",
    "https://storyweaver.org.in/en/stories/458913-mota-raja-dubla-kutta",
    "https://storyweaver.org.in/en/stories/130538-sneaky-fox",
]
# 下载文件保存的目录
OUTPUT_DIR = r"D:\A_PythonCode\Picture book dataset\01Reverse crawler\output"
# ============================================================

os.makedirs(OUTPUT_DIR, exist_ok=True)

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

# 创建会话，模拟 Chrome 110 TLS 指纹
session = requests.Session(impersonate="chrome110")

# ========== 自动登录，获取有效 cookie ==========
print("[0] 访问主站，获取 cookie...")
resp = session.get("https://storyweaver.org.in/en", headers=headers)
print(f"状态码: {resp.status_code}")

print("[1] 检查用户状态...")
resp = session.get(
    "https://storyweaver.org.in/node/api/v1/user/status",
    params={"email": "mrtx0505@outlook.com"},
    headers=headers,
)
print(f"状态码: {resp.status_code}  |  响应: {resp.text}")

print("[2] 发送登录请求...")
data = {
    "user[email]": "mrtx0505@outlook.com",
    "user[password]": "12345678",
}
resp = session.post(
    "https://storyweaver.org.in/node/api/v1/users/sign_in",
    data=data,
    headers=headers,
)
print(f"状态码: {resp.status_code}  |  响应: {resp.text}")

# 打印登录后的 cookie
print("[3] 登录后的 Cookie:")
cookies = dict(session.cookies)
for name, value in cookies.items():
    print(f"  {name}: {value}")

# ========== 开始下载 ==========
DOWNLOAD_URL = "https://storyweaver.org.in/node/api/v1/download-story"

total = len(STORY_URLS)
success = 0
failed = []

for index, story_url in enumerate(STORY_URLS, start=1):
    m = re.search(r"/stories/(\d+)(?:-([^/?#]+))?", story_url)
    if not m:
        print(f"[{index}/{total}] 无法从链接解析故事 ID，跳过: {story_url}")
        failed.append(story_url)
        continue
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
        success += 1
    except Exception as e:
        print(f"[{index}/{total}] 失败: {story_slug} -> {e}")
        failed.append(story_url)

    if index < total:
        print(f"等待 10 秒...")
        time.sleep(10)

print(f"\n全部结束：成功 {success}/{total}")
if failed:
    print("以下链接失败：")
    for url in failed:
        print(f"  - {url}")