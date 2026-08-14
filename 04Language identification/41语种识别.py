"""
基于 03Finishing process 的 output_jpg_crop 和 metadata.jsonl，以文件夹（每本绘本）为单位，
对每张图片做语种识别（中文 / 英文）：
  1. 用 rapidocr 提取图片中的文字
  2. 统计中文字符 vs 英文字符数量，判定语种
  3. 图片按语种复制到 04Language identification/中文/{书目录}/ 或 英文/{书目录}/
  4. 每本处理完追加一行同格式 jsonl（image_url 带语种前缀），支持断点续跑

依赖：pip install rapidocr_onnxruntime
"""
import json
import os
import shutil

try:
    from rapidocr_onnxruntime import RapidOCR
except ImportError:
    print("缺少依赖：请先运行  pip install rapidocr_onnxruntime")
    raise SystemExit(1)

# 路径配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_CROP_DIR = os.path.join(BASE_DIR, "..", "03Finishing process", "output_jpg_crop")
INPUT_JSONL = os.path.join(BASE_DIR, "..", "03Finishing process", "metadata.jsonl")
OUTPUT_JSONL = os.path.join(BASE_DIR, "metadata.jsonl")

LANGS = ("中文", "英文")


def classify_language(texts):
    """根据 OCR 识别出的文字判定语种：中文字符多→中文，否则英文"""
    text = "".join(texts)
    cjk = sum(1 for c in text if "一" <= c <= "鿿")
    latin = sum(1 for c in text if c.isascii() and c.isalpha())
    if cjk == 0 and latin == 0:
        return "英文"  # 未识别到文字（纯插图页），默认英文
    return "中文" if cjk >= latin else "英文"


def load_books():
    """读取 03 的 metadata.jsonl，返回 [{book_dir, images:[image_url,...]}, ...]"""
    books = []
    with open(INPUT_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line).get("data", [])
            urls = [img.get("image_url") for img in data if img.get("image_url")]
            if not urls:
                continue
            books.append({"book_dir": urls[0].split("/", 1)[0], "images": urls})
    return books


def load_done():
    """读取已有输出 jsonl，返回已处理完的 book_dir 集合（断点续跑）"""
    done = set()
    if not os.path.isfile(OUTPUT_JSONL):
        return done
    with open(OUTPUT_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line).get("data", [])
                first = next((img.get("image_url") for img in data if img.get("image_url")), None)
                if first:
                    # image_url 形如 "中文/529-masala-chai_20260814_15/xxx.jpg"
                    done.add(first.split("/", 2)[1])
            except (json.JSONDecodeError, IndexError, AttributeError):
                continue
    return done


def main():
    if not os.path.isfile(INPUT_JSONL):
        print(f"找不到 {INPUT_JSONL}")
        return
    if not os.path.isdir(INPUT_CROP_DIR):
        print(f"找不到 {INPUT_CROP_DIR}")
        return

    ocr = RapidOCR()

    books = load_books()
    done = load_done()
    total_books = len(books)
    new_books = 0
    new_images = 0

    for book_index, book in enumerate(books, 1):
        if book["book_dir"] in done:
            print(f"跳过已处理: {book['book_dir']}")
            continue
        print(f"[{book_index}/{total_books}] {book['book_dir']}")

        data = []
        for image_url in book["images"]:
            img_name = os.path.basename(image_url)
            img_path = os.path.join(INPUT_CROP_DIR, image_url)
            print(f"    {img_name}")

            if not os.path.isfile(img_path):
                print(f"      跳过：文件不存在")
                continue

            try:
                result, _ = ocr(img_path)
                texts = [item[1] for item in result] if result else []
            except Exception as e:
                print(f"      OCR 失败: {e}")
                continue

            lang = classify_language(texts)
            print(f"      语种: {lang}")

            # 复制到对应语种文件夹
            lang_dir = os.path.join(BASE_DIR, lang, book["book_dir"])
            os.makedirs(lang_dir, exist_ok=True)
            shutil.copy2(img_path, os.path.join(lang_dir, img_name))

            data.append({"type": "image", "image_url": f"{lang}/{book['book_dir']}/{img_name}"})

        if not data:
            print(f"  无有效图片，跳过")
            continue

        # 每本处理完立即追加一行 jsonl
        with open(OUTPUT_JSONL, "a", encoding="utf-8") as f:
            f.write(json.dumps({"data": data}, ensure_ascii=False) + "\n")
        new_books += 1
        new_images += len(data)
        print(f"  完成: {len(data)} 张")

    print(f"\n完成：本次新增 {new_books} 本绘本（共 {total_books} 本），{new_images} 张图片")
    print(f"输出 jsonl: {OUTPUT_JSONL}")
    print(f"图片: {BASE_DIR}/中文/、{BASE_DIR}/英文/")


if __name__ == "__main__":
    main()
