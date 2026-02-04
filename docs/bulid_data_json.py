# build_data_json.py
import json
from pathlib import Path

# 以当前目录为根目录（dataset_current）
ROOT = Path(".")
IMG_DIR = Path("/Users/chenkaige/Desktop/new-podv1/dataset/docs/image")
LAB_DIR = Path("/Users/chenkaige/Desktop/new-podv1/dataset/docs/labels")
OUT = ROOT / "data.json"

STEP_KEYS = [
    "step1_valid_pod",
    "step2_has_package",
    "step3_not_in_mailbox",
    "step4_valid_location",
]

def parse_label_line(line: str):
    raw = line.strip()
    parts = [p.strip() for p in raw.split(",")]
    parts = (parts + [""] * 4)[:4]  # 只取前4列，不足补空

    values = []
    for p in parts:
        if p == "":
            values.append(None)
        else:
            try:
                values.append(int(p))
            except Exception:
                values.append(p)

    by_key = {k: values[i] for i, k in enumerate(STEP_KEYS)}
    return {"raw": raw, "values": values, "by_key": by_key}

def main():
    if not IMG_DIR.exists():
        raise FileNotFoundError(f"找不到图片目录：{IMG_DIR.resolve()}")
    if not LAB_DIR.exists():
        raise FileNotFoundError(f"找不到标注目录：{LAB_DIR.resolve()}")

    img_files = []
    for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
        img_files += sorted(IMG_DIR.glob(ext))

    items = []
    for img_path in img_files:
        stem = img_path.stem
        lab_path = LAB_DIR / f"{stem}.txt"

        if lab_path.exists():
            text = lab_path.read_text(encoding="utf-8", errors="ignore").strip()
            first_line = text.splitlines()[0] if text else ""
            label_info = parse_label_line(first_line)
        else:
            label_info = {"raw": "", "values": [None]*4, "by_key": {k: None for k in STEP_KEYS}}

        by_key = label_info["by_key"]
        overall_pass = 1 if all(by_key[k] == 1 for k in STEP_KEYS) else 0

        items.append({
            "image_name": img_path.name,
            "image_relpath": f"image/{img_path.name}",
            "label_relpath": f"label/{stem}.txt",
            "label": label_info,
            "overall_pass": overall_pass
        })

    OUT.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"found images: {len(img_files)} in {IMG_DIR}")
    print(f"wrote {len(items)} items -> {OUT}")

if __name__ == "__main__":
    main()
