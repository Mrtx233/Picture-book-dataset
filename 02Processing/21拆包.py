# 合并流程：遍历 ..\01Reverse crawler\output 中的 zip
#   1. 从 zip 中直接读取 PDF（不落盘），去重后决定每本的保留页
#   2. 逐页渲染 JPG 到同一文件夹，裁掉四周各 3%（去除白边/扫描边框），命名 {md5}_{原页码:补零}.jpg，分辨率不低于 720p（1280x720）
#      删除首页及末尾 4 页（不渲染、不保存、不纳入 metadata），保留页沿用原 PDF 页码，不重新编号
#   3. 每本绘本处理完成后立即追加一行到 metadata.jsonl，格式：{"data":[{"type":"image","image_url":"..."}, ...]}
# 源 zip 不删除；已存在的 JPG 跳过；被删页的旧 JPG 自动清理；已在 jsonl 中的绘本跳过
import hashlib
import json
import os
import zipfile
from datetime import datetime

import pymupdf as fitz  # PyMuPDF

# 脚本所在目录（即 02Processing），无论从哪里运行都以这里为基准
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ZIP_DIR = os.path.join(BASE_DIR, "..", "01Reverse crawler", "output")
OUTPUT_ROOT = os.path.join(BASE_DIR, "output_pdf")
OUTPUT_JSONL = os.path.join(BASE_DIR, "metadata.jsonl")

# 要裁掉的页数：开头 DROP_HEAD 页，末尾 DROP_TAIL 页
DROP_HEAD = 1
DROP_TAIL = 4

# 渲染倍数：2 约等于 144 DPI，画质和体积比较均衡；需要更清晰可以调大
ZOOM = 2
# 转 JPG 的最低分辨率（像素）：渲染结果至少达到 720p（1280x720），页面较小时自动提高缩放倍数
MIN_WIDTH = 1280
MIN_HEIGHT = 720
JPEG_QUALITY = 90
# 裁剪比例：渲染后裁掉四周各 3%，去除 PDF 白边/扫描边框
CROP_RATIO = 0.03

# 文件夹名中的日期（运行当天）
TODAY = datetime.now().strftime("%Y%m%d")

os.makedirs(OUTPUT_ROOT, exist_ok=True)


def md5_of_bytes(data):
    return hashlib.md5(data).hexdigest()


books = set()  # 本次运行已记录的绘本（以故事 ID 去重，例如 3.zip 和 11986-...zip 是同一本）
total = len([f for f in os.listdir(ZIP_DIR) if f.lower().endswith(".zip")])
index = 0

# 读取已有的 metadata.jsonl，避免重复写入（断点续跑）
done_book_dirs = set()
if os.path.isfile(OUTPUT_JSONL):
    with open(OUTPUT_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                first_url = json.loads(line).get("data", [])[0].get("image_url")
                if first_url:
                    done_book_dirs.add(first_url.split("/", 1)[0])
            except (json.JSONDecodeError, IndexError, AttributeError):
                continue

for filename in sorted(os.listdir(ZIP_DIR)):
    if not filename.lower().endswith(".zip"):
        continue
    index += 1
    zip_path = os.path.join(ZIP_DIR, filename)
    print(f"[{index}/{total}] 处理: {filename}")

    try:
        with zipfile.ZipFile(zip_path) as zf:
            pdf_names = [n for n in zf.namelist() if n.lower().endswith(".pdf")]
            if not pdf_names:
                print("  跳过：压缩包里没有 PDF")
                continue

            pdf_name = pdf_names[0]
            pdf_data = zf.read(pdf_name)
            md5 = md5_of_bytes(pdf_data)
            story_id = pdf_name.split("-", 1)[0]
            slug = os.path.splitext(pdf_name)[0]

            # 确定总页数与保留页，便于生成文件夹名和补零宽度
            with fitz.open(stream=pdf_data, filetype="pdf") as temp_doc:
                total_pages = temp_doc.page_count
            width = max(2, len(str(total_pages)))  # 按原总页数确定补零宽度，保留的页码不重排
            kept_indices = list(range(total_pages))[DROP_HEAD:total_pages - DROP_TAIL]
            dropped_indices = set(range(total_pages)) - set(kept_indices)

            if not kept_indices:
                print(f"  跳过渲染：总页数 {total_pages} 不足，删除首尾后没有剩余页面")
                continue

            # 每本绘本的专属目录：{slug}_{日期}_{保留页数}
            book_dir_name = f"{slug}_{TODAY}_{len(kept_indices)}"
            if story_id in books or book_dir_name in done_book_dirs:
                print(f"  已记录过，跳过")
                continue
            book_dir = os.path.join(OUTPUT_ROOT, book_dir_name)
            os.makedirs(book_dir, exist_ok=True)

            # 渲染 JPG
            image_names = []
            skipped = 0

            # 清理旧版本可能已经生成的、属于被删页的图片
            for page_index in dropped_indices:
                dropped_path = os.path.join(
                    book_dir, f"{md5}_{page_index + 1:0{width}d}.jpg"
                )
                if os.path.isfile(dropped_path):
                    os.remove(dropped_path)

            with fitz.open(stream=pdf_data, filetype="pdf") as doc:
                for page_index in kept_indices:
                    image_name = f"{md5}_{page_index + 1:0{width}d}.jpg"
                    image_path = os.path.join(book_dir, image_name)
                    if os.path.isfile(image_path):
                        image_names.append(image_name)
                        skipped += 1
                        continue
                    page = doc[page_index]
                    # 按页面尺寸动态算缩放倍数，保证渲染结果至少 1280x720（720p）
                    zoom = max(ZOOM, MIN_WIDTH / page.rect.width, MIN_HEIGHT / page.rect.height)
                    # 裁掉四周白边/扫描边框（各 3%），在渲染时裁剪避免后处理
                    rect = page.rect
                    clip = fitz.Rect(
                        rect.x0 + rect.width * CROP_RATIO,
                        rect.y0 + rect.height * CROP_RATIO,
                        rect.x1 - rect.width * CROP_RATIO,
                        rect.y1 - rect.height * CROP_RATIO,
                    )
                    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False, clip=clip)
                    pix.save(image_path, jpg_quality=JPEG_QUALITY)
                    image_names.append(image_name)

            # 3. 生成 metadata 行并立即追加写入 jsonl
            data = [
                {"type": "image", "image_url": f"{book_dir_name}/{name}"}
                for name in image_names
            ]
            with open(OUTPUT_JSONL, "a", encoding="utf-8") as f:
                f.write(json.dumps({"data": data}, ensure_ascii=False) + "\n")
            books.add(story_id)

            deleted_note = f"，已删除首尾 {DROP_HEAD + DROP_TAIL} 页"
            skipped_note = f"（其中 {skipped} 张已存在，跳过）" if skipped else ""
            print(f"  完成: 保留 {len(image_names)} 页{deleted_note}{skipped_note}")
    except zipfile.BadZipFile:
        print("  跳过：不是有效的 zip 文件（可能是下载失败的错误页）")

print(f"\n本次新增 {len(books)} 本绘本，元数据已追加写入: {OUTPUT_JSONL}")
