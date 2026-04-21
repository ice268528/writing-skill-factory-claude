#!/usr/bin/env python3
"""
rollback_child.py
从 release 恢复并重新发布 active child。

用法:
    python rollback_child.py <child_name> <version> [--factory-dir <dir>] [--skills-dir <dir>]
"""

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def rollback_child(child_name: str, version: str, factory_dir: str, skills_dir: str) -> dict:
    repo_dir = Path(factory_dir) / child_name / "repo"
    state_dir = repo_dir / "state"

    if not repo_dir.exists():
        return {"status": "error", "message": f"Repo not found for {child_name}"}

    tag = f"v{version}"

    # 检出指定 tag
    try:
        subprocess.run(
            ["git", "checkout", tag, "--", "."],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        return {"status": "error", "message": f"Failed to checkout {tag}: {e.stderr.decode() if e.stderr else str(e)}"}

    # 更新 active_version
    release_index_path = state_dir / "release-index.json"
    if release_index_path.exists():
        release_index = json.loads(release_index_path.read_text(encoding="utf-8"))
        release_index["active_version"] = version
        release_index_path.write_text(json.dumps(release_index, ensure_ascii=False, indent=2), encoding="utf-8")

    # 重新发布
    skill_src = repo_dir / "skill"
    dest_dir = Path(skills_dir) / f"writer-{child_name}"

    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    for item in skill_src.rglob("*"):
        if item.is_file():
            rel = item.relative_to(skill_src)
            dest_file = dest_dir / rel
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest_file)

    # 追加 change-log
    changelog_path = repo_dir / "reports" / "change-log.md"
    if changelog_path.exists():
        log_entry = (
            f"\n## {version} ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')})\n\n"
            f"- **Type:** rollback\n"
            f"- **Rolled back to:** `{tag}`\n"
            f"- **Destination:** `{dest_dir}`\n"
        )
        existing = changelog_path.read_text(encoding="utf-8")
        changelog_path.write_text(existing + log_entry, encoding="utf-8")

    # 记录日志
    log_path = state_dir / "learning-log.jsonl"
    log_entry = {
        "event": "rollback",
        "child_name": child_name,
        "version": version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    return {
        "status": "rolled_back",
        "child_name": child_name,
        "version": version,
        "published_to": str(dest_dir),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Rollback a child skill to a specific version")
    parser.add_argument("child_name", help="Child skill name")
    parser.add_argument("version", help="Version to rollback to (e.g., 1.0.0)")
    parser.add_argument("--factory-dir", default=".claude/writing-factory/children", help="Factory base dir")
    parser.add_argument("--skills-dir", default=".claude/skills", help="Claude skills dir")
    args = parser.parse_args()

    result = rollback_child(args.child_name, args.version, args.factory_dir, args.skills_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
