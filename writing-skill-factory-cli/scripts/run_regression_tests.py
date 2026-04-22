#!/usr/bin/env python3
"""
run_regression_tests.py
自动化回归测试运行器。

覆盖场景:
    1. structure_integrity   — child skill 必要文件存在性
    2. style_memory_schema   — style-memory.json 关键字段与类型
    3. rules_validity        — 规则对象字段完整性
    4. diff_classification   — classify_change 对已知输入的分类准确性
    5. promote_dedup         — promote_rules 对重复规则的处理
    6. eval_score_range      — eval_candidate 输出分数在 0-5 区间
    7. pipeline_dry_run      — learn_pipeline --dry-run 不报错
    8. manifest_integrity    — manifest 指向的 baseline/article 存在

用法:
    python run_regression_tests.py <child_name> [--factory-dir <dir>] [--project-root <dir>]
"""

import argparse
import importlib.util
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from factory_logging import LogContext, setup_logger, sanitize_child_name

logger = setup_logger("run_regression_tests")

SCRIPT_DIR = Path(__file__).parent.resolve()


def _import_module(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------------
# 测试用例
# ------------------------------------------------------------------

def test_structure_integrity(child_name: str, factory_dir: str) -> dict:
    """测试 child skill 目录结构完整。"""
    skill_dir = Path(factory_dir) / child_name / "repo" / "skill"
    required = [
        "SKILL.md",
        "references/style-profile.md",
        "references/editorial-rules.md",
        "references/author-boundary.md",
        "references/anti-patterns.md",
        "references/examples.md",
        "assets/style-memory.json",
        "assets/quality-rubric.json",
        "evals/evals.json",
    ]
    missing = [f for f in required if not (skill_dir / f).exists()]
    return {"name": "structure_integrity", "passed": not missing, "missing": missing}


def test_style_memory_schema(child_name: str, factory_dir: str) -> dict:
    """测试 style-memory.json 包含必要顶层键。"""
    memory_path = Path(factory_dir) / child_name / "repo" / "skill" / "assets" / "style-memory.json"
    if not memory_path.exists():
        return {"name": "style_memory_schema", "passed": False, "error": "file missing"}
    try:
        data = json.loads(memory_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {"name": "style_memory_schema", "passed": False, "error": f"invalid json: {e}"}

    required_keys = [
        "voice_traits",
        "punctuation_preferences",
        "paragraph_formulas",
        "narrative_moves",
        "editorial_heuristics",
        "author_boundary_rules",
        "anti_patterns",
        "confidence_buckets",
    ]
    missing = [k for k in required_keys if k not in data]
    # confidence_buckets 必须有三个子键
    buckets = data.get("confidence_buckets", {})
    bucket_ok = set(buckets.keys()) >= {"candidate", "probation", "active"}
    return {
        "name": "style_memory_schema",
        "passed": not missing and bucket_ok,
        "missing_keys": missing,
        "bucket_keys": list(buckets.keys()),
    }


def test_rules_validity(child_name: str, factory_dir: str) -> dict:
    """测试所有规则条目具备最小必要字段。"""
    memory_path = Path(factory_dir) / child_name / "repo" / "skill" / "assets" / "style-memory.json"
    if not memory_path.exists():
        return {"name": "rules_validity", "passed": False, "error": "file missing"}
    data = json.loads(memory_path.read_text(encoding="utf-8"))
    buckets = data.get("confidence_buckets", {})
    invalid = []
    for bucket_name, rules in buckets.items():
        for idx, r in enumerate(rules):
            if "description" not in r or not r["description"]:
                invalid.append({"bucket": bucket_name, "index": idx, "issue": "missing description"})
            if "confidence" not in r:
                invalid.append({"bucket": bucket_name, "index": idx, "issue": "missing confidence"})
    return {"name": "rules_validity", "passed": not invalid, "invalid_rules": invalid}


def test_diff_classification() -> dict:
    """用已知输入验证 classify_change 的分级逻辑。"""
    diff_mod = _import_module("diff_revision")
    cases = [
        # (old, new, expected_level, context_hint)
        ("你好，世界。", "你好世界。", "L1", "punctuation_only"),
        ("这是一个的句子。", "这是一个句子。", "L1", "particle_only"),
        ("A" * 100, "A" * 101, "L1", "high_similarity"),
        ("核心在于A。\n\n因此B。", "核心在于A。\n\n然而B。", "L2", "thesis_keep_connector_change"),
        ("总之，很好。", "最后，很好。", "L2", "conclusion_similar_rewrite"),
        ("# 标题\n\n正文。", "## 新标题\n\n正文。", "L3", "heading_change"),
        ("最近，发生了X。", "很久以前，发生了Y。\n\n而且Z。", "L3", "opening_rewrite_and_expand"),
    ]
    passed = 0
    failed = []
    for old, new, expected, hint in cases:
        result = diff_mod.classify_change(old, new, "")
        level = result.get("level")
        if level == expected:
            passed += 1
        else:
            failed.append({
                "hint": hint,
                "expected": expected,
                "actual": level,
                "reason": result.get("reason"),
            })
    return {
        "name": "diff_classification",
        "passed": not failed,
        "summary": f"{passed}/{len(cases)} passed",
        "failed": failed,
    }


def test_promote_dedup() -> dict:
    """验证 promote_rules 对重复 description 的累加逻辑，且不同描述不被合并。"""
    import tempfile
    promote_mod = _import_module("promote_rules")

    with tempfile.TemporaryDirectory() as tmpdir:
        factory_dir = tmpdir
        child_name = "test_dedup_child"
        article_id = "art-001"

        repo_dir = Path(factory_dir) / child_name / "repo"
        state_dir = repo_dir / "state"
        revisions_dir = state_dir / "revisions"
        skill_dir = repo_dir / "skill"
        assets_dir = skill_dir / "assets"
        for d in [revisions_dir, assets_dir, skill_dir / "references"]:
            d.mkdir(parents=True, exist_ok=True)

        memory = {
            "voice_traits": [], "punctuation_preferences": [], "paragraph_formulas": [],
            "narrative_moves": [], "editorial_heuristics": [], "author_boundary_rules": [],
            "anti_patterns": [], "confidence_buckets": {"candidate": [], "probation": [], "active": []}
        }
        (assets_dir / "style-memory.json").write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")
        (skill_dir / "references" / "anti-patterns.md").write_text("# Anti-patterns\n", encoding="utf-8")

        # 2 个相同描述的 change -> 应合并为 1 条 probation
        # 注意：added_sents > removed_sents 才会触发"拆分"描述
        revision = {
            "changes": [
                {"classification": {"level": "L2", "type": "reusable_preference", "reason": "拆分"},
                 "added": "第一句。第二句。", "removed": "这是一个很长的句子，包含很多内容。"},
                {"classification": {"level": "L2", "type": "reusable_preference", "reason": "拆分"},
                 "added": "新短句一。新短句二。", "removed": "旧长句，包含很多内容。"},
            ]
        }
        (revisions_dir / f"{article_id}.json").write_text(json.dumps(revision, ensure_ascii=False), encoding="utf-8")
        promote_mod.promote_rules(child_name, article_id, factory_dir)

        updated = json.loads((assets_dir / "style-memory.json").read_text(encoding="utf-8"))
        probations = updated["confidence_buckets"]["probation"]
        dedup_ok = len(probations) == 1 and probations[0]["evidence_count"] == 2

        # 不同描述的 change -> 不应合并
        # removed_sents > added_sents 才会触发"合并"描述
        article_id_2 = "art-002"
        revision2 = {
            "changes": [
                {"classification": {"level": "L2", "type": "reusable_preference", "reason": "合并"},
                 "added": "合并后的长句。", "removed": "短句一。短句二。"},
            ]
        }
        (revisions_dir / f"{article_id_2}.json").write_text(json.dumps(revision2, ensure_ascii=False), encoding="utf-8")
        promote_mod.promote_rules(child_name, article_id_2, factory_dir)

        updated2 = json.loads((assets_dir / "style-memory.json").read_text(encoding="utf-8"))
        probations2 = updated2["confidence_buckets"]["probation"]
        candidates2 = updated2["confidence_buckets"]["candidate"]

        # 应有 1 条 probation（evidence=2）和 1 条 candidate（evidence=1）
        separate_ok = len(probations2) == 1 and len(candidates2) == 1

        return {
            "name": "promote_dedup",
            "passed": dedup_ok and separate_ok,
            "dedup_ok": dedup_ok,
            "separate_ok": separate_ok,
            "probation_count": len(probations2),
            "candidate_count": len(candidates2),
        }


def test_promote_cross_article_upgrade() -> dict:
    """验证同一 article_id 的 3 个同类 change 最多只能将规则升至 probation，不能跳到 active。"""
    import tempfile
    promote_mod = _import_module("promote_rules")

    with tempfile.TemporaryDirectory() as tmpdir:
        factory_dir = tmpdir
        child_name = "test_cross_child"
        article_id = "art-001"

        repo_dir = Path(factory_dir) / child_name / "repo"
        state_dir = repo_dir / "state"
        revisions_dir = state_dir / "revisions"
        skill_dir = repo_dir / "skill"
        assets_dir = skill_dir / "assets"
        for d in [revisions_dir, assets_dir, skill_dir / "references"]:
            d.mkdir(parents=True, exist_ok=True)

        desc = "偏好将长句拆分为短句，提升节奏感"
        memory = {
            "voice_traits": [], "punctuation_preferences": [], "paragraph_formulas": [],
            "narrative_moves": [], "editorial_heuristics": [], "author_boundary_rules": [],
            "anti_patterns": [], "confidence_buckets": {
                "candidate": [],
                "probation": [{"rule_id": "r1", "rule_type": "reusable_preference", "description": desc,
                               "evidence_count": 2, "confidence": "probation", "source_articles": [article_id],
                               "transferability": "medium", "boundary_note": ""}],
                "active": []
            }
        }
        (assets_dir / "style-memory.json").write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")
        (skill_dir / "references" / "anti-patterns.md").write_text("# Anti-patterns\n", encoding="utf-8")

        # 同一 article_id 再增加 1 个 evidence -> evidence_count=3
        # 必须保证 _abstract_rule_description 生成与初始规则相同的描述
        revision = {
            "changes": [
                {"classification": {"level": "L2", "type": "reusable_preference", "reason": "拆分"},
                 "added": "新短句一。新短句二。", "removed": "旧长句，包含很多内容。"},
            ]
        }
        (revisions_dir / f"{article_id}.json").write_text(json.dumps(revision, ensure_ascii=False), encoding="utf-8")
        promote_mod.promote_rules(child_name, article_id, factory_dir)

        updated = json.loads((assets_dir / "style-memory.json").read_text(encoding="utf-8"))
        probations = updated["confidence_buckets"]["probation"]
        active = updated["confidence_buckets"]["active"]

        # 必须仍为 probation，不能跳到 active
        stayed_probation = len(probations) == 1 and len(active) == 0
        evidence_count_ok = probations[0]["evidence_count"] == 3 if probations else False

        return {
            "name": "promote_cross_article_upgrade",
            "passed": stayed_probation and evidence_count_ok,
            "stayed_probation": stayed_probation,
            "evidence_count": probations[0]["evidence_count"] if probations else None,
            "source_articles": probations[0].get("source_articles") if probations else None,
        }


def test_diff_empty_text() -> dict:
    """验证 old_text=\"\" 或 new_text=\"\" 时强制返回 L3。"""
    diff_mod = _import_module("diff_revision")
    cases = [
        ("", "全新段落内容", "L3", "empty_old"),
        ("原有段落内容", "", "L3", "empty_new"),
    ]
    passed = 0
    failed = []
    for old, new, expected, hint in cases:
        result = diff_mod.classify_change(old, new, "")
        level = result.get("level")
        if level == expected:
            passed += 1
        else:
            failed.append({"hint": hint, "expected": expected, "actual": level, "reason": result.get("reason")})
    return {
        "name": "diff_empty_text",
        "passed": not failed,
        "summary": f"{passed}/{len(cases)} passed",
        "failed": failed,
    }


def test_diff_particle_frequency() -> dict:
    """验证仅字符频次变化的助词修改返回 L1（Counter 逻辑）。"""
    diff_mod = _import_module("diff_revision")
    cases = [
        # 纯助词频次变化，similarity < 0.92，必须靠 _is_particle_only 捕获
        ("的的的的的的的的", "的的的的的", "L1", "particle_frequency_decrease"),
        ("这是一个的的的句子", "这是一个的句子", "L1", "particle_in_sentence"),
    ]
    passed = 0
    failed = []
    for old, new, expected, hint in cases:
        result = diff_mod.classify_change(old, new, "")
        level = result.get("level")
        if level == expected:
            passed += 1
        else:
            failed.append({"hint": hint, "expected": expected, "actual": level, "reason": result.get("reason")})
    return {
        "name": "diff_particle_frequency",
        "passed": not failed,
        "summary": f"{passed}/{len(cases)} passed",
        "failed": failed,
    }


def test_eval_score_range(child_name: str, factory_dir: str) -> dict:
    """验证 eval_candidate 返回的分数在 0-5 之间。"""
    eval_mod = _import_module("eval_candidate")
    try:
        result = eval_mod.eval_candidate(child_name, factory_dir)
    except Exception as e:
        return {"name": "eval_score_range", "passed": False, "error": str(e)}

    scores_to_check = []
    total = result.get("total_score")
    if total is not None:
        scores_to_check.append(("total_score", total))
    struct = result.get("structure_dimension", {})
    for k, v in struct.get("scores", {}).items():
        scores_to_check.append((f"structure.{k}", v))
    effect = result.get("effect_dimension", {})
    for k, v in effect.get("scores", {}).items():
        if isinstance(v, (int, float)):
            scores_to_check.append((f"effect.{k}", v))

    out_of_range = [(name, val) for name, val in scores_to_check if not (0 <= val <= 5)]
    return {
        "name": "eval_score_range",
        "passed": not out_of_range,
        "out_of_range": out_of_range,
        "checked": len(scores_to_check),
    }


def test_eval_sensitivity() -> dict:
    """验证 eval_candidate 的 style_fit 对 voice_traits 变化具有灵敏度。"""
    eval_mod = _import_module("eval_candidate")

    base_memory = {
        "voice_traits": [
            {"trait": "sentence_length", "value": 25},
            {"trait": "formality", "value": 3},
        ],
        "punctuation_preferences": [
            {"mark": "，", "density_per_1k": 45},
        ],
        "paragraph_formulas": ["formula1"],
        "narrative_moves": ["move1"],
    }

    # 完全相同的 memory -> 应得高分
    same_memory = json.loads(json.dumps(base_memory))
    score_same = eval_mod.compute_style_fit(base_memory, same_memory)

    # 大幅修改 voice_traits -> 分数必须下降
    changed_memory = json.loads(json.dumps(base_memory))
    changed_memory["voice_traits"][0]["value"] = 80
    score_changed = eval_mod.compute_style_fit(base_memory, changed_memory)

    sensitive = score_changed < score_same

    # 删除关键字段 -> 分数必须显著下降
    incomplete_memory = json.loads(json.dumps(base_memory))
    incomplete_memory["voice_traits"] = []
    score_incomplete = eval_mod.compute_style_fit(base_memory, incomplete_memory)
    incomplete_low = score_incomplete <= 1.5

    return {
        "name": "eval_sensitivity",
        "passed": sensitive and incomplete_low,
        "sensitive": sensitive,
        "score_same": score_same,
        "score_changed": score_changed,
        "score_incomplete": score_incomplete,
    }


def test_show_status_semver() -> dict:
    """验证 show_status 使用 semver 正确排序版本号（1.10.0 > 1.2.0）。"""
    import tempfile
    status_mod = _import_module("show_status")

    with tempfile.TemporaryDirectory() as tmpdir:
        factory_dir = tmpdir
        child_name = "test_semver_child"

        repo_dir = Path(factory_dir) / child_name / "repo"
        state_dir = repo_dir / "state"
        state_dir.mkdir(parents=True, exist_ok=True)

        release_index = {
            "releases": [
                {"version": "1.0.2", "tag": "v1.0.2", "created_at": "2026-04-20T00:00:00Z"},
                {"version": "1.0.10", "tag": "v1.0.10", "created_at": "2026-04-21T00:00:00Z"},
                {"version": "1.2.0", "tag": "v1.2.0", "created_at": "2026-04-22T00:00:00Z"},
            ],
            "active_version": "1.0.10"
        }
        (state_dir / "release-index.json").write_text(json.dumps(release_index), encoding="utf-8")

        status = status_mod.show_status(child_name, factory_dir)
        latest = status["sections"]["release"]["latest_version"]

        correct = latest == "1.2.0"

        return {
            "name": "show_status_semver",
            "passed": correct,
            "latest_version": latest,
        }


def test_pipeline_dry_run(child_name: str, factory_dir: str, project_root: str) -> dict:
    """验证 learn_pipeline --dry-run 不抛出异常。"""
    pipeline_mod = _import_module("learn_pipeline")
    try:
        result = pipeline_mod.learn_pipeline(
            child_name=child_name,
            factory_dir=factory_dir,
            project_root=project_root,
            article_id=None,
            skip_eval=True,
            dry_run=True,
        )
        ok = result.get("dry_run") is True
    except Exception as e:
        return {"name": "pipeline_dry_run", "passed": False, "error": str(e), "traceback": traceback.format_exc()}
    return {"name": "pipeline_dry_run", "passed": ok}


def test_baseline_sha_alignment() -> dict:
    """验证 sync_visible_edits 能正确检测并更新 baseline_sha 与实际文件内容不一致的情况。"""
    import tempfile
    sync_mod = _import_module("sync_visible_edits")

    with tempfile.TemporaryDirectory() as tmpdir:
        factory_dir = Path(tmpdir) / "factory"
        project_root = Path(tmpdir) / "root"
        child_name = "test_sha_child"

        repo_dir = factory_dir / child_name / "repo"
        state_dir = repo_dir / "state"
        baselines_dir = state_dir / "baselines"
        manifests_dir = state_dir / "manifests"
        articles_dir = project_root / f"{child_name}_Generated_Articles"
        manifest_dir = articles_dir / ".manifest"

        for d in [baselines_dir, manifests_dir, articles_dir, manifest_dir]:
            d.mkdir(parents=True, exist_ok=True)

        article_id = "2026-04-22-001"
        topic_slug = "test-topic"

        # 创建初始 baseline
        baseline_content = "初始 baseline 内容"
        baseline_file = baselines_dir / f"{article_id}.md"
        baseline_file.write_text(baseline_content, encoding="utf-8")
        initial_baseline_sha = sync_mod.compute_sha(baseline_content)

        # 创建 visible draft
        visible_content = f"article_id: {article_id}\n\nvisible content"
        visible_file = articles_dir / f"{article_id}__{topic_slug}.md"
        visible_file.write_text(visible_content, encoding="utf-8")
        visible_sha = sync_mod.compute_sha(visible_content)

        # 创建 manifest（baseline_sha 为初始值）
        manifest = {
            "article_id": article_id,
            "child_name": f"writer-{child_name}",
            "child_version": "1.0.0",
            "baseline_sha": initial_baseline_sha,
            "current_sha": visible_sha,
            "topic": topic_slug,
            "status": "drafted",
        }
        state_manifest = manifests_dir / f"{article_id}.json"
        state_manifest.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        (manifest_dir / f"{article_id}.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

        # 修改 baseline 内容（模拟 Claude 填充正文）
        new_baseline_content = "这是 Claude 填充后的完整 baseline 内容"
        baseline_file.write_text(new_baseline_content, encoding="utf-8")
        expected_sha = sync_mod.compute_sha(new_baseline_content)

        # 运行 sync
        sync_mod.sync_visible_edits(child_name, str(factory_dir), str(project_root))

        # 检查 manifest 是否已更新
        updated_manifest = json.loads(state_manifest.read_text(encoding="utf-8"))
        aligned = updated_manifest.get("baseline_sha") == expected_sha

        return {
            "name": "baseline_sha_alignment",
            "passed": aligned,
            "expected_sha": expected_sha,
            "actual_sha": updated_manifest.get("baseline_sha"),
        }


def test_manifest_integrity(child_name: str, factory_dir: str) -> dict:
    """验证 state/manifests 指向的 baseline 文件存在。"""
    repo_dir = Path(factory_dir) / child_name / "repo"
    manifests_dir = repo_dir / "state" / "manifests"
    baselines_dir = repo_dir / "state" / "baselines"
    if not manifests_dir.exists():
        return {"name": "manifest_integrity", "passed": True, "note": "no manifests yet"}

    broken = []
    for mpath in manifests_dir.glob("*.json"):
        try:
            data = json.loads(mpath.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            broken.append({"manifest": mpath.name, "issue": "invalid json"})
            continue
        article_id = data.get("article_id")
        if article_id and not (baselines_dir / f"{article_id}.md").exists():
            broken.append({"manifest": mpath.name, "issue": f"missing baseline for {article_id}"})
    return {"name": "manifest_integrity", "passed": not broken, "broken": broken}


# ------------------------------------------------------------------
# 运行器
# ------------------------------------------------------------------

def run_all(child_name: str, factory_dir: str, project_root: str) -> dict:
    tests = [
        lambda: test_structure_integrity(child_name, factory_dir),
        lambda: test_style_memory_schema(child_name, factory_dir),
        lambda: test_rules_validity(child_name, factory_dir),
        lambda: test_diff_classification(),
        lambda: test_diff_empty_text(),
        lambda: test_diff_particle_frequency(),
        lambda: test_promote_dedup(),
        lambda: test_promote_cross_article_upgrade(),
        lambda: test_eval_score_range(child_name, factory_dir),
        lambda: test_eval_sensitivity(),
        lambda: test_pipeline_dry_run(child_name, factory_dir, project_root),
        lambda: test_manifest_integrity(child_name, factory_dir),
        lambda: test_baseline_sha_alignment(),
        lambda: test_show_status_semver(),
    ]

    results = []
    passed = 0
    failed = 0
    for t in tests:
        try:
            r = t()
        except Exception as e:
            r = {"name": t.__name__, "passed": False, "error": str(e), "traceback": traceback.format_exc()}
        results.append(r)
        if r.get("passed"):
            passed += 1
        else:
            failed += 1
            logger.warning("Test failed: %s", r)

    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "child_name": child_name,
        "total": len(tests),
        "passed": passed,
        "failed": failed,
        "results": results,
    }
    return summary


def write_report(child_name: str, repo_dir: Path, summary: dict) -> Path:
    lines = [
        f"# Regression Test Report: {child_name}",
        "",
        f"- **Run at:** {summary['run_at']}",
        f"- **Total:** {summary['total']} | **Passed:** {summary['passed']} | **Failed:** {summary['failed']}",
        "",
        "## Results",
        "",
        "| Test | Status | Detail |",
        "|------|--------|--------|",
    ]
    for r in summary["results"]:
        status = "PASS" if r.get("passed") else "FAIL"
        detail = ""
        if "summary" in r:
            detail = r["summary"]
        elif "error" in r:
            detail = f"error: {r['error'][:60]}"
        elif "missing" in r:
            detail = f"missing: {r['missing']}"
        elif "invalid_rules" in r:
            detail = f"invalid: {len(r['invalid_rules'])}"
        elif "out_of_range" in r:
            detail = f"oor: {len(r['out_of_range'])}"
        elif "broken" in r:
            detail = f"broken: {len(r['broken'])}"
        lines.append(f"| {r['name']} | {status} | {detail} |")

    lines.append("")
    lines.append("## Raw JSON")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(summary, ensure_ascii=False, indent=2))
    lines.append("```")

    report_path = repo_dir / "reports" / "regression-test-report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run regression tests for a child skill")
    parser.add_argument("child_name", help="Child skill name")
    parser.add_argument("--factory-dir", default=".claude/writing-factory/children", help="Factory base dir")
    parser.add_argument("--project-root", default=".", help="Project root directory")
    args = parser.parse_args()
    args.child_name = sanitize_child_name(args.child_name)

    with LogContext(logger, child_name=args.child_name, step="regression_test"):
        logger.info("Starting regression tests for %s", args.child_name)
        summary = run_all(args.child_name, args.factory_dir, args.project_root)
        repo_dir = Path(args.factory_dir) / args.child_name / "repo"
        report_path = write_report(args.child_name, repo_dir, summary)
        logger.info("Regression tests complete: %d/%d passed. Report: %s", summary["passed"], summary["total"], report_path)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"\nReport written to: {report_path}")

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
