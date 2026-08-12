from curl_cffi import requests
import os
import re
import time

# ============================================================
# 要下载哪些绘本，把链接放进下面这个列表即可
# ============================================================
STORY_URLS = [
    "https://storyweaver.org.in/en/stories/13329-har-din-ek-kahani",
    "https://storyweaver.org.in/en/stories/43229-chunu-munu-it-s-freezing",
    "https://storyweaver.org.in/en/stories/39842-whale-in-the-sky",
    "https://storyweaver.org.in/en/stories/28887-creatures-of-old",
    "https://storyweaver.org.in/en/stories/54021-have-you-seen-sundari",
]
# 下载文件保存的目录
OUTPUT_DIR = r"D:\A_PythonCode\Picture book dataset\01Reverse crawler\output"
# ============================================================

os.makedirs(OUTPUT_DIR, exist_ok=True)

# cookie 会过期，失效后从浏览器重新复制整段贴到这里即可
cookies = {
    "_fbp": "b.2.1786437496104.359027494716172950",
    "_ga": "GA1.1.944163902.1786437496",
    "_session_id": "5fd2b5271761df4dc4e3aa8ba92e58db69ac3c55b6248db1e4a0a2b5bfc0ab74",
    "cf_clearance": "r_prASARrLFHaW3Vvlj6_n3rls0WnzjPSPX4BfEivco-1786513488-1.2.1.1-O5IwXDJIy99_WU60ICxWPGc3mY9UtWlKFmSxZfnK3sp2120T9OkIE35C5XEFhXmIOQtE5vOQmWSqM1ji.B57DMl4j.enkOuyw7UIQWwWyRWzyIDjR.urLWjgMTTNSssmRvdHnfidIbzpTIoP.UIv_CVUSWdTcloa.U8KVWoI2vLHyPqikwLN3q4LCugeKTTAXfSlPERVTpNbjRDXzxho7Ebz56KKAonm87JQToGMqRnZjPW.ghhzBE7V4JL_Mti.ROPyzu5zEB1cqwtvb17amoHlmB9HqkGZDrYbwp.uabZgDgNkhxHHN5U52T5fFXMgzMdLHqNjqHNQsPVOLLXOC2nxt8EmlphPJAm3nd0QBBA",
    "_ga_7SYFBHPQLQ": f"GS2.1.s1786517413$o5$g1$t{int(time.time())}$j42$l0$h0",
}

headers = {
    "accept": "*/*",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "cache-control": "no-cache",
    "locale": "en",
    "pragma": "no-cache",
    "priority": "u=1, i",
    "sec-ch-ua": '"Not=A?Brand";v="99", "Microsoft Edge";v="151", "Chromium";v="151"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0",
}

DOWNLOAD_URL = "https://storyweaver.org.in/node/api/v1/download-story"

session = requests.Session(impersonate="chrome124")
session.headers.update(headers)
session.cookies.update(cookies)

total = len(STORY_URLS)
success = 0
failed = []

for index, story_url in enumerate(STORY_URLS, start=1):
    # 从链接里解析出故事 ID 和 slug，例如 11986 / 11986-who-is-it
    m = re.search(r"/stories/(\d+)(?:-([^/?#]+))?", story_url)
    if not m:
        print(f"[{index}/{total}] 无法从链接解析故事 ID，跳过: {story_url}")
        failed.append(story_url)
        continue
    story_id = m.group(1)
    story_slug = f"{story_id}-{m.group(2)}" if m.group(2) else story_id

    print(f"[{index}/{total}] 正在下载: {story_slug}")

    try:
        # 第一步：换取内部 uid（referer 指向当前故事页）
        api_url = f"https://storyweaver.org.in/node/api/v1/stories/{story_id}/translations_and_videos"
        response = session.get(api_url, headers={"referer": story_url})
        data = response.json()
        if "uid" not in data.get("data", {}):
            raise RuntimeError(
                f"没有拿到 uid，可能是 cookie 失效或该故事不允许下载。"
                f"状态码: {response.status_code}，响应: {response.text[:300]}"
            )
        story_uid = data["data"]["uid"]

        # 第二步：下载 ZIP（内含 PDF + 署名文件）
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

    # 每本之间间隔 10 秒，最后一本不再等待
    if index < total:
        print(f"等待 10 秒...")
        time.sleep(10)

print(f"\n全部结束：成功 {success}/{total}")
if failed:
    print("以下链接失败：")
    for url in failed:
        print(f"  - {url}")
