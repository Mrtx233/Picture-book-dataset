"""
读取 output.json，逐张图片：
  1. 第一次识别：原始图片白色背景占比
  2. 四周各裁剪 5%
  3. 第二次识别：裁剪后白色背景占比
裁剪后白色占比 < 50% 的保存到 output_jpg_crop，每张立即写 JSON，支持断点续跑。
"""
import json
import os
from PIL import Image

# 路径配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_JSON = os.path.join(BASE_DIR, "..", "02Processing", "output.json")
# img_rel_path 已经包含 "output_pdf/..."，所以基目录是 02Processing
INPUT_BASE_DIR = os.path.join(BASE_DIR, "..", "02Processing")
OUTPUT_JSON = os.path.join(BASE_DIR, "output.json")
OUTPUT_CROP_DIR = os.path.join(BASE_DIR, "output_jpg_crop")

# 白色判断阈值：RGB 三通道均 >= 此值视为白色像素
WHITE_THRESHOLD = 240
# 裁剪比例：四周各裁 5%
CROP_RATIO = 0.05
# 裁剪后白色占比低于此值才保存裁剪图
CROP_THRESHOLD = 0.6


def white_bg_ratio(image):
    """计算 PIL Image 中白色背景像素的占比，返回 0.0 ~ 1.0"""
    if isinstance(image, str):
        img = Image.open(image).convert("RGB")
    else:
        img = image.convert("RGB")
    pixels = img.get_flattened_data()
    white_count = sum(1 for r, g, b in pixels if r >= WHITE_THRESHOLD and g >= WHITE_THRESHOLD and b >= WHITE_THRESHOLD)
    total = len(pixels)
    return white_count / total if total > 0 else 0


def save_json(books):
    """保存 JSON 到文件"""
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(books, f, ensure_ascii=False, indent=2)


def main():
    if not os.path.isfile(INPUT_JSON):
        print(f"找不到 {INPUT_JSON}")
        return

    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        books = json.load(f)

    # 加载已有结果，支持断点续跑
    if os.path.isfile(OUTPUT_JSON):
        with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
            done_books = json.load(f)
        done_images = set()
        for b in done_books:
            for img in b.get("images", []):
                if "white_bg_ratio_crop" in img:
                    done_images.add(img["path"])
        print(f"已有 {len(done_images)} 张图片已处理，跳过")
    else:
        done_images = set()

    total_images = sum(len(b["images"]) for b in books)
    processed = len(done_images)

    for book in books:
        md5 = book["md5"]
        new_images = book.get("images", [])
        # 如果已有分析结果则跳过整本
        if "images" in book and book["images"] and "white_bg_ratio_crop" in book["images"][0]:
            continue

        for i, img_rel_path in enumerate(book["images"]):
            if img_rel_path in done_images:
                continue

            img_full_path = os.path.join(INPUT_BASE_DIR, img_rel_path)
            processed += 1
            print(f"[{processed}/{total_images}] {img_rel_path}")

            if not os.path.isfile(img_full_path):
                print(f"  跳过：文件不存在")
                new_images[i] = {
                    "path": img_rel_path,
                    "white_bg_ratio": 0,
                    "white_bg_ratio_crop": 0,
                    "error": "file not found",
                }
            else:
                try:
                    img = Image.open(img_full_path)
                    w, h = img.size

                    # 第一次识别：原始图片
                    wb_ratio = white_bg_ratio(img)

                    # 裁剪
                    crop_left = int(w * CROP_RATIO)
                    crop_top = int(h * CROP_RATIO)
                    crop_right = w - crop_left
                    crop_bottom = h - crop_top
                    cropped = img.crop((crop_left, crop_top, crop_right, crop_bottom))

                    # 第二次识别：裁剪后图片
                    wb_ratio_crop = white_bg_ratio(cropped)

                    img.close()

                    new_images[i] = {
                        "path": img_rel_path,
                        "white_bg_ratio": round(wb_ratio, 4),
                        "white_bg_ratio_crop": round(wb_ratio_crop, 4),
                        "original_width": w,
                        "original_height": h,
                        "crop_left": crop_left,
                        "crop_top": crop_top,
                        "crop_right": crop_right,
                        "crop_bottom": crop_bottom,
                    }

                    # 裁剪后白色占比 < 50% 才保存裁剪图
                    if wb_ratio_crop < CROP_THRESHOLD:
                        img_name = os.path.basename(img_rel_path)
                        crop_dir = os.path.join(OUTPUT_CROP_DIR, md5)
                        os.makedirs(crop_dir, exist_ok=True)
                        crop_path = os.path.join(crop_dir, img_name)
                        cropped.save(crop_path, quality=90)
                    else:
                        print(f"  裁剪后白色占比 {wb_ratio_crop:.2%} >= 60%，跳过保存裁剪图")

                except Exception as e:
                    wb_ratio = 0
                    print(f"  计算失败: {e}")
                    new_images[i] = {
                        "path": img_rel_path,
                        "white_bg_ratio": 0,
                        "white_bg_ratio_crop": 0,
                        "error": str(e),
                    }

            book["images"] = new_images
            save_json(books)

    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    save_json(books)

    print(f"\n完成：{len(books)} 本绘本，{total_images} 张图片")
    print(f"输出 JSON: {OUTPUT_JSON}")
    print(f"裁剪图片: {OUTPUT_CROP_DIR}")


if __name__ == "__main__":
    main()