# Picture Book Dataset

从 [StoryWeaver](https://storyweaver.org.in) 下载绘本 PDF，拆解为 JPG，并按文字占比筛选出大插图页的数据集构建工具。

## 项目结构

```
├── 00Log in/
│   ├── login_storyweaver.py     # 登录测试脚本，验证 curl_cffi 能否绕过 Cloudflare
│   └── sign up.py               # Selenium 注册脚本（需手动过 reCAPTCHA）
│
├── 01Reverse crawler/
│   ├── 00添加链接.py             # 往 stories.json 添加待下载链接
│   ├── 00添加邮箱.py             # 往 outlook.json 添加邮箱账号
│   ├── 01逆向下载基础版.py        # 主下载脚本，自动登录 → 下载 ZIP
│   ├── outlook.json             # 邮箱列表，含 failed_at 时间戳
│   └── stories.json             # 任务记录，含 status 和 failed_at
│
├── 02Processing/
│   └── 拆包.py                   # 解压 ZIP → 渲染 JPG（≥720p、删首尾页）→ 写 metadata.jsonl
│
└── 03Finishing process/
    └── 01图片分析.py             # 文字块占比筛选 → 保留大插图页 → 写 metadata.jsonl
```

## 环境要求

```bash
pip install curl_cffi pymupdf opencv-python
# 注册脚本（00Log in/sign up.py）另需
pip install selenium
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

### 4. 拆包渲染（02Processing/拆包.py）

运行 `02Processing/拆包.py`：

- 从 ZIP 中直接读取 PDF（不落盘，按 MD5 去重）
- 逐页渲染 JPG，分辨率不低于 720p（1280×720），页面较小时自动提高缩放倍数
- 删除首页 1 页 + 末尾 4 页，保留页沿用原 PDF 页码命名，不重新编号
- 每本绘本输出到 `02Processing/output_pdf/{slug}_{日期}_{保留页数}/`
- 每本处理完立即追加一行到 `metadata.jsonl`，重跑时已记录的绘本自动跳过

### 5. 图片筛选（03Finishing process/01图片分析.py）

运行 `03Finishing process/01图片分析.py`：

- 扫描 `02Processing/output_pdf/` 下每个绘本文件夹
- 逐张计算文字块占比：二值化 → 按字符尺寸过滤掉插画黑色大轮廓 → 膨胀合并文字为文本块 → 包围盒面积 / 整图面积
- 文字块占比 < 50% 保留（大插图页），≥ 50% 过滤（大段文字页）
- 保留图复制到 `03Finishing process/output_jpg_crop/{slug}_{日期}_{保留张数}/`
- 每本处理完立即追加一行到 `metadata.jsonl`，重跑时已处理的绘本自动跳过

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

### metadata.jsonl（02Processing / 03Finishing process 生成）

每本绘本一行：

```json
{"data": [{"type": "image", "image_url": "529-masala-chai_20260814_15/f45e..._02.jpg"}, ...]}
```

- 文件夹名 `{slug}_{日期}_{保留张数}`，末尾数字即该文件夹实际图片数
- 02Processing 的 `image_url` 相对 `02Processing/output_pdf/`，03Finishing process 的相对 `03Finishing process/output_jpg_crop/`

## 技术要点

- 使用 `curl_cffi` 模拟 Chrome 110 TLS 指纹，绕过 Cloudflare 防护
- 下载失败自动切换邮箱轮换，避免单账号被限流
- 下载间隔 10 秒，避免请求过快
- reCAPTCHA 令牌有效期约 2 分钟且一次性，注册改用 Selenium 手动过验证码
- 文字占比用连通域包围盒面积而非黑色像素占比，避免单字笔画误判；过滤插画大轮廓避免图画被当成文字块
