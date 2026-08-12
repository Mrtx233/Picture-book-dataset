"""
使用 curl_cffi 登录 StoryWeaver
curl_cffi 模拟 Chrome TLS 指纹，绕过 Cloudflare
"""
import time
from curl_cffi import requests

# 请求头，模拟真实浏览器
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

# ========== 第一步：访问主站，获取 cookie ==========
print("[0] 访问主站，获取 cookie...")
resp = session.get("https://storyweaver.org.in/en", headers=headers)
print(f"状态码: {resp.status_code}")
print(f"页面标题: {resp.text[:200]}...")

# ========== 第二步：检查用户是否存在 ==========
print("\n[1] 检查用户状态...")
status_url = "https://storyweaver.org.in/node/api/v1/user/status"
resp = session.get(status_url, params={"email": "mrtx0505@outlook.com"}, headers=headers)
print(f"状态码: {resp.status_code}")
print(f"响应: {resp.text}")

# ========== 第三步：发送登录请求 ==========
print("\n[2] 发送登录请求...")
login_url = "https://storyweaver.org.in/node/api/v1/users/sign_in"

data = {
    "user[email]": "sDOUWr2ngs@outlook.com",
    "user[password]": "12345678",
}

resp = session.post(login_url, data=data, headers=headers)
print(f"状态码: {resp.status_code}")
print(f"响应: {resp.text}")

# ========== 打印 cookie ==========
print("\n[Cookie]")
cookies = dict(session.cookies)
for name, value in cookies.items():
    print(f"  {name}: {value}")