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


def _is_punctuation_only(old_text: str, new_text: str) -> bool:
    """检测是否仅标点/空格/换行变化"""
    # 移除所有标点和空白后比较
    punct_pattern = r"[\s\n\r\t　、。！？，；：\"\"''（）【】《》…—–—~\-,.!?;:'\"()\\[\\]]"
    stripped_old = re.sub(punct_pattern, "", old_text)
    stripped_new = re.sub(punct_pattern, "", new_text)
    return stripped_old == stripped_new


def _is_particle_only(old_text: str, new_text: str) -> bool:
    """检测是否仅语气词/助词增删（如 了/的/呢/吧/啊）"""
    particles = set("的了呢吧啊嘛哦呀呗")  # 常见语气助词
    old_chars = set(old_text)
    new_chars = set(new_text)
    diff = old_chars.symmetric_difference(new_chars)
    if not diff:
        return False
    return all(c in particles for c in diff)


def _detect_paragraph_function(text: str) -> str:
    """通过首句关键词识别段落功能"""
    first_line = text.strip().split("\n")[0].strip()
    # 标题/小标题
    if re.match(r"^#{1,4}\s", first_line) or re.match(r"^\d+[.．、]\s*", first_line):
        return "heading"
    # 论点句（常见标志）
    if re.match(r"^(核心|本质|关键|根本|重点)在于", first_line):
        return "thesis"
    # 过渡段
    if re.match(r"^(然而|不过|但是|另一方面|与此同时|话说回来)", first_line):
        return "transition"
    # 结论段
    if re.match(r"^(总之|综上所述|一言以蔽之|说到底|归根到底|所以)", first_line):
        return "conclusion"
    # 引言/背景
    if re.match(r"^(最近|近年来|随着|在.*背景下|说到|谈起)", first_line):
        return "opening"
    return "body"


def _compute_similarity(old_text: str, new_text: str) -> float:
    """使用 SequenceMatcher 计算文本相似度"""
    return difflib.SequenceMatcher(None, old_text, new_text).ratio()


def classify_change(old_text: str, new_text: str, context: str) -> dict:
    """
    语义化分类变更类型。

    层级定义：
      L1 Cosmetic        — 标点、空格、个别助词、同义词替换，不改变语义
      L2 Reusable Preference — 句式调整、用词偏好、连接方式变化，体现可迁移风格
      L3 Structural Rule — 段落功能改变、论点增删、结构重排、开头/结尾重写
    """
    old_len = len(old_text) if old_text else 0
    new_len = len(new_text) if new_text else 0
    delta = new_len - old_len
    similarity = _compute_similarity(old_text, new_text)

    # --------------------------------------------------------------
    # L1: 表层 cosmetic（相似度极高，或仅标点/助词变化）
    # --------------------------------------------------------------
    if similarity >= 0.92:
        return {"level": "L1", "type": "cosmetic", "reason": "高相似度文本微调（相似度 {:.1%}）".format(similarity)}

    if _is_punctuation_only(old_text, new_text):
        return {"level": "L1", "type": "cosmetic", "reason": "仅标点/空格/格式调整"}

    if _is_particle_only(old_text, new_text):
        return {"level": "L1", "type": "cosmetic", "reason": "仅语气助词增删"}

    if abs(delta) < 15 and similarity >= 0.85:
        return {"level": "L1", "type": "cosmetic", "reason": "局部同义词/语序微调"}

    # --------------------------------------------------------------
    # 前置分析：段落功能
    # --------------------------------------------------------------
    old_func = _detect_paragraph_function(old_text)
    new_func = _detect_paragraph_function(new_text)

    # --------------------------------------------------------------
    # L3: 结构性变化
    # --------------------------------------------------------------
    old_paras = [p.strip() for p in old_text.split("\n\n") if p.strip()]
    new_paras = [p.strip() for p in new_text.split("\n\n") if p.strip()]

    # 段落数变化且总文本大幅变化
    if len(old_paras) != len(new_paras) and abs(delta) > old_len * 0.25:
        return {"level": "L3", "type": "structural", "reason": f"段落数量改变（{len(old_paras)}→{len(new_paras)}）且大幅改写"}

    # 段落功能改变（如论点段变过渡段、结论段被重写）
    if old_func != new_func and old_func != "body" and new_func != "body":
        return {"level": "L3", "type": "structural", "reason": f"段落功能转变（{old_func}→{new_func}）"}

    # 开头/结尾重写（对整篇文章影响大）
    if old_func in ("opening", "conclusion") or new_func in ("opening", "conclusion"):
        if similarity < 0.6:
            return {"level": "L3", "type": "structural", "reason": f"{'开头' if old_func == 'opening' or new_func == 'opening' else '结尾'}重写"}

    # 大幅删改（超过原长度 35%）
    if old_len > 0 and abs(delta) > old_len * 0.35:
        return {"level": "L3", "type": "structural", "reason": "大幅删改（变化 {:.0%}）".format(abs(delta) / old_len)}

    # 标题/小标题变更
    if old_func == "heading" or new_func == "heading":
        return {"level": "L3", "type": "structural", "reason": "标题层级或内容变更"}

    # --------------------------------------------------------------
    # L2: 可复用偏好（句式、用词、连接方式）
    # --------------------------------------------------------------
    # 中等规模改写，但保留了段落功能
    if 0.5 <= similarity < 0.85:
        return {"level": "L2", "type": "reusable_preference", "reason": f"句式/用词偏好调整（相似度 {similarity:.1%}），保留段落功能 {old_func}"}

    # 长度变化适中（10%~35%），段落结构不变
    if old_len > 0 and 0.10 <= abs(delta) / old_len < 0.35 and len(old_paras) == len(new_paras):
        return {"level": "L2", "type": "reusable_preference", "reason": "中等规模改写，段落结构保留"}

    # 句子拆分/合并（段落数不变但内部句数变化明显）
    old_sents = re.split(r"[。！？\n]", old_text)
    new_sents = re.split(r"[。！？\n]", new_text)
    if len(old_sents) != len(new_sents) and len(old_paras) == len(new_paras):
        return {"level": "L2", "type": "reusable_preference", "reason": f"句子拆分/合并（{len(old_sents)}→{len(new_sents)} 句），段落数不变"}

    # --------------------------------------------------------------
    # Fallback
    # --------------------------------------------------------------
    if similarity >= 0.85:
        return {"level": "L1", "type": "cosmetic", "reason": f"微调 fallback（相似度 {similarity:.1%}）"}
    return {"level": "L2", "type": "reusable_preference", "reason": "一般性文本调整 fallback"}


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
