#!/usr/bin/env python3
"""
promote_rules.py
把 revision signals 提升为 candidate / probation / active 规则。

用法:
    python promote_rules.py <child_name> <article_id> [--factory-dir <dir>]
"""

import argparse
import difflib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from factory_logging import setup_logger, LogContext, sanitize_child_name


def _description_similarity(desc1: str, desc2: str) -> float:
    """计算两条规则描述的编辑相似度（SequenceMatcher ratio）。"""
    if desc1 == desc2:
        return 1.0
    return difflib.SequenceMatcher(None, desc1, desc2).ratio()


# 去重相似度阈值：只有相似度 >= 0.85 才视为同一规则
_DEDUP_SIMILARITY_THRESHOLD = 0.85


def _abstract_rule_description(level: str, rule_type: str, removed: str, added: str, reason: str) -> str:
    """
    对变更内容进行语义抽象，生成可复用的规则描述。
    """
    import re

    # 辅助：统计句子数
    def count_sentences(text: str) -> int:
        return len([s for s in re.split(r"[。！？]", text) if s.strip()])

    removed_sents = count_sentences(removed)
    added_sents = count_sentences(added)

    # ----------------------------------------------------------
    # L3 Structural — 结构级规则
    # ----------------------------------------------------------
    if level == "L3":
        if "开头" in reason or "opening" in reason:
            return "文章开头应更直接/更有钩子，避免模板化引入"
        if "结尾" in reason or "conclusion" in reason:
            return "结尾应避免总结式收束，改用留白或反转"
        if "标题" in reason or "heading" in reason:
            return "标题层级或小标题表述需调整以匹配作者习惯"
        if "段落功能" in reason:
            return "段落功能定位需调整（如过渡段→论证段）"
        if "段落数量" in reason:
            return "段落数量与密度需重新分配"
        if "大幅删改" in reason:
            return "某段内容需大幅重构或删减"
        return f"结构性调整：{reason}"

    # ----------------------------------------------------------
    # L2 Reusable Preference — 可复用风格偏好
    # ----------------------------------------------------------
    if level == "L2":
        # 句式拆分/合并
        if "拆分" in reason or "合并" in reason:
            if added_sents > removed_sents:
                return "偏好将长句拆分为短句，提升节奏感"
            return "偏好将短句合并为长句，增强密度"

        # 连接词/过渡方式
        connectors_old = set(re.findall(r"因此|所以|于是|从而|不过|但是|然而|另一方面|与此同时", removed))
        connectors_new = set(re.findall(r"因此|所以|于是|从而|不过|但是|然而|另一方面|与此同时", added))
        if connectors_old != connectors_new:
            return f"偏好使用特定逻辑连接方式（如：{','.join(list(connectors_new)[:2])}）"

        # 具体化 vs 抽象化
        if len(added) > len(removed) * 1.3 and added_sents >= removed_sents:
            return "偏好更具体的描述与细节展开"
        if len(removed) > len(added) * 1.3 and added_sents <= removed_sents:
            return "偏好更简洁/抽象的表述"

        # 人称/视角变化
        if re.search(r"我|我们", removed) and not re.search(r"我|我们", added):
            return "避免使用第一人称，保持客观或第三人称视角"
        if re.search(r"你|你们", removed) and not re.search(r"你|你们", added):
            return "避免直接称呼读者，改用间接引导"

        # AI 套路词检测（用户删除 AI 味词汇）
        ai_cliches_removed = set(re.findall(
            r"值得注意的是|不可否认的是|让我们|深入探讨|不言而喻|\b众所周知\b|\b显而易见\b",
            removed,
        ))
        ai_cliches_added = set(re.findall(
            r"值得注意的是|不可否认的是|让我们|深入探讨|不言而喻|\b众所周知\b|\b显而易见\b",
            added,
        ))
        if ai_cliches_removed and not ai_cliches_added:
            return f"避免 AI 套路表达（如：{','.join(list(ai_cliches_removed)[:2])}）"
        if ai_cliches_added and not ai_cliches_removed:
            return f"可使用特定表达（但需控制频率）：{','.join(list(ai_cliches_added)[:2])}"

        # 默认：提取变更的核心差异作为描述
        return f"风格偏好：{reason}（从样文修改中归纳）"

    # Fallback
    return reason if reason else "未分类的文本调整"


