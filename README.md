# Picture Book Dataset

从 [StoryWeaver](https://storyweaver.org.in) 下载绘本 PDF，拆解为 JPG，按文字占比筛出大插图页，再按语种（中文/英文）分拣，构建用于 AI 训练的数据集。

## 项目结构

```
├── 00Log in/
│   └── login_storyweaver.py     # 登录测试脚本，验证 curl_cffi 能否绕过 Cloudflare
│
├── 01Reverse crawler/
│   ├── 00添加链接.py             # 往 stories.json 添加待下载链接
│   ├── 00添加邮箱.py             # 往 outlook.json 添加邮箱账号
│   ├── 01逆向下载基础版.py        # 主下载脚本，自动登录 → 下载 ZIP
│   ├── output/                  # 下载的 ZIP（git 忽略，自动生成）
│   ├── outlook.json             # 邮箱列表，含 failed_at 时间戳
│   └── stories.json             # 任务记录，含 status 和 failed_at
│
├── 02Processing/
│   ├── 21拆包.py                 # 解压 ZIP → 渲染 JPG → 写 metadata.jsonl
│   ├── output_pdf/              # 渲染的 JPG 分册目录（git 忽略，自动生成）
│   └── metadata.jsonl           # 第一步拆包渲染的元数据
│
├── 03Finishing process/
│   ├── 31图片分析.py             # 文字块占比筛选 → 保留大插图页
│   ├── output_jpg_crop/         # 筛选后的大插图分册目录（git 忽略，自动生成）
│   └── metadata.jsonl           # 第二步筛选的元数据
│
└── 04Language identification/
    ├── 41语种识别.py             # OCR 判定中英文 → 按语种分文件夹
    ├── 中文/                    # 中文绘本图片（git 忽略，自动生成）
    ├── 英文/                    # 英文绘本图片（git 忽略，自动生成）
    └── metadata.jsonl           # 第三步语种分拣的元数据
```

## 环境要求

```bash
pip install curl_cffi pymupdf opencv-python
# 语种识别（04Language identification/41语种识别.py）另需
pip install rapidocr_onnxruntime
```

> 使用 Python 3.8+。`rapidocr_onnxruntime` 首次运行会下载内置模型，需联网。

## 路径约定（跨平台：Windows / macOS / Linux 零配置）

**所有脚本均不含任何绝对路径、盘符或正/反斜杠硬编码**，统一采用以下模式：

```python
BASE_DIR = os.path.dirname(os.path.abspath(__file__))   # 脚本自身所在目录
```

- 每个脚本以**自身所在目录**为基准，通过 `os.path.join` 拼接子路径；
- 跨目录读取上一层的结果时走**相对父级指针**（`os.path.join(BASE_DIR, "..", "...")`）；
- `os.path.join` 自动适配当前系统分隔符（Windows `\` / macOS·Linux `/`），目录名中的空格（如 `01Reverse crawler`）也无需转义。

因此：仓库克隆到任意路径、脚本从任意工作目录被调用，路径都正确解析；从 Windows 换到 macOS/Linux（或反之）无需改动任何代码。

各脚本的输入/输出目录关系：

| 脚本 | 输入 | 输出 |
|---|---|---|
| `01Reverse crawler/01逆向下载基础版.py` | — | `{BASE_DIR}/output/` |
| `02Processing/21拆包.py` | `../01Reverse crawler/output/` | `./output_pdf/` |
| `03Finishing process/31图片分析.py` | `../02Processing/output_pdf/` | `./output_jpg_crop/` |
| `04Language identification/41语种识别.py` | `../03Finishing process/` | `./中文/`、`./英文/` |

> 所有 `metadata.jsonl` 中只存**相对路径**（如 `529-masala-chai_20260814_15/xxx.jpg`、`中文/529-.../xxx.jpg`），不含绝对路径，保证数据集可整体搬移、跨机器共享。

## 使用流程

### 1. 添加绘本链接

运行 `01Reverse crawler/00添加链接.py`，逐行粘贴 StoryWeaver 故事链接，写入 `stories.json`。

```
https://storyweaver.org.in/en/stories/34911-the-case-of-the-missing-water
https://storyweaver.org.in/en/stories/39753-rabbit-becomes-a-chef
```

脚本会自动过滤已存在、已成功、已失败的链接。

### 2. 添加邮箱账号

运行 `01Reverse crawler/00添加邮箱.py`，逐行输入邮箱地址，写入 `outlook.json`。

> 所有邮箱密码统一为 `12345678`，在 `01逆向下载基础版.py` 顶部 `PASSWORD` 变量中修改。

### 3. 下载绘本

运行 `01Reverse crawler/01逆向下载基础版.py`：

- 自动从 `outlook.json` 选一个今天未失败的邮箱登录
- 用户状态检查固定使用 `STATUS_CHECK_EMAIL`（登录外的固定探针邮箱，不参与轮换）
- 遍历 `stories.json` 中 `pending` 和 `failed` 的链接
- 下载成功 → 标记 `success`
- 下载失败 → 记录时间戳，切换下一个邮箱重试同一链接
- 换邮箱后仍失败 → 停止退出

ZIP 保存到 `01Reverse crawler/output/`。

### 4. 拆包渲染（02Processing/21拆包.py）

运行 `02Processing/21拆包.py`：

- 从 ZIP 中直接读取 PDF（不落盘，按 MD5 去重）
- 逐页渲染 JPG，分辨率不低于 720p（1280×720），页面较小时自动提高缩放倍数
- 删除首页 1 页 + 末尾 4 页，保留页沿用原 PDF 页码命名，不重新编号
- 每本绘本输出到 `02Processing/output_pdf/{slug}_{日期}_{保留页数}/`
- 每本处理完立即追加一行到 `metadata.jsonl`，重跑时已记录的绘本自动跳过

### 5. 图片筛选（03Finishing process/31图片分析.py）

运行 `03Finishing process/31图片分析.py`：

- 扫描 `02Processing/output_pdf/` 下每个绘本文件夹
- 逐张计算文字块占比：二值化 → 按字符尺寸过滤掉插画黑色大轮廓 → 膨胀合并文字为文本块 → 包围盒面积 / 整图面积
- 文字块占比 < 50% 保留（大插图页），≥ 50% 过滤（大段文字页）
- 保留图复制到 `03Finishing process/output_jpg_crop/{slug}_{日期}_{保留张数}/`
- 每本处理完立即追加一行到 `metadata.jsonl`，重跑时已处理的绘本自动跳过

### 6. 语种识别（04Language identification/41语种识别.py）

运行 `04Language identification/41语种识别.py`：

- 读取 `03Finishing process/metadata.jsonl`，图片从 `output_jpg_crop/` 读取
- 每张图用 RapidOCR 提取文字，统计中文字符 vs 英文字符数量判定语种；纯插图页（无文字）默认归为英文
- 图片按语种复制到 `04Language identification/中文/{书目录}/` 或 `英文/{书目录}/`
- `image_url` 写入带语种前缀的相对路径（`中文/...`、`英文/...`）
- 每本处理完追加一行到 `metadata.jsonl`，重跑时已处理的绘本自动跳过

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
- `00添加邮箱.py` 兼容旧格式（纯字符串列表）和新格式（对象列表）

### stories.json

```json
{
    "https://storyweaver.org.in/en/stories/34911-xxx": {"status": "success"},
    "https://storyweaver.org.in/en/stories/50898-xxx": {"status": "pending"},
    "https://storyweaver.org.in/en/stories/458913-xxx": {"status": "failed", "failed_at": "2026-08-12 22:30:00"}
}
```

### metadata.jsonl（02 / 03 / 04 三个阶段分别生成）

每本绘本一行：

```json
{"data": [{"type": "image", "image_url": "529-masala-chai_20260814_15/f45e..._02.jpg"}, ...]}
```

- 文件夹名 `{slug}_{日期}_{保留张数}`，末尾数字即该文件夹实际图片数
- 02Processing 的 `image_url` 相对 `02Processing/output_pdf/`
- 03Finishing process 的相对 `03Finishing process/output_jpg_crop/`
- 04Language identification 的带语种前缀（`中文/`、`英文/`），相对该目录
- 三个阶段各自独立、各自断点续跑，互不干扰

## 技术要点

- 使用 `curl_cffi` 模拟 Chrome 110 TLS 指纹，绕过 Cloudflare 防护
- 下载失败自动切换邮箱轮换，避免单账号被限流；用户状态探针固定用一个邮箱，不影响轮换
- 下载间隔 10 秒，避免请求过快
- 文字占比用连通域包围盒面积而非黑色像素占比，避免单字笔画误判；过滤插画大轮廓避免图画被当成文字块
- 语种判定基于 OCR 文本量（中文字符 vs 英文字符），纯插图页默认英文
- 所有路径基于脚本所在目录，跨平台（Win/macOS/Linux）无需任何配置

## 常见问题

- **所有邮箱都失败**：某天全部账号被限流时提示"明天再试或添加新邮箱"，次日 `failed_at` 过期后自动复用。
- **rapidocr 未安装**：运行 `41语种识别.py` 会提示先 `pip install rapidocr_onnxruntime` 并退出。
- **跨平台运行**：无需任何修改，脚本按自身目录解析路径（见"路径约定"）。
- **git 提交看不到图片**：`output/`、`output_pdf/`、`output_jpg_crop/`、`中文/`、`英文/` 均被 `.gitignore` 排除，只持久化脚本、json 与 jsonl 元数据。
