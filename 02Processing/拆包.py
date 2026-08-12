# 合并流程：遍历 ..\01Reverse crawler\output 中的 zip
#   1. 提取 PDF，按 MD5 存到 output_pdf\{md5}\{md5}.pdf（已存在则跳过）
#   2. 逐页渲染 JPG 到同一文件夹，命名 {md5}_{原页码:补零}.jpg
#      删除首页及末尾 3 页（不渲染、不保存、不纳入 JSON），保留页沿用原 PDF 页码，不重新编号
#   3. 汇总元数据写入 output.json
# 源 zip 不删除；已存在的 PDF/JPG 跳过；被删页的旧 JPG 自动清理
import hashlib
import json
import os
import zipfile

import pymupdf as fitz  # PyMuPDF

# 脚本所在目录（即 02Processing），无论从哪里运行都以这里为基准
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ZIP_DIR = os.path.join(BASE_DIR, "..", "01Reverse crawler", "output")
OUTPUT_ROOT = os.path.join(BASE_DIR, "output_pdf")
OUTPUT_JSON = os.path.join(BASE_DIR, "output.json")

# 要裁掉的页数：开头 DROP_HEAD 页，末尾 DROP_TAIL 页
DROP_HEAD = 1
DROP_TAIL = 3

# 渲染倍数：2 约等于 144 DPI，画质和体积比较均衡；需要更清晰可以调大
ZOOM = 2
JPEG_QUALITY = 90

os.makedirs(OUTPUT_ROOT, exist_ok=True)


def md5_of_bytes(data):
    return hashlib.md5(data).hexdigest()


books = {}  # 以故事 ID 为键，自动去重（例如 3.zip 和 11986-...zip 是同一本）
total = len([f for f in os.listdir(ZIP_DIR) if f.lower().endswith(".zip")])
index = 0

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

            # 每本绘本的专属目录
            book_dir = os.path.join(OUTPUT_ROOT, md5)
            os.makedirs(book_dir, exist_ok=True)
            pdf_path = os.path.join(book_dir, f"{md5}.pdf")

            # 1. 写入 PDF（已存在则跳过）
            if os.path.isfile(pdf_path):
                print("  PDF 已存在，跳过写入")
            else:
                with open(pdf_path, "wb") as dst:
                    dst.write(pdf_data)
                print(f"  已提取 PDF: {md5}.pdf")

            # 2. 渲染 JPG
            matrix = fitz.Matrix(ZOOM, ZOOM)
            image_names = []
            skipped = 0
            with fitz.open(pdf_path) as doc:
                width = max(2, len(str(doc.page_count)))  # 按原总页数确定补零宽度，保留的页码不重排
                kept_indices = list(range(doc.page_count))[DROP_HEAD:doc.page_count - DROP_TAIL]
                dropped_indices = set(range(doc.page_count)) - set(kept_indices)

                # 清理旧版本可能已经生成的、属于被删页的图片
                for page_index in dropped_indices:
                    dropped_path = os.path.join(
                        book_dir, f"{md5}_{page_index + 1:0{width}d}.jpg"
                    )
                    if os.path.isfile(dropped_path):
                        os.remove(dropped_path)

                if not kept_indices:
                    print(f"  跳过渲染：总页数 {doc.page_count} 不足，删除首尾后没有剩余页面")
                    continue

                for page_index in kept_indices:
                    image_name = f"{md5}_{page_index + 1:0{width}d}.jpg"
                    image_path = os.path.join(book_dir, image_name)
                    if os.path.isfile(image_path):
                        image_names.append(image_name)
                        skipped += 1
                        continue
                    page = doc[page_index]
                    pix = page.get_pixmap(matrix=matrix, alpha=False)
                    pix.save(image_path, jpg_quality=JPEG_QUALITY)
                    image_names.append(image_name)

            rel_dir = os.path.join("output_pdf", md5)
            books[story_id] = {
                "story_id": int(story_id),
                "slug": slug,
                "pdf_file": os.path.join(rel_dir, f"{md5}.pdf"),
                "source_zip": filename,
                "md5": md5,
                "page_count": len(image_names),
                "images": [os.path.join(rel_dir, name) for name in image_names],
            }
            deleted_note = f"，已删除首尾 {DROP_HEAD + DROP_TAIL} 页"
            skipped_note = f"（其中 {skipped} 张已存在，跳过）" if skipped else ""
            print(f"  完成: 保留 {len(image_names)} 页{deleted_note}{skipped_note}")
    except zipfile.BadZipFile:
        print("  跳过：不是有效的 zip 文件（可能是下载失败的错误页）")

result = list(books.values())
with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"\n共记录 {len(result)} 本绘本，元数据已写入: {OUTPUT_JSON}")
