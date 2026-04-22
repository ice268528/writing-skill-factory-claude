#!/usr/bin/env python3
"""
publish_child.py
将 canonical child skill 发布为 active child（同步到 .claude/skills/）。

用法:
    python publish_child.py <child_name> [--factory-dir <dir>] [--skills-dir <dir>]
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from factory_logging import LogContext, setup_logger, sanitize_child_name

logger = setup_logger("publish_child")


def publish_child(child_name: str, factory_dir: str, skills_dir: str) -> None:
    repo_dir = Path(factory_dir) / child_name / "repo"
    skill_src = repo_dir / "skill"
    state_dir = repo_dir / "state"

    if not skill_src.exists():
        logger.error("Canonical skill not found at %s", skill_src)
        sys.exit(1)

    # 读取当前版本
    release_index_path = state_dir / "release-index.json"
    version = "1.0.0"
    if release_index_path.exists():
        release_index = json.loads(release_index_path.read_text(encoding="utf-8"))
        version = release_index.get("active_version", "1.0.0")

    # 目标目录
    dest_dir = Path(skills_dir) / f"writer-{child_name}"

    # 清理旧版本（保留目录）
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    # 同步文件（同步前更新 SKILL.md 中的版本号）
    skill_md_src = skill_src / "SKILL.md"
    if skill_md_src.exists():
        content = skill_md_src.read_text(encoding="utf-8")
        # 更新 frontmatter 中的版本声明（简单替换）
        content = re.sub(
            r"> 当前版本：\d+\.\d+\.\d+",
            f"> 当前版本：{version}",
            content,
        )
        skill_md_src.write_text(content, encoding="utf-8")

    for item in skill_src.rglob("*"):
        if item.is_file():
            rel = item.relative_to(skill_src)
            dest_file = dest_dir / rel
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest_file)

    # 记录发布日志
    log_entry = {
        "event": "publish",
        "child_name": child_name,
        "version": version,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "source": str(skill_src),
        "destination": str(dest_dir),
    }
    log_path = state_dir / "learning-log.jsonl"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    # 追加 change-log
    changelog_path = repo_dir / "reports" / "change-log.md"
    if changelog_path.exists():
        log_entry = (
            f"\n## {version} ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')})\n\n"
            f"- **Type:** release\n"
            f"- **Status:** published to active skills\n"
            f"- **Destination:** `{dest_dir}`\n"
        )
        existing = changelog_path.read_text(encoding="utf-8")
        changelog_path.write_text(existing + log_entry, encoding="utf-8")

    logger.info("Published writer-%s v%s to %s", child_name, version, dest_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish a child skill to active skills dir")
    parser.add_argument("child_name", help="Child skill name")
    parser.add_argument("--factory-dir", default=".claude/writing-factory/children", help="Factory base dir")
    parser.add_argument("--skills-dir", default=".claude/skills", help="Claude skills dir")
    args = parser.parse_args()
    args.child_name = sanitize_child_name(args.child_name)

    with LogContext(logger, child_name=args.child_name, step="publish"):
        try:
            publish_child(args.child_name, args.factory_dir, args.skills_dir)
        except Exception as e:
            logger.exception("Publish failed for %s: %s", args.child_name, e)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
