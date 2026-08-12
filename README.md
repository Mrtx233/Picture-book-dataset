# Picture Book Dataset

从 [StoryWeaver](https://storyweaver.org.in) 下载绘本 PDF，拆解为 JPG 图片的数据集构建工具。

## 项目结构

```
├── 00Log in/
│   └── login_storyweaver.py     # 登录测试脚本，验证 curl_cffi 能否绕过 Cloudflare
│
├── 01Reverse crawler/
│   ├── 00添加链接.py             # 往 stories.json 添加待下载链接
│   ├── 00添加邮箱.py             # 往 outlook.json 添加邮箱账号
│   ├── 01逆向下载基础版.py        # 主下载脚本，自动登录 → 下载 ZIP
│   ├── outlook.json             # 邮箱列表，含 failed_at 时间戳
│   └── stories.json             # 任务记录，含 status 和 failed_at
│
└── 02Processing/
    └── 拆包.py                   # 解压 ZIP → 提取 PDF → 渲染 JPG → 输出元数据
```

## 环境要求

```bash
pip install curl_cffi pymupdf
```

## 使用流程

### 1. 添加绘本链接

运行 `01Reverse crawler/00添加链接.py`，逐行粘贴 StoryWeaver 故事链接，写入 `stories.json`。

```
https://storyweaver.org.in/en/stories/34911-the-case-of-the-missing-water
https://storyweaver.org.in/en/stories/39753-rabbit-becomes-a-chef
```

### 2. 添加邮箱账号

运行 `01Reverse crawler/00添加邮箱.py`，逐行输入邮箱地址，写入 `outlook.json`。

> 所有邮箱密码统一为 `12345678`，在 `01逆向下载基础版.py` 顶部 `PASSWORD` 变量修改。

### 3. 下载绘本

运行 `01Reverse crawler/01逆向下载基础版.py`：

- 自动从 `outlook.json` 选一个今天未失败的邮箱登录
- 遍历 `stories.json` 中 `pending` 和 `failed` 的链接
- 下载成功 → 标记 `success`
- 下载失败 → 记录时间戳，切换下一个邮箱重试同一链接
- 换邮箱后仍失败 → 停止退出

ZIP 文件保存到 `01Reverse crawler/output/`。

### 4. 拆解处理

运行 `02Processing/拆包.py`：

- 解压 ZIP，提取 PDF（按 MD5 去重存放）
- 逐页渲染为 JPG（自动删除首页 + 末尾 3 页）
- 输出元数据到 `02Processing/output.json`

## 数据格式

### outlook.json

```json
[
    {"email": "xxx@outlook.com", "failed_at": "1970-01-01 00:00:00"},
    {"email": "yyy@outlook.com", "failed_at": "2026-08-12 14:30:00"}
]
```

- `failed_at` 为 `1970-01-01 00:00:00` 表示从未失败
- 下载失败时写入当天时间戳，当天不会再被选中

### stories.json

```json
{
    "https://storyweaver.org.in/en/stories/34911-xxx": {"status": "success"},
    "https://storyweaver.org.in/en/stories/50898-xxx": {"status": "pending"},
    "https://storyweaver.org.in/en/stories/458913-xxx": {"status": "failed", "failed_at": "2026-08-12 22:30:00"}
}
```

### output.json（02Processing 生成）

```json
[
    {
        "story_id": 34911,
        "slug": "34911-the-case-of-the-missing-water",
        "pdf_file": "output_pdf/abc123/abc123.pdf",
        "source_zip": "34911-xxx.zip",
        "md5": "abc123...",
        "page_count": 12,
        "images": ["output_pdf/abc123/abc123_02.jpg", ...]
    }
]
```

## 技术要点

- 使用 `curl_cffi` 模拟 Chrome 110 TLS 指纹，绕过 Cloudflare 防护
- 下载失败自动切换邮箱轮换，避免单账号被限流
- 下载间隔 10 秒，避免请求过快