# -*- coding: utf-8 -*-
import json
from pathlib import Path
from collections import defaultdict

# ================== 你需要改的路径 ==================
PRED_JSONL = Path("/Users/chenkaige/Desktop/new-podv1/datasets/qwen3-vl-8b-instruct/results.jsonl")          # 你的预测文件（jsonl：每行一个json）
LABELS_DIR = Path("/Users/chenkaige/Desktop/new-podv1/dataset/docs/labels")                # labels/*.txt
IMAGES_DIR = Path("/Users/chenkaige/Desktop/new-podv1/dataset/docs/images")                # 图片目录（网页相对路径基准）
OUT_JSON   = Path("/Users/chenkaige/Desktop/new-podv1/dataset/docs/data_orders.json")      # 输出给网页用
# ===================================================

STEP_KEYS = [
    "step1_valid_pod",
    "step2_has_package",
    "step3_not_in_mailbox",
    "step4_valid_location",
]

def derive_overall(step_dict):
    return 1 if all(int(step_dict.get(k, 0)) == 1 for k in STEP_KEYS) else 0

def order_prefix(image_name: str) -> str:
    # 例：general_SWX003100000018939890_jpg_2026...  -> general_SWX003100000018939890
    parts = image_name.split("_")
    return "_".join(parts[:2]) if len(parts) >= 2 else image_name

def candidate_label_paths(image_name: str):
    # 兼容：1) 原名 + .txt
    yield LABELS_DIR / f"{image_name}.txt"
    # 2) 去掉一层后缀（.jpg.jpg -> .jpg / .webp.webp -> .webp）
    p = Path(image_name)
    yield LABELS_DIR / f"{p.stem}.txt"
    # 3) 去掉两层后缀（针对 .jpg.jpg 这种）
    yield LABELS_DIR / f"{Path(p.stem).stem}.txt"

def read_gt(image_name: str):
    lab_path = None
    for cand in candidate_label_paths(image_name):
        if cand.exists():
            lab_path = cand
            break
    if lab_path is None:
        return None  # 缺失 GT

    s = lab_path.read_text(encoding="utf-8").strip()
    # 格式: 1,1,1,1,1
    arr = [x.strip() for x in s.split(",")]
    if len(arr) < 5:
        return None

    gt_steps = {
        "step1_valid_pod": int(arr[0]),
        "step2_has_package": int(arr[1]),
        "step3_not_in_mailbox": int(arr[2]),
        "step4_valid_location": int(arr[3]),
        "overall_pass": int(arr[4]),
    }
    return gt_steps

def main():
    # order_id -> list[items]
    groups = defaultdict(list)

    with PRED_JSONL.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)

            image_name = obj.get("image_name") or obj.get("parsed", {}).get("image_name")
            image_path = obj.get("image_path") or obj.get("parsed", {}).get("image_path") or image_name
            parsed = obj.get("parsed", {}) or {}

            pred_steps = {k: int(parsed.get(k, 0)) for k in STEP_KEYS}
            pred_overall = derive_overall(pred_steps)

            gt = read_gt(image_name)
            if gt is None:
                gt_steps = None
                gt_overall = None
            else:
                gt_steps = {k: int(gt.get(k, 0)) for k in STEP_KEYS}
                # 你给的第5位就是 overall_pass（真值）
                gt_overall = int(gt.get("overall_pass", 0))

            oid = order_prefix(image_name)

            # 网页里用相对路径加载图片：images/xxx.jpg
            # 如果你 IMAGES_DIR 就是网页同目录下 images，则保持如下写法
            # 网页里用相对路径加载图片：./images/xxx.jpg.jpg
            fname = Path(image_path).name  # 只取文件名，避免 /Users/... 绝对路径
            rel_img_src = f"./images/{fname}"


            groups[oid].append({
                "image_name": image_name,
                "image_src": rel_img_src,
                "pred": {**pred_steps, "overall_pass": pred_overall},
                "gt": (None if gt_steps is None else {**gt_steps, "overall_pass": gt_overall}),
            })

    # orders = []
    # for oid, items in groups.items():
    #     # 订单级：只要任意图片 overall_pass==1，则订单 pass=1
    #     pred_order_pass = 1 if any(int(it["pred"]["overall_pass"]) == 1 for it in items) else 0
    #     gt_order_pass = None
    #     if all(it["gt"] is not None for it in items):
    #         gt_order_pass = 1 if any(int(it["gt"]["overall_pass"]) == 1 for it in items) else 0

    #     orders.append({
    #         "order_id": oid,
    #         "pred_order_pass": pred_order_pass,
    #         "gt_order_pass": gt_order_pass,
    #         "images": items,
    #     })
    orders = []
    for oid, items in groups.items():
        # ================== 新订单规则 ==================
        # 1) 至少一张图 overall_pass==1 (等价于 1,1,1,1,1)
        # 2) 所有图 step3_not_in_mailbox==1

        # 预测订单级
        pred_all_not_in_mailbox = all(int(it["pred"].get("step3_not_in_mailbox", 0)) == 1 for it in items)
        pred_any_full_pass = any(int(it["pred"].get("overall_pass", 0)) == 1 for it in items)
        pred_order_pass = 1 if (pred_all_not_in_mailbox and pred_any_full_pass) else 0

        # 真值订单级（保持你原来的策略：必须所有图都有 gt 才算订单 gt，否则 None）
        gt_order_pass = None
        if all(it["gt"] is not None for it in items):
            gt_all_not_in_mailbox = all(int(it["gt"].get("step3_not_in_mailbox", 0)) == 1 for it in items)
            gt_any_full_pass = any(int(it["gt"].get("overall_pass", 0)) == 1 for it in items)
            gt_order_pass = 1 if (gt_all_not_in_mailbox and gt_any_full_pass) else 0
        # ==============================================

        orders.append({
            "order_id": oid,
            "pred_order_pass": pred_order_pass,
            "gt_order_pass": gt_order_pass,
            "images": items,
        })


    # 稳定排序：按 order_id
    orders.sort(key=lambda x: x["order_id"])

    OUT_JSON.write_text(json.dumps({"orders": orders}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK -> {OUT_JSON} | orders={len(orders)}")

if __name__ == "__main__":
    main()
