"""
扫描 02Processing/output_pdf 下的子文件夹（每本绘本一个目录，如 529-masala-chai_20260814_23）：
  1. 逐张计算文字块区域占比 text_block_ratio
     （二值化 → 按字符尺寸过滤掉插画黑色大轮廓 → 膨胀合并文字成文本块 → 包围盒面积 / 整图面积）
  2. text_block_ratio < 50% 的保留（大插图页），>= 50% 的过滤（大段文字页）
  3. 保留图按实际张数重命名文件夹 {slug}_{日期}_{保留数} 保存到 output_jpg_crop
  4. 每本处理完立即追加一行 jsonl，支持断点续跑
"""
import json
import os
import shutil

import cv2
import numpy as np

# 路径配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_ROOT = os.path.join(BASE_DIR, "..", "02Processing", "output_pdf")
OUTPUT_JSONL = os.path.join(BASE_DIR, "metadata.jsonl")
OUTPUT_CROP_DIR = os.path.join(BASE_DIR, "output_jpg_crop")

# 文字块占比低于此值才保留（大插图页）
TEXT_THRESHOLD = 0.5
# 膨胀核：横向大把一行内单词粘连，纵向小区分不同段落
KERNEL_SIZE = (18, 12)
# 字符尺寸上限：超过判定为绘画线条轮廓，直接丢弃（过滤插画黑色大轮廓）
MAX_CHAR_BOX_W = 120
MAX_CHAR_BOX_H = 60


def calc_text_block_area_ratio(img_path, kernel_size=KERNEL_SIZE, max_char_box_w=MAX_CHAR_BOX_W, max_char_box_h=MAX_CHAR_BOX_H):
    """
    绘本专用：只统计文字区域占比，过滤插画黑色大轮廓
    :param img_path: 图片路径
    :param kernel_size: 膨胀核，把一行行文字粘连成大文本块
    :param max_char_box_w: 单个字符最大宽度，超过判定为绘画线条直接丢弃
    :param max_char_box_h: 单个字符最大高度，超过判定为绘画线条直接丢弃
    :return: text_ratio 文字块占比(0~1)
    """
    img = cv2.imread(img_path)
    if img is None:
        return 1.0
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 二值反转：文字线条变成白色
    _, binary = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY_INV)

    # 找全部小连通域，过滤掉绘画大轮廓
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mask_text_only = np.zeros_like(binary)

    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        # 核心！过滤掉插画大线条轮廓，只保留字符大小的小块
        if cw < max_char_box_w and ch < max_char_box_h:
            cv2.drawContours(mask_text_only, [cnt], -1, 255, -1)

    # 把细碎文字膨胀合并成整行文本块
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, kernel_size)
    dilate = cv2.dilate(mask_text_only, kernel, iterations=2)

    text_contours, _ = cv2.findContours(dilate, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    total_text_box_area = 0
    for cnt in text_contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        total_text_box_area += cw * ch

    total_img_area = h * w
    text_ratio = total_text_box_area / total_img_area
    return round(text_ratio, 4)


def load_books():
    """扫描 output_pdf 下的子文件夹，每个文件夹是一本绘本，返回 [{book_dir, images:[image_url,...]}, ...]"""
    books = []
    if not os.path.isdir(INPUT_ROOT):
        return books
    for name in sorted(os.listdir(INPUT_ROOT)):
        folder = os.path.join(INPUT_ROOT, name)
        if not os.path.isdir(folder):
            continue
        images = sorted(
            f for f in os.listdir(folder)
            if f.lower().endswith(".jpg") or f.lower().endswith(".jpeg")
        )
        if not images:
            continue
        books.append({
            "book_dir": name,
            "images": [f"{name}/{img}" for img in images],
        })
    return books


def load_done():
    """读取已有输出 jsonl，返回已处理完的绘本集合（以 {slug}_{日期} 为键，断点续跑）"""
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
                    done.add(first.split("/", 1)[0].rsplit("_", 2)[0])
            except (json.JSONDecodeError, IndexError, AttributeError):
                continue
    return done


def main():
    if not os.path.isdir(INPUT_ROOT):
        print(f"找不到 {INPUT_ROOT}")
        return

    books = load_books()
    done = load_done()
    total_books = len(books)
    new_books = 0
    new_images = 0

    for book_index, book in enumerate(books, 1):
        base = book["book_dir"].rsplit("_", 2)[0]  # {slug}_{日期}
        if base in done:
            print(f"跳过已处理: {book['book_dir']}")
            continue
        print(f"[{book_index}/{total_books}] {book['book_dir']}")

        kept_names = []  # 保留的图片文件名
        for image_url in book["images"]:
            img_name = os.path.basename(image_url)
            print(f"    {img_name}")
            img_full_path = os.path.join(INPUT_ROOT, image_url)

            if not os.path.isfile(img_full_path):
                print(f"      跳过：文件不存在")
                continue

            ratio = calc_text_block_area_ratio(img_full_path)
            if ratio < TEXT_THRESHOLD:
                kept_names.append(img_name)
                print(f"      文字块占比 {ratio:.2%} < 50%，保留")
            else:
                print(f"      文字块占比 {ratio:.2%} >= 50%，过滤")

        if not kept_names:
            print(f"  无保留图片，跳过")
            continue

        # 输出文件夹按实际保留张数命名
        new_book_dir = f"{base}_{len(kept_names)}"
        crop_dir = os.path.join(OUTPUT_CROP_DIR, new_book_dir)
        os.makedirs(crop_dir, exist_ok=True)

        data = []
        for img_name in kept_names:
            src = os.path.join(INPUT_ROOT, book["book_dir"], img_name)
            dst = os.path.join(crop_dir, img_name)
            shutil.copyfile(src, dst)
            data.append({"type": "image", "image_url": f"{new_book_dir}/{img_name}"})

        # 每本处理完立即追加一行 jsonl
        with open(OUTPUT_JSONL, "a", encoding="utf-8") as f:
            f.write(json.dumps({"data": data}, ensure_ascii=False) + "\n")
        new_books += 1
        new_images += len(kept_names)
        print(f"  保留 {len(kept_names)} 张 -> {new_book_dir}")

    print(f"\n完成：本次新增 {new_books} 本绘本（共 {total_books} 本），{new_images} 张图片")
    print(f"输出 jsonl: {OUTPUT_JSONL}")
    print(f"保留图片: {OUTPUT_CROP_DIR}")


if __name__ == "__main__":
    main()
