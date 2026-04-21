#!/usr/bin/env python3
"""
generate_article.py
调用 active child 写稿并执行双写（baseline + visible draft）。

用法:
    python generate_article.py <child_name> <topic> [--factory-dir <dir>] [--project-root <dir>]

注意：本脚本不直接生成文章内容，而是准备文件结构并记录元数据。
实际文章生成由 Claude Code 调用 active child skill 完成。
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def generate_article_id() -> str:
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    # 序号通过扫描现有文件确定
    return f"{date_str}"


def get_next_sequence(articles_dir: Path, date_str: str) -> int:
    if not articles_dir.exists():
        return 1
    existing = [f.name for f in articles_dir.glob(f"{date_str}-*")]
    if not existing:
        return 1
    seqs = []
    for name in existing:
        parts = name.split("__")
        if len(parts) > 0:
            prefix = parts[0]
            try:
                seq = int(prefix.split("-")[-1])
                seqs.append(seq)
            except ValueError:
                pass
    return max(seqs, default=0) + 1


def compute_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def sanitize_topic(topic: str) -> str:
    return re.sub(r'[^\w\u4e00-\u9fff\-]', "-", topic)[:40].strip("-")


def generate_article(child_name: str, topic: str, factory_dir: str, project_root: str) -> dict:
    import re

    root = Path(project_root).resolve()
    repo_dir = Path(factory_dir).resolve() / child_name / "repo"
    skill_dir = repo_dir / "skill"
    state_dir = repo_dir / "state"
    baselines_dir = state_dir / "baselines"
    manifests_dir = state_dir / "manifests"

    articles_dir = root / f"{child_name}_Generated_Articles"
    manifest_dir = articles_dir / ".manifest"

    # 确保目录
    for d in [baselines_dir, manifests_dir, articles_dir, manifest_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # 生成 article_id
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    seq = get_next_sequence(articles_dir, date_str)
    article_id = f"{date_str}-{seq:03d}"
    topic_slug = sanitize_topic(topic)

    # 读取当前版本
    release_index_path = state_dir / "release-index.json"
    version = "1.0.0"
    if release_index_path.exists():
        release_index = json.loads(release_index_path.read_text(encoding="utf-8"))
        version = release_index.get("active_version", "1.0.0")

    # 准备 baseline（由 Claude 后续填充内容）
    baseline_content = f"""---
article_id: {article_id}
child_name: writer-{child_name}
child_version: {version}
status: drafted
topic: {topic}
---

# {topic}

[此 baseline 由 writer-{child_name} skill 生成，待填充内容]

"""
    baseline_sha = compute_sha(baseline_content)
    baseline_path = baselines_dir / f"{article_id}.md"
    baseline_path.write_text(baseline_content, encoding="utf-8")

    # 准备 visible draft
    visible_content = f"""---
article_id: {article_id}
child_name: writer-{child_name}
child_version: {version}
baseline_sha: {baseline_sha}
created_at: {now.isoformat()}
topic: {topic}
status: drafted
---

# {topic}

[此稿件由 writer-{child_name} skill 生成，用户可在此编辑]

"""
    visible_path = articles_dir / f"{article_id}__{topic_slug}.md"
    visible_path.write_text(visible_content, encoding="utf-8")

    # 生成 manifest
    manifest = {
        "article_id": article_id,
        "child_name": f"writer-{child_name}",
        "child_version": version,
        "baseline_sha": baseline_sha,
        "created_at": now.isoformat(),
        "topic": topic,
        "status": "drafted",
        "baseline_path": str(baseline_path.relative_to(root)),
        "visible_path": str(visible_path.relative_to(root)),
    }
    manifest_path = manifest_dir / f"{article_id}.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # 同时保存到 state/manifests
    state_manifest_path = manifests_dir / f"{article_id}.json"
    state_manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[generate_article] Article structure prepared: {article_id}")
    print(f"[generate_article] Baseline: {baseline_path}")
    print(f"[generate_article] Visible:  {visible_path}")

    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate article structure with dual-write")
    parser.add_argument("child_name", help="Child skill name")
    parser.add_argument("topic", help="Article topic or brief")
    parser.add_argument("--factory-dir", default=".claude/writing-factory/children", help="Factory base dir")
    parser.add_argument("--project-root", default=".", help="Project root directory")
    args = parser.parse_args()

    manifest = generate_article(args.child_name, args.topic, args.factory_dir, args.project_root)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
