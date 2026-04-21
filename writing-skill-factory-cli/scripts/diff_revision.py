#!/usr/bin/env python3
"""
diff_revision.py
分析 baseline 与用户修改稿的差异，提取 revision signals。

用法:
    python diff_revision.py <child_name> <article_id> [--factory-dir <dir>] [--project-root <dir>]
"""

import argparse
import difflib
import json
import re
import sys
from pathlib import Path


def classify_change(old_text: str, new_text: str, context: str) -> dict:
    """简单分类变更类型"""
    old_len = len(old_text)
    new_len = len(new_text)
    delta = new_len - old_len

    # L1: 微小改动
    if abs(delta) < 10 and abs(len(old_text.split())) - len(new_text.split()) < 3:
        return {"level": "L1", "type": "cosmetic", "reason": "微小文本变动"}

    # L3: 结构性变化（段落重排、开头/结尾改写）
    old_paras = [p.strip() for p in old_text.split('\n\n') if p.strip()]
    new_paras = [p.strip() for p in new_text.split('\n\n') if p.strip()]
    if len(old_paras) != len(new_paras) or abs(delta) > len(old_text) * 0.3:
        return {"level": "L3", "type": "structural", "reason": "段落结构或大幅改写"}

    # L2: 可复用偏好
    return {"level": "L2", "type": "reusable_preference", "reason": "中等规模文本调整"}


def diff_revision(child_name: str, article_id: str, factory_dir: str, project_root: str) -> dict:
    root = Path(project_root).resolve()
    repo_dir = Path(factory_dir) / child_name / "repo"
    state_dir = repo_dir / "state"
    baselines_dir = state_dir / "baselines"
    revisions_dir = state_dir / "revisions"

    baseline_file = baselines_dir / f"{article_id}.md"
    visible_dir = root / f"{child_name}_Generated_Articles"
    visible_files = list(visible_dir.glob(f"{article_id}__*.md"))
    if not visible_files:
        return {"status": "error", "message": f"Visible file not found for {article_id}"}
    visible_file = visible_files[0]

    if not baseline_file.exists():
        return {"status": "error", "message": f"Baseline not found for {article_id}"}

    baseline_text = baseline_file.read_text(encoding="utf-8")
    visible_text = visible_file.read_text(encoding="utf-8")

    # 移除 frontmatter 进行对比
    def strip_frontmatter(text: str) -> str:
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                return parts[2].strip()
        return text.strip()

    baseline_body = strip_frontmatter(baseline_text)
    visible_body = strip_frontmatter(visible_text)

    # 生成 diff
    diff = list(difflib.unified_diff(
        baseline_body.splitlines(keepends=True),
        visible_body.splitlines(keepends=True),
        fromfile="baseline",
        tofile="visible",
    ))
    diff_text = "".join(diff)

    # 提取变更块并分类
    changes = []
    hunks = re.split(r'@@ .* @@\n', diff_text)
    for hunk in hunks[1:]:
        added = "".join([l[1:] for l in hunk.splitlines(keepends=True) if l.startswith("+") and not l.startswith("+++")])
        removed = "".join([l[1:] for l in hunk.splitlines(keepends=True) if l.startswith("-") and not l.startswith("---")])
        classification = classify_change(removed, added, hunk)
        changes.append({
            "added": added[:200],
            "removed": removed[:200],
            "classification": classification,
        })

    # 汇总
    l1_count = sum(1 for c in changes if c["classification"]["level"] == "L1")
    l2_count = sum(1 for c in changes if c["classification"]["level"] == "L2")
    l3_count = sum(1 for c in changes if c["classification"]["level"] == "L3")

    result = {
        "article_id": article_id,
        "child_name": child_name,
        "baseline_path": str(baseline_file),
        "visible_path": str(visible_file),
        "diff_summary": {
            "total_changes": len(changes),
            "L1_cosmetic": l1_count,
            "L2_preference": l2_count,
            "L3_structural": l3_count,
        },
        "changes": changes,
    }

    # 保存 revision 记录
    revisions_dir.mkdir(parents=True, exist_ok=True)
    rev_file = revisions_dir / f"{article_id}.json"
    rev_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Diff baseline vs visible revision")
    parser.add_argument("child_name", help="Child skill name")
    parser.add_argument("article_id", help="Article ID")
    parser.add_argument("--factory-dir", default=".claude/writing-factory/children", help="Factory base dir")
    parser.add_argument("--project-root", default=".", help="Project root directory")
    args = parser.parse_args()

    result = diff_revision(args.child_name, args.article_id, args.factory_dir, args.project_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
