#!/usr/bin/env python3
"""
promote_rules.py
把 revision signals 提升为 candidate / probation / active 规则。

用法:
    python promote_rules.py <child_name> <article_id> [--factory-dir <dir>]
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def promote_rules(child_name: str, article_id: str, factory_dir: str) -> dict:
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

        # 生成规则描述（简化版）
        desc = f"用户将 '{removed[:40]}...' 改为 '{added[:40]}...'"
        rule_id = f"{rule_type}-{article_id}-{len(promoted)+1:03d}"

        # 查找是否已有同类规则
        existing = None
        for bucket in ["active", "probation", "candidate"]:
            for r in memory["confidence_buckets"].get(bucket, []):
                if r.get("description") == desc or r.get("rule_type") == rule_type and desc[:20] in r.get("description", ""):
                    existing = r
                    break
            if existing:
                break

        if existing:
            existing["evidence_count"] = existing.get("evidence_count", 0) + 1
            existing["source_articles"] = list(set(existing.get("source_articles", []) + [article_id]))
            # 升级
            if existing["confidence"] == "candidate" and existing["evidence_count"] >= 2:
                existing["confidence"] = "probation"
                memory["confidence_buckets"]["candidate"].remove(existing)
                memory["confidence_buckets"]["probation"].append(existing)
                promoted.append({"rule_id": existing["rule_id"], "new_confidence": "probation"})
            elif existing["confidence"] == "probation" and existing["evidence_count"] >= 3:
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote revision signals to rules")
    parser.add_argument("child_name", help="Child skill name")
    parser.add_argument("article_id", help="Article ID")
    parser.add_argument("--factory-dir", default=".claude/writing-factory/children", help="Factory base dir")
    args = parser.parse_args()

    result = promote_rules(args.child_name, args.article_id, args.factory_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
