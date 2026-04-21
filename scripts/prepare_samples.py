#!/usr/bin/env python3
"""
prepare_samples.py
预处理 local_articles_datasets 中的样文，清洗微信公众号 UI 噪音，
输出到扁平目录供 build_*_profile 使用。
"""

import glob
import os
import re
import shutil
import sys
from pathlib import Path

NOISE_LINES = [
    "已关注", "关注", "重播", "分享", "赞", "关闭",
    "观看更多", "更多", "退出全屏", "展开全文", "阅读原文",
    "写下你的留言", "精选留言", "赞", "在看",
]


def clean_text(text: str) -> str:
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # 跳过纯噪音行
        if stripped in NOISE_LINES:
            continue
        # 跳过空图片引用
        if stripped == "![]()":
            continue
        # 跳过图片说明行（如果它本身是一张图片的 markdown）
        if re.match(r'^!\[.*?\]\(.*?\)$', stripped):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def main() -> int:
    src_base = Path("e:/Allproject/PyProject/StyleDistill_SKILLS/local_articles_datasets/AGI Hunt")
    dst_dir = Path("e:/Allproject/PyProject/StyleDistill_SKILLS/yiyi_skill/Claude/test_samples")
    dst_dir.mkdir(parents=True, exist_ok=True)

    md_files = sorted(src_base.rglob("*.md"))
    if not md_files:
        print("No .md files found")
        return 1

    for md in md_files:
        raw = md.read_text(encoding="utf-8")
        cleaned = clean_text(raw)
        # 保留文件名
        out_name = md.name
        out_path = dst_dir / out_name
        out_path.write_text(cleaned, encoding="utf-8")
        print(f"Prepared: {out_name} ({len(cleaned)} chars)")

    print(f"\nAll {len(md_files)} samples prepared in {dst_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