def promote_rules(child_name: str, article_id: str, factory_dir: str) -> dict:
    logger = setup_logger(__name__, child_name=child_name)
    repo_dir = Path(factory_dir) / child_name / "repo"
    state_dir = repo_dir / "state"
    revisions_dir = state_dir / "revisions"
    skill_dir = repo_dir / "skill"
    memory_path = skill_dir / "assets" / "style-memory.json"

    rev_file = revisions_dir / f"{article_id}.json"
    if not rev_file.exists():
        return {"status": "error", "message": f"Revision not found for {article_id}"}

    revision = json.loads(rev_file.read_text(encoding="utf-8"))

    if memory_path.exists():
        memory = json.loads(memory_path.read_text(encoding="utf-8"))
    else:
        memory = {
            "voice_traits": [],
            "punctuation_preferences": [],
            "paragraph_formulas": [],
            "narrative_moves": [],
            "editorial_heuristics": [],
            "author_boundary_rules": [],
            "anti_patterns": [],
            "confidence_buckets": {"candidate": [], "probation": [], "active": []}
        }

    promoted = []

    for change in revision.get("changes", []):
        level = change["classification"]["level"]
        if level == "L1":
            continue  # L1 不进入长期记忆

        rule_type = change["classification"]["type"]
        added = change.get("added", "")
        removed = change.get("removed", "")
        reason = change["classification"].get("reason", "")

        # 语义抽象：根据 level 和变更内容生成有意义的规则描述
        desc = _abstract_rule_description(level, rule_type, removed, added, reason)
        rule_id = f"{rule_type}-{article_id}-{len(promoted)+1:03d}"

        # 查找是否已有同类规则（严格去重：rule_type 相同且描述完全相等或高度相似）
        existing = None
        for bucket in ["active", "probation", "candidate"]:
            for r in memory["confidence_buckets"].get(bucket, []):
                if r.get("rule_type") == rule_type:
                    if r.get("description") == desc or _description_similarity(r.get("description", ""), desc) >= _DEDUP_SIMILARITY_THRESHOLD:
                        existing = r
                        break
            if existing:
                break

        if existing:
            existing["evidence_count"] = existing.get("evidence_count", 0) + 1
            source_articles = set(existing.get("source_articles", []))
            source_articles.add(article_id)
            existing["source_articles"] = list(source_articles)
            # 升级逻辑
            # candidate -> probation：evidence_count >= 2（可在同一 article_id 内发生）
            if existing["confidence"] == "candidate" and existing["evidence_count"] >= 2:
                existing["confidence"] = "probation"
                memory["confidence_buckets"]["candidate"].remove(existing)
                memory["confidence_buckets"]["probation"].append(existing)
                promoted.append({"rule_id": existing["rule_id"], "new_confidence": "probation"})
            # probation -> active：必须 evidence_count >= 3 且来自至少 2 个不同 article_id
            elif existing["confidence"] == "probation" and existing["evidence_count"] >= 3 and len(existing["source_articles"]) >= 2:
                existing["confidence"] = "active"
                memory["confidence_buckets"]["probation"].remove(existing)
                memory["confidence_buckets"]["active"].append(existing)
                promoted.append({"rule_id": existing["rule_id"], "new_confidence": "active"})
        else:
            new_rule = {
                "rule_id": rule_id,
                "rule_type": rule_type,
                "description": desc,
                "evidence_count": 1,
                "confidence": "candidate",
                "source_articles": [article_id],
                "transferability": "medium",
                "boundary_note": f"从 {article_id} 的修改中提取"
            }
            memory["confidence_buckets"]["candidate"].append(new_rule)
            promoted.append({"rule_id": rule_id, "new_confidence": "candidate"})

    memory_path.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")

    # 自动扩充 anti-patterns.md（从 revision 中提取 AI 套路词）
    _update_anti_patterns_from_revision(skill_dir, revision)

    # 记录日志
    log_path = state_dir / "learning-log.jsonl"
    log_entry = {
        "event": "promote_rules",
        "child_name": child_name,
        "article_id": article_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "promoted_count": len(promoted),
        "promoted": promoted,
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    return {"status": "promoted", "promoted": promoted}


# AI 套路句型模板库：(正则模式, 模板描述)
# 正则使用非贪婪匹配 .*? 以适配具体变体
AI_PATTERN_TEMPLATES = [
    # 社会背景型
    (r"在当今社会[，,].*?[。！？]", "在当今社会，...（社会背景引入）"),
    (r"随着.*?的?发展[，,].*?[。！？]", "随着...的发展，...（趋势引入）"),
    (r"在.*?的背景下[，,].*?[。！？]", "在...的背景下，...（背景铺垫）"),
    # 思考引导型
    (r"这是一个值得深思的问题[。，,]?", "这是一个值得深思的问题。（强行升华）"),
    (r"这?不得不让人思考.*?[。！？]", "这不得不让人思考...（强行升华）"),
    (r"从某种程度上说[，,].*?[。！？]", "从某种程度上说，...（模糊表态）"),
    # 全面性伪装型
    (r"无论是.*?还是.*?[，,].*?[。！？]", "无论是A还是B，...（虚假全面）"),
    (r".*?的背后[，,]是.*?[。！？]", "...的背后，是...（过度归因）"),
    # 总结收束型
    (r"总而言之[，,].*?[。！？]", "总而言之，...（模板化总结）"),
    (r"综上所述[，,].*?[。！？]", "综上所述，...（模板化总结）"),
    (r"不仅如此[，,].*?[。！？]", "不仅如此，...（递进模板）"),
    # 号召型
    (r"让我们一起.*?[吧!！。]", "让我们一起...（空洞号召）"),
    (r"相信未来.*?[吧!！。]", "相信未来...（空洞号召）"),
    # 断言型
    (r"毫无疑问[，,].*?[。！？]", "毫无疑问，...（绝对化断言）"),
    (r"不可否认的是[，,].*?[。！？]", "不可否认的是，...（绝对化断言）"),
    (r"众所周知[，,].*?[。！？]", "众所周知，...（预设共识）"),
    (r"显而易见[，,].*?[。！？]", "显而易见，...（预设共识）"),
    # 探讨型
    (r"让我们深入探讨.*?[。！？]", "让我们深入探讨...（AI自导自演）"),
    (r"值得注意的是[，,].*?[。！？]", "值得注意的是，...（AI旁观视角）"),
    # 伪金句型
    (r"这[,，]就是.*?[。！？]", "这，就是...（伪金句）"),
]


def _extract_ai_cliches(removed: str, added: str) -> set[str]:
    """提取用户删除且未保留的 AI 套路词汇。"""
    ai_pattern = re.compile(
        r"值得注意的是|不可否认的是|让我们|深入探讨|不言而喻|众所周知|显而易见|"
        r"在当今社会|随着科技的发展|这是一个值得深思的问题|不仅如此|总而言之|综上所述|"
        r"让我们一起|相信未来|毫无疑问"
    )
    matches = ai_pattern.findall(removed)
    return {m for m in matches if m not in added}


def _extract_ai_patterns(removed: str, added: str) -> set[str]:
    """提取用户删除且未保留的 AI 套路句型（返回模板描述集合）。"""
    found: set[str] = set()
    for regex, desc in AI_PATTERN_TEMPLATES:
        for match in re.findall(regex, removed):
            # 确认修改后的文本中不存在该匹配的具体实例
            if match not in added:
                found.add(desc)
    return found


def _update_anti_patterns_from_revision(skill_dir: Path, revision: dict) -> None:
    """
    扫描 revision 中的 changes，提取用户删除的 AI 套路词和句型，追加到 anti-patterns.md。
    避免重复添加。
    """
    anti_patterns_path = skill_dir / "references" / "anti-patterns.md"
    if not anti_patterns_path.exists():
        return

    existing_content = anti_patterns_path.read_text(encoding="utf-8")

    # ------------------------------------------------------------------
    # 1) 提取单个词汇
    # ------------------------------------------------------------------
    new_cliches: set[str] = set()
    for change in revision.get("changes", []):
        removed = change.get("removed", "")
        added = change.get("added", "")
        new_cliches |= _extract_ai_cliches(removed, added)

    to_add_cliches = [c for c in sorted(new_cliches) if c not in existing_content]

    # ------------------------------------------------------------------
    # 2) 提取句型模式
    # ------------------------------------------------------------------
    new_patterns: set[str] = set()
    for change in revision.get("changes", []):
        removed = change.get("removed", "")
        added = change.get("added", "")
        new_patterns |= _extract_ai_patterns(removed, added)

    to_add_patterns = [p for p in sorted(new_patterns) if p not in existing_content]

    if not to_add_cliches and not to_add_patterns:
        return

    lines = existing_content.splitlines()

    # ------------------------------------------------------------------
    # 3) 词汇追加到 "高频 AI 味" 区块末尾
    # ------------------------------------------------------------------
    if to_add_cliches:
        cliché_insert_idx = len(lines)
        for i, line in enumerate(lines):
            if "常见套路句" in line or "不允许伪造" in line:
                cliché_insert_idx = i
                break
        cliché_lines = [f"- {c}" for c in to_add_cliches]
        lines = lines[:cliché_insert_idx] + [""] + cliché_lines + lines[cliché_insert_idx:]

    # ------------------------------------------------------------------
    # 4) 句型追加到 "常见套路句" 区块末尾
    # ------------------------------------------------------------------
    if to_add_patterns:
        # 重新定位（因为上面可能已插入内容）
        pattern_start_idx = None
        pattern_end_idx = len(lines)
        for i, line in enumerate(lines):
            if "常见套路句" in line:
                pattern_start_idx = i
            elif pattern_start_idx is not None and line.startswith("## ") and "常见套路句" not in line:
                pattern_end_idx = i
                break

        if pattern_start_idx is not None:
            pattern_lines = [f"- \"{p}\"" for p in to_add_patterns]
            lines = lines[:pattern_end_idx] + [""] + pattern_lines + lines[pattern_end_idx:]
        else:
            # 如果文档中没有"常见套路句"区块，在末尾创建
            pattern_lines = [
                "",
                "## 常见套路句",
                "",
            ] + [f"- \"{p}\"" for p in to_add_patterns]
            lines.extend(pattern_lines)

    anti_patterns_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote revision signals to rules")
    parser.add_argument("child_name", help="Child skill name")
    parser.add_argument("article_id", help="Article ID")
    parser.add_argument("--factory-dir", default=".claude/writing-factory/children", help="Factory base dir")
    args = parser.parse_args()
    args.child_name = sanitize_child_name(args.child_name)

    result = promote_rules(args.child_name, args.article_id, args.factory_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
