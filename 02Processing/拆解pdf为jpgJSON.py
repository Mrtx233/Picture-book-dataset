# 拆解 output_pdf 中的 PDF，逐页输出为 JPG：
#   JPG 命名为 {pdf的md5}_{页码:02d}.jpg，放在 output_jpg/{md5}/ 下
# 删除首页及末尾 3 页（不渲染、不保存、不纳入 JSON），其余页面保留原 PDF 页码，不重新编号
# 已存在的图片跳过；汇总每本绘本的图片数量和文件名，写入 output_pdf_jpg.json
import json
import os

import pymupdf as fitz  # PyMuPDF

# 脚本所在目录（即 02Processing），无论从哪里运行都以这里为基准
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_DIR = os.path.join(BASE_DIR, "output_pdf")
JPG_DIR = os.path.join(BASE_DIR, "output_jpg")
INPUT_JSON = os.path.join(BASE_DIR, "output.json")
OUTPUT_JSON = os.path.join(BASE_DIR, "output_pdf_jpg.json")

# 要裁掉的页数：开头 DROP_HEAD 页，末尾 DROP_TAIL 页
DROP_HEAD = 1
DROP_TAIL = 3

# 渲染倍数：2 约等于 144 DPI，画质和体积比较均衡；需要更清晰可以调大
ZOOM = 2
JPEG_QUALITY = 90

with open(INPUT_JSON, "r", encoding="utf-8") as f:
    books = json.load(f)

result = []
for index, book in enumerate(books, start=1):
    md5 = book["md5"]
    pdf_path = os.path.join(PDF_DIR, f"{md5}.pdf")
    out_subdir = os.path.join(JPG_DIR, md5)
    os.makedirs(out_subdir, exist_ok=True)

    print(f"[{index}/{len(books)}] 拆解: {md5}.pdf")

    if not os.path.isfile(pdf_path):
        print(f"  跳过：找不到 {pdf_path}")
        continue

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
                out_subdir, f"{md5}_{page_index + 1:0{width}d}.jpg"
            )
            if os.path.isfile(dropped_path):
                os.remove(dropped_path)

        if not kept_indices:
            print(f"  跳过：总页数 {doc.page_count} 不足，删除首尾后没有剩余页面")
            continue

        for page_index in kept_indices:
            image_name = f"{md5}_{page_index + 1:0{width}d}.jpg"
            image_path = os.path.join(out_subdir, image_name)
            if os.path.isfile(image_path):
                image_names.append(image_name)
                skipped += 1
                continue
            page = doc[page_index]
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            pix.save(image_path, jpg_quality=JPEG_QUALITY)
            image_names.append(image_name)

    result.append({
        "md5": md5,
        "story_id": book.get("story_id"),
        "slug": book.get("slug"),
        "page_count": len(image_names),
        "images": [os.path.join("output_jpg", md5, name) for name in image_names],
    })
    deleted_note = f"，已删除首尾 {DROP_HEAD + DROP_TAIL} 页"
    skipped_note = f"（其中 {skipped} 页已存在，跳过）" if skipped else ""
    print(f"  完成: 保留 {len(image_names)} 页{deleted_note}{skipped_note}")

with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"\n共处理 {len(result)} 本绘本，元数据已写入: {OUTPUT_JSON}")
