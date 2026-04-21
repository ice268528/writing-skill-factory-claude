#!/usr/bin/env python3
"""
sync_visible_edits.py
同步可见目录与 baseline 的映射关系。

用法:
    python sync_visible_edits.py <child_name> [--factory-dir <dir>] [--project-root <dir>]
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from factory_logging import setup_logger, LogContext


def compute_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def extract_article_id(content: str) -> str | None:
    m = re.search(r'article_id:\s*(\S+)', content)
    return m.group(1) if m else None


def sync_visible_edits(child_name: str, factory_dir: str, project_root: str) -> dict:
    logger = setup_logger(__name__, child_name=child_name)
    root = Path(project_root).resolve()
    articles_dir = root / f"{child_name}_Generated_Articles"
    manifest_dir = articles_dir / ".manifest"

    repo_dir = Path(factory_dir) / child_name / "repo"
    state_dir = repo_dir / "state"
    baselines_dir = state_dir / "baselines"
    manifests_dir = state_dir / "manifests"

    if not articles_dir.exists():
        return {"status": "no_visible_dir", "changes": []}

    changes = []

    # 扫描 visible 目录中的 .md 文件
    visible_files = {f for f in articles_dir.glob("*.md") if f.name != ".manifest"}
    known_manifests = {f.stem: f for f in manifest_dir.glob("*.json")} if manifest_dir.exists() else {}

    # 检查删除：manifest 存在但 visible 文件不存在
    for article_id, manifest_file in known_manifests.items():
        visible_file = articles_dir / f"{article_id}__*.md"
        matches = list(articles_dir.glob(f"{article_id}__*.md"))
        if not matches:
            # 用户删除了 visible 稿
            changes.append({"action": "delete", "article_id": article_id})
            # 删除内部 baseline
            baseline_file = baselines_dir / f"{article_id}.md"
            if baseline_file.exists():
                baseline_file.unlink()
            manifest_file.unlink()
            state_manifest = manifests_dir / f"{article_id}.json"
            if state_manifest.exists():
                state_manifest.unlink()

    # 检查新增/修改
    for vf in visible_files:
        content = vf.read_text(encoding="utf-8")
        article_id = extract_article_id(content)
        if not article_id:
            # manifest 丢失，尝试 hash + 文首片段匹配
            # 简单处理：如果文件名含日期格式，尝试提取
            article_id = vf.stem.split("__")[0]

        state_manifest = manifests_dir / f"{article_id}.json"
        if not state_manifest.exists():
            # 新增 visible 稿
            changes.append({"action": "add", "article_id": article_id, "file": str(vf.name)})
            # 创建对应的 manifest
            now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
            manifest = {
                "article_id": article_id,
                "child_name": f"writer-{child_name}",
                "child_version": "unknown",
                "baseline_sha": "",
                "created_at": now,
                "topic": vf.stem.split("__")[-1] if "__" in vf.stem else "unknown",
                "status": "user_added",
                "visible_path": str(vf.relative_to(root)),
            }
            manifest_dir.mkdir(parents=True, exist_ok=True)
            (manifest_dir / f"{article_id}.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            state_manifest.parent.mkdir(parents=True, exist_ok=True)
            state_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            # 检查是否修改
            manifest = json.loads(state_manifest.read_text(encoding="utf-8"))
            current_sha = compute_sha(content)
            if manifest.get("current_sha") and manifest["current_sha"] != current_sha:
                changes.append({"action": "edit", "article_id": article_id, "file": str(vf.name)})
            manifest["current_sha"] = current_sha
            state_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"status": "synced", "changes": changes}


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync visible edits with canonical repo")
    parser.add_argument("child_name", help="Child skill name")
    parser.add_argument("--factory-dir", default=".claude/writing-factory/children", help="Factory base dir")
    parser.add_argument("--project-root", default=".", help="Project root directory")
    args = parser.parse_args()

    result = sync_visible_edits(args.child_name, args.factory_dir, args.project_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
