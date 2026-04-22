#!/usr/bin/env python3
"""
build_style_profile.py
高分辨率风格画像生成（14维分析框架）。

用法:
    python build_style_profile.py <child_name> <samples_dir> [--factory-dir <dir>]
"""

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

from factory_logging import setup_logger, LogContext

# 14 维分析框架键名
DIMENSIONS = [
    "sentence_length", "paragraph_length", "paragraph_structure",
    "connector_density", "rhetoric_preference", "person_usage",
    "tense_narrative", "information_density", "emotional_intensity",
    "terminology_density", "citation_style", "opening_style",
    "ending_style", "rhythm_breathing"
]


def read_samples(samples_dir: str) -> List[Tuple[str, str]]:
    """读取样文，返回 (filename, content) 列表"""
    path = Path(samples_dir)
    files = []
    for ext in ("*.md", "*.txt"):
        files.extend(path.glob(ext))
    results = []
    for f in sorted(files):
        content = f.read_text(encoding="utf-8")
        # 简单清洗：移除 markdown 标记
        content = re.sub(r'[#*`\[\]!]', '', content)
        results.append((f.name, content))
    return results


def split_sentences(text: str) -> List[str]:
    """按中文句号、感叹号、问号、换行分句"""
    sentences = re.split(r'[。！？\n]', text)
    return [s.strip() for s in sentences if s.strip()]


def split_paragraphs(text: str) -> List[str]:
    """按空行分段"""
    return [p.strip() for p in text.split('\n\n') if p.strip()]


# ---------------------------------------------------------------------------
# D01 句子长度偏好
# ---------------------------------------------------------------------------
def analyze_sentence_length(text: str) -> Dict:
    sentences = split_sentences(text)
    lengths = [len(s) for s in sentences]
    if not lengths:
        return {"avg": 0, "distribution": {}, "dominant": "unknown"}
    avg = sum(lengths) / len(lengths)
    buckets = {"short": 0, "medium": 0, "long": 0}
    for l in lengths:
        if l < 15:
            buckets["short"] += 1
        elif l < 35:
            buckets["medium"] += 1
        else:
            buckets["long"] += 1
    total = len(lengths)
    distribution = {k: round(v / total, 2) for k, v in buckets.items()}
    dominant = max(distribution, key=distribution.get)
    return {"avg": round(avg, 1), "distribution": distribution, "dominant": dominant}


# ---------------------------------------------------------------------------
# D02 段落长度偏好
# ---------------------------------------------------------------------------
def analyze_paragraph_length(text: str) -> Dict:
    paragraphs = split_paragraphs(text)
    lengths = [len(p) for p in paragraphs]
    if not lengths:
        return {"avg": 0, "distribution": {}, "dominant": "unknown"}
    avg = sum(lengths) / len(lengths)
    buckets = {"short": 0, "medium": 0, "long": 0}
    for l in lengths:
        if l < 80:
            buckets["short"] += 1
        elif l < 200:
            buckets["medium"] += 1
        else:
            buckets["long"] += 1
    total = len(lengths)
    distribution = {k: round(v / total, 2) for k, v in buckets.items()}
    dominant = max(distribution, key=distribution.get)
    return {"avg": round(avg, 1), "distribution": distribution, "dominant": dominant}


# ---------------------------------------------------------------------------
# D03 段落结构模式
# ---------------------------------------------------------------------------
def analyze_paragraph_structure(text: str) -> Dict:
    paragraphs = split_paragraphs(text)
    if not paragraphs:
        return {"dominant": "unknown", "distribution": {}}

    patterns = Counter()
    for para in paragraphs:
        # 总分：首句含总括词，后续有例证
        if re.search(r'^(总的来说|总体而言|简单来说|一句话)', para):
            patterns["general_to_specific"] += 1
        # 分总：末尾有总结词
        elif re.search(r'(总之|归根结底|说到底|所以|因此)$', para[-20:]):
            patterns["specific_to_general"] += 1
        # 递进：含递进连接词
        elif re.search(r'(不仅|不但|甚至|更|而且|进而)', para):
            patterns["progressive"] += 1
        # 并列：含并列连接词或分号
        elif re.search(r'(同时|另外|此外|一方面|另一方面|；)', para):
            patterns["parallel"] += 1
        else:
            patterns["neutral"] += 1

    total = sum(patterns.values())
    distribution = {k: round(v / total, 2) for k, v in patterns.most_common()}
    dominant = patterns.most_common(1)[0][0] if patterns else "unknown"
    return {"dominant": dominant, "distribution": distribution}


# ---------------------------------------------------------------------------
# D04 连接词使用密度
# ---------------------------------------------------------------------------
def analyze_connectors(text: str) -> Dict:
    connector_words = [
        "但是", "然而", "不过", "可是", "而", "却",
        "因为", "所以", "因此", "于是", "从而",
        "首先", "其次", "然后", "接着", "最后",
        "不仅", "而且", "并且", "同时", "另外",
        "如果", "即使", "虽然", "尽管", "无论",
        "总之", "总而言之", "换句话说", "也就是说", "换言之",
        "例如", "比如", "像", "正如"
    ]
    counts = Counter()
    for word in connector_words:
        counts[word] = len(re.findall(re.escape(word), text))
    total = sum(counts.values())
    total_chars = len(text)
    density = round(total / total_chars * 1000, 2) if total_chars else 0
    top = counts.most_common(10)
    return {"total": total, "density_per_1k": density, "top": top}


# ---------------------------------------------------------------------------
# D05 修辞手法偏好
# ---------------------------------------------------------------------------
def analyze_rhetoric(text: str) -> Dict:
    # 比喻：明确比喻词
    metaphor = len(re.findall(r'像|如同|仿佛|犹如|像是|好似|宛如', text))

    # 拟人：排除人称主语（我你他她它/我们你们他们她们它们），匹配非人事物+人类行为谓词
    personification = 0
    # 常见非人主语 + 人类谓词（风在说、时间见证、城市叹息等）
    personification += len(re.findall(
        r'(?:风|雨|阳光|时间|岁月|历史|时代|世界|城市|市场|技术|数据|算法|模型|系统|浪潮|趋势|机器|AI|代码|网络|平台|光线|夜晚|大地|海洋|山川|河流|火焰|种子|萌芽|凋零)[^，。！？\n]{0,4}(?:在|说|觉得|认为|感到|叹息|低语|咆哮|沉默|等待|见证|记录|讲述|诉说|笑|哭|奔跑|沉睡|醒来|凝视)',
        text
    ))
    # 更通用的模式：连续2-6个非人称汉字 + 人类谓词（需前后文排除人名等，这里用保守策略）
    personification += len(re.findall(
        r'[^，。！？\n我你他她它咱们俺咱我们你们他们她们它们的]{3,6}(?:在[^，。！？\n]{0,2}(?:说|笑|哭泣|叹息|低语|咆哮)|觉得|认为|感到|见证|记录|讲述|诉说|沉默|等待)',
        text
    ))

    # 反问
    rhetorical_question = len(re.findall(r'难道|岂|何尝|何必', text))

    # 夸张
    exaggeration = len(re.findall(r'绝对|永远|无数|所有|一切|完全|彻底', text))

    # 对比
    contrast = len(re.findall(r'不是.*而是|与其.*不如|一方面.*另一方面', text))

    patterns = {
        "metaphor": metaphor,
        "personification": personification,
        "rhetorical_question": rhetorical_question,
        "exaggeration": exaggeration,
        "contrast": contrast,
    }
    total = sum(patterns.values())
    distribution = {k: round(v / total, 2) if total else 0 for k, v in patterns.items()}
    dominant = max(patterns, key=patterns.get) if total else "unknown"
    return {"dominant": dominant, "distribution": distribution, "counts": patterns}


# ---------------------------------------------------------------------------
# D06 人称使用
# ---------------------------------------------------------------------------
def analyze_person_usage(text: str) -> Dict:
    first = len(re.findall(r'我|我们|我的|咱们', text))
    second = len(re.findall(r'你|你们|您的|你俩', text))
    third = len(re.findall(r'他|她|它|他们|她们|它们|其|某人', text))
    total = first + second + third
    if total == 0:
        return {"dominant": "none", "distribution": {}}
    distribution = {
        "first": round(first / total, 2),
        "second": round(second / total, 2),
        "third": round(third / total, 2),
    }
    dominant = max(distribution, key=distribution.get)
    return {"dominant": dominant, "distribution": distribution, "counts": {"first": first, "second": second, "third": third}}


# ---------------------------------------------------------------------------
# D07 时态与叙事时间
# ---------------------------------------------------------------------------
def analyze_tense_narrative(text: str) -> Dict:
    past_markers = len(re.findall(r'曾经|那时|当时|过去|以前|之前|已经|了|过', text))
    present_markers = len(re.findall(r'现在|目前|当下|今天|如今|正在|着', text))
    future_markers = len(re.findall(r'将|会|可能|也许|未来|以后|之后|下一步', text))
    total = past_markers + present_markers + future_markers
    if total == 0:
        return {"dominant": "no_markers", "distribution": {}}
    distribution = {
        "past": round(past_markers / total, 2),
        "present": round(present_markers / total, 2),
        "future": round(future_markers / total, 2),
    }
    dominant = max(distribution, key=distribution.get)
    return {"dominant": dominant, "distribution": distribution}


# ---------------------------------------------------------------------------
# D08 信息密度
# ---------------------------------------------------------------------------
def analyze_information_density(text: str) -> Dict:
    sentences = split_sentences(text)
    if not sentences:
        return {"avg_entities_per_sentence": 0, "dominant": "unknown"}
    # 信息单元计数：数字、英文术语、引号内容、带后缀的专有名词/机构名/技术概念
    entity_counts = []
    for s in sentences:
        count = 0
        # 数字（含百分比、小数）
        count += len(re.findall(r'\d+\.?\d*[%％]?', s))
        # 英文术语（3字母以上）
        count += len(re.findall(r'[a-zA-Z]{3,}', s))
        # 引号内容
        count += len(re.findall(r'[「""].*?[」""]', s))
        # 带组织/机构/技术后缀的实体
        count += len(re.findall(
            r'[一-鿿]{2,8}(?:公司|组织|机构|平台|系统|框架|模型|算法|技术|产品|服务|行业|市场|国家|地区|城市|学派|理论|概念|原则|方法)',
            s
        ))
        entity_counts.append(count)
    avg = sum(entity_counts) / len(entity_counts)
    # 概念密度：每百字平均实体数
    total_chars = len(text)
    density_per_100 = round(avg / max(len(sentences), 1) * 100, 2) if sentences else 0
    dominant = "high" if avg > 5 else ("medium" if avg > 2 else "low")
    return {"avg_entities_per_sentence": round(avg, 1), "density_per_100": density_per_100, "dominant": dominant}


# ---------------------------------------------------------------------------
# D09 情感表达强度
# ---------------------------------------------------------------------------
def analyze_emotional_intensity(text: str) -> Dict:
    emotional_words = [
        "惊讶", "震惊", "愤怒", "悲哀", "快乐", "兴奋", "焦虑", "恐惧",
        "热爱", "厌恶", "失望", "希望", "绝望", "激动", "平静", "无奈",
        "好笑", "心疼", "佩服", "鄙视", "赞赏", "批评", "担心", "期待"
    ]
    count = sum(len(re.findall(re.escape(w), text)) for w in emotional_words)
    exclamation = text.count('！') + text.count('!')
    total_chars = len(text)
    density = round(count / total_chars * 1000, 2) if total_chars else 0
    exclamation_density = round(exclamation / total_chars * 1000, 2) if total_chars else 0
    dominant = "strong" if density > 3 or exclamation_density > 5 else ("moderate" if density > 1 else "restrained")
    return {"emotional_word_density_per_1k": density, "exclamation_density_per_1k": exclamation_density, "dominant": dominant}


# ---------------------------------------------------------------------------
# D10 专业术语密度
# ---------------------------------------------------------------------------
def analyze_terminology(text: str) -> Dict:
    # 粗略检测：英文单词、四字以上的专业复合词、技术常见词
    english_terms = len(re.findall(r'[a-zA-Z]{3,}', text))
    tech_terms = len(re.findall(
        r'模型|算法|数据|系统|平台|框架|引擎|协议|接口|模块|组件|部署|训练|推理|微调|对齐|涌现|泛化|过拟合|token|embedding|LLM|AI|API',
        text
    ))
    total_chars = len(text)
    density = round((english_terms + tech_terms) / total_chars * 1000, 2) if total_chars else 0
    dominant = "high" if density > 15 else ("medium" if density > 5 else "low")
    return {"english_terms": english_terms, "tech_terms": tech_terms, "density_per_1k": density, "dominant": dominant}


# ---------------------------------------------------------------------------
# D11 引用与证据方式
# ---------------------------------------------------------------------------
def analyze_citation_style(text: str) -> Dict:
    direct_quote = len(re.findall(r'[""""「」]', text))
    data_ref = len(re.findall(r'\d+[%％]|\d+\.\d+[%％]|统计|数据|报告|研究显示|调查发现', text))
    case_ref = len(re.findall(r'例如|比如|举个例子|案例|有一个|有一次', text))
    expert_ref = len(re.findall(r'据.*说|某.*表示|专家|学者|认为', text))
    total = direct_quote + data_ref + case_ref + expert_ref
    if total == 0:
        return {"dominant": "none", "distribution": {}}
    distribution = {
        "direct_quote": round(direct_quote / total, 2),
        "data_ref": round(data_ref / total, 2),
        "case_ref": round(case_ref / total, 2),
        "expert_ref": round(expert_ref / total, 2),
    }
    dominant = max(distribution, key=distribution.get)
    return {"dominant": dominant, "distribution": distribution}


# ---------------------------------------------------------------------------
# D12 / D13 开头与结尾方式
# ---------------------------------------------------------------------------
def analyze_opening_ending(samples: List[Tuple[str, str]]) -> Dict:
    opening_patterns = Counter()
    ending_patterns = Counter()
    openings = []
    endings = []

    for _, text in samples:
        paras = split_paragraphs(text)
        if not paras:
            continue
        first = paras[0]
        last = paras[-1]
        openings.append(first[:80])
        endings.append(last[-80:])

        # 开头分类
        if any(w in first for w in ["为什么", "怎么", "什么", "吗", "呢", "难道", "何尝"]):
            opening_patterns["question"] += 1
        elif any(w in first for w in ["最近", "那天", "有一次", "记得", "故事", "当年"]):
            opening_patterns["story"] += 1
        elif re.search(r'\d+[%％]|数据|报告|统计|显示', first):
            opening_patterns["data"] += 1
        elif re.search(r'我认为|我觉得|在我看来|一句话|简单来说', first):
            opening_patterns["opinion"] += 1
        else:
            opening_patterns["situation"] += 1

        # 结尾分类
        if any(w in last for w in ["总之", "总结", "归根结底", "说到底", "综上"]):
            ending_patterns["summary"] += 1
        elif any(w in last for w in ["你", "我们", "不妨", "试试", "可以", "建议"]):
            ending_patterns["call_to_action"] += 1
        elif any(w in last for w in ["？", "?", "难道", "吗", "呢"]):
            ending_patterns["rhetorical_question"] += 1
        elif re.search(r'[""""「」].{5,30}[""""」]', last):
            ending_patterns["quote"] += 1
        else:
            ending_patterns["open"] += 1

    total_o = sum(opening_patterns.values())
    total_e = sum(ending_patterns.values())

    return {
        "opening": {
            "dominant": opening_patterns.most_common(1)[0][0] if opening_patterns else "unknown",
            "distribution": {k: round(v / total_o, 2) for k, v in opening_patterns.most_common()} if total_o else {}
        },
        "ending": {
            "dominant": ending_patterns.most_common(1)[0][0] if ending_patterns else "unknown",
            "distribution": {k: round(v / total_e, 2) for k, v in ending_patterns.most_common()} if total_e else {}
        },
        "openings": openings,
        "endings": endings,
    }


# ---------------------------------------------------------------------------
# D14 节奏与呼吸感
# ---------------------------------------------------------------------------
def analyze_rhythm_breathing(text: str) -> Dict:
    sentences = split_sentences(text)
    if len(sentences) < 3:
        return {"dominant": "unknown", "distribution": {}, "pause_density": 0}

    lengths = [len(s) for s in sentences]
    # 检测长短交替模式
    alternations = 0
    for i in range(1, len(lengths)):
        if (lengths[i] > 30 and lengths[i - 1] < 20) or (lengths[i] < 20 and lengths[i - 1] > 30):
            alternations += 1
    alt_ratio = round(alternations / (len(lengths) - 1), 2) if len(lengths) > 1 else 0

    # 停顿密度（逗号、顿号、分号、破折号、省略号）
    pauses = text.count('，') + text.count('、') + text.count('；') + text.count('——') + text.count('……')
    pause_density = round(pauses / len(text) * 1000, 2) if text else 0

    if alt_ratio > 0.4:
        dominant = "undulating"
    elif pause_density > 60:
        dominant = "leisurely"
    elif pause_density < 30:
        dominant = "urgent"
    else:
        dominant = "uniform"

    return {
        "dominant": dominant,
        "alternation_ratio": alt_ratio,
        "pause_density_per_1k": pause_density,
        "avg_sentence_length": round(sum(lengths) / len(lengths), 1) if lengths else 0,
    }


# ---------------------------------------------------------------------------
# 标点偏好
# ---------------------------------------------------------------------------
def analyze_punctuation(text: str) -> Dict:
    total_chars = len(text)
    if total_chars == 0:
        return {}
    marks = {
        "comma": text.count('，'),
        "period": text.count('。'),
        "semicolon": text.count('；'),
        "dash": text.count('——') + text.count('－'),
        "parentheses": text.count('（') + text.count('('),
        "quotes": text.count('"') + text.count('"') + text.count("'") + text.count("'") + text.count('「') + text.count('」'),
        "ellipsis": text.count('……') + text.count('...'),
        "exclamation": text.count('！') + text.count('!'),
        "question": text.count('？') + text.count('?'),
    }
    density = {k: round(v / total_chars * 1000, 2) for k, v in marks.items()}
    return {"counts": marks, "density_per_1k": density}


# ---------------------------------------------------------------------------
# Few-shot 提取
# ---------------------------------------------------------------------------
def extract_few_shots(samples: List[Tuple[str, str]], max_per_sample: int = 2, max_chars: int = 200) -> List[str]:
    """提取 few-shot 片段"""
    shots = []
    for _, text in samples:
        paras = [p.strip() for p in text.split('\n\n') if p.strip() and len(p.strip()) > 50]
        for para in paras[:max_per_sample]:
            shot = para[:max_chars]
            if len(shot) >= 30:
                shots.append(shot)
    return shots[:5]


# ---------------------------------------------------------------------------
# 段落配方提取（简单启发式）
# ---------------------------------------------------------------------------
def extract_paragraph_formulas(samples: List[Tuple[str, str]]) -> List[Dict]:
    """从样文中提取高频段落配方"""
    formulas = Counter()
    for _, text in samples:
        paras = split_paragraphs(text)
        for para in paras:
            # 观点-例证-回扣
            if re.search(r'(我认为|我觉得|观点是|一句话)', para) and re.search(r'(比如|例如|像|有一次)', para):
                formulas["观点-例证-回扣"] += 1
            # 情境-感受-判断
            elif re.search(r'(那天|当时|最近|有一次)', para) and re.search(r'(感到|觉得|意识到|发现)', para):
                formulas["情境-感受-判断"] += 1
            # 问题-分析-结论
            elif re.search(r'(为什么|怎么|什么|呢|吗)', para) and re.search(r'(因为|所以|因此|于是)', para):
                formulas["问题-分析-结论"] += 1
            # 数据-解读- implications
            elif re.search(r'\d+', para) and re.search(r'(说明|表明|意味着|反映)', para):
                formulas["数据-解读-引申"] += 1

    total = sum(formulas.values())
    result = []
    for name, count in formulas.most_common(3):
        result.append({
            "name": name,
            "frequency": "high" if count / total > 0.3 else "medium",
            "typical_length": "3-5句",
            "evidence_count": count,
        })
    return result


# ---------------------------------------------------------------------------
# 叙述方法识别
# ---------------------------------------------------------------------------
def extract_narrative_moves(text: str) -> List[Dict]:
    """识别叙述方法"""
    moves = []
    if re.search(r'(那天|当时|曾经|后来|之后|然后|接着)', text):
        moves.append({"move": "顺叙推进", "confidence": "active", "evidence": "时间链标记词高频出现"})
    if re.search(r'(回到|回到.*之前|先.*再.*最后|倒回)', text):
        moves.append({"move": "倒叙/插叙", "confidence": "medium", "evidence": "回溯标记词出现"})
    if re.search(r'(视角|角度|从.*来看|对.*而言)', text):
        moves.append({"move": "视角切换", "confidence": "medium", "evidence": "视角标记词出现"})
    if len(re.findall(r'我|我们', text)) > len(re.findall(r'他|她|它|他们', text)):
        moves.append({"move": "第一人称主导", "confidence": "active", "evidence": "第一人称代词占比更高"})
    else:
        moves.append({"move": "第三人称/客观叙述", "confidence": "active", "evidence": "第三人称或缺省人称为主"})
    return moves


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def build_style_profile(child_name: str, samples_dir: str, factory_dir: str) -> None:
    logger = setup_logger(__name__, child_name=child_name)
    samples = read_samples(samples_dir)
    if not samples:
        logger.error("No samples found in %s", samples_dir)
        sys.exit(1)

    all_text = "\n\n".join([t for _, t in samples])

    # 执行全部 14 维分析
    sentence_analysis = analyze_sentence_length(all_text)
    paragraph_analysis = analyze_paragraph_length(all_text)
    paragraph_structure = analyze_paragraph_structure(all_text)
    punctuation_analysis = analyze_punctuation(all_text)
    connector_analysis = analyze_connectors(all_text)
    rhetoric_analysis = analyze_rhetoric(all_text)
    person_analysis = analyze_person_usage(all_text)
    tense_analysis = analyze_tense_narrative(all_text)
    info_density = analyze_information_density(all_text)
    emotional = analyze_emotional_intensity(all_text)
    terminology = analyze_terminology(all_text)
    citation = analyze_citation_style(all_text)
    oe_analysis = analyze_opening_ending(samples)
    rhythm = analyze_rhythm_breathing(all_text)
    few_shots = extract_few_shots(samples)
    paragraph_formulas = extract_paragraph_formulas(samples)
    narrative_moves = extract_narrative_moves(all_text)

    # 生成风格 DNA 描述
    style_dna = (
        f"该作者偏好{sentence_analysis.get('dominant', '中等')}句长，"
        f"{paragraph_analysis.get('dominant', '中等')}段落，"
        f"连接词密度为每千字 {connector_analysis['density_per_1k']} 个。"
        f"人称以{person_analysis.get('dominant', '无明显偏好')}为主，"
        f"情感表达趋于{emotional.get('dominant', '温和')}。"
        f"开头偏好{oe_analysis['opening']['dominant']}，"
        f"结尾偏好{oe_analysis['ending']['dominant']}。"
        f"节奏感呈{rhythm.get('dominant', '均匀')}特征。"
    )

    # 构建 style-memory.json
    style_memory = {
        "voice_traits": [
            {"trait": "句长偏好", "value": sentence_analysis.get("dominant", "unknown"), "confidence": "active"},
            {"trait": "段长偏好", "value": paragraph_analysis.get("dominant", "unknown"), "confidence": "active"},
            {"trait": "段落结构", "value": paragraph_structure.get("dominant", "unknown"), "confidence": "active"},
            {"trait": "修辞偏好", "value": rhetoric_analysis.get("dominant", "unknown"), "confidence": "active"},
            {"trait": "人称使用", "value": person_analysis.get("dominant", "unknown"), "confidence": "active"},
            {"trait": "时态叙事", "value": tense_analysis.get("dominant", "unknown"), "confidence": "active"},
            {"trait": "信息密度", "value": info_density.get("dominant", "unknown"), "confidence": "active"},
            {"trait": "情感强度", "value": emotional.get("dominant", "unknown"), "confidence": "active"},
            {"trait": "术语密度", "value": terminology.get("dominant", "unknown"), "confidence": "active"},
            {"trait": "引用风格", "value": citation.get("dominant", "unknown"), "confidence": "active"},
            {"trait": "开头方式", "value": oe_analysis["opening"]["dominant"], "confidence": "active"},
            {"trait": "结尾方式", "value": oe_analysis["ending"]["dominant"], "confidence": "active"},
            {"trait": "节奏呼吸", "value": rhythm.get("dominant", "unknown"), "confidence": "active"},
        ],
        "punctuation_preferences": [
            {"mark": k, "density_per_1k": v, "confidence": "active"}
            for k, v in punctuation_analysis.get("density_per_1k", {}).items()
        ],
        "paragraph_formulas": paragraph_formulas,
        "narrative_moves": narrative_moves,
        "editorial_heuristics": [],
        "author_boundary_rules": [],
        "anti_patterns": [],
        "confidence_buckets": {
            "candidate": [],
            "probation": [],
            "active": []
        }
    }

    # 写入 canonical repo
    repo_dir = Path(factory_dir) / child_name / "repo"
    skill_dir = repo_dir / "skill"
    state_dir = repo_dir / "state"

    # 生成 style-profile.md
    style_profile_path = skill_dir / "references" / "style-profile.md"
    lines = [
        f"# {child_name} 风格画像",
        "",
        f"> 基于 {len(samples)} 篇样文",
        f"> 生成时间：{datetime.now(timezone.utc).isoformat()}",
        "",
        "## 核心风格 DNA",
        "",
        style_dna,
        "",
        "## 14 维量化底盘",
        "",
        f"### D01 句子长度偏好",
        f"- 平均句长：{sentence_analysis['avg']} 字",
        f"- 分布：{sentence_analysis.get('distribution', {})}",
        f"- 主导：{sentence_analysis.get('dominant', 'unknown')}",
        "",
        f"### D02 段落长度偏好",
        f"- 平均段长：{paragraph_analysis['avg']} 字",
        f"- 分布：{paragraph_analysis.get('distribution', {})}",
        f"- 主导：{paragraph_analysis.get('dominant', 'unknown')}",
        "",
        f"### D03 段落结构模式",
        f"- 主导：{paragraph_structure.get('dominant', 'unknown')}",
        f"- 分布：{paragraph_structure.get('distribution', {})}",
        "",
        f"### D04 连接词使用密度",
        f"- 每千字连接词数：{connector_analysis['density_per_1k']}",
        f"- 高频连接词：{connector_analysis['top'][:5]}",
        "",
        f"### D05 修辞手法偏好",
        f"- 主导：{rhetoric_analysis.get('dominant', 'unknown')}",
        f"- 分布：{rhetoric_analysis.get('distribution', {})}",
        "",
        f"### D06 人称使用",
        f"- 主导：{person_analysis.get('dominant', 'unknown')}",
        f"- 分布：{person_analysis.get('distribution', {})}",
        "",
        f"### D07 时态与叙事时间",
        f"- 主导：{tense_analysis.get('dominant', 'unknown')}",
        f"- 分布：{tense_analysis.get('distribution', {})}",
        "",
        f"### D08 信息密度",
        f"- 平均每句实体数：{info_density.get('avg_entities_per_sentence', 0)}",
        f"- 每百字概念密度：{info_density.get('density_per_100', 0)}",
        f"- 主导：{info_density.get('dominant', 'unknown')}",
        "",
        f"### D09 情感表达强度",
        f"- 情感词密度（每千字）：{emotional.get('emotional_word_density_per_1k', 0)}",
        f"- 感叹号密度（每千字）：{emotional.get('exclamation_density_per_1k', 0)}",
        f"- 主导：{emotional.get('dominant', 'unknown')}",
        "",
        f"### D10 专业术语密度",
        f"- 英文术语数：{terminology.get('english_terms', 0)}",
        f"- 技术词数：{terminology.get('tech_terms', 0)}",
        f"- 密度（每千字）：{terminology.get('density_per_1k', 0)}",
        f"- 主导：{terminology.get('dominant', 'unknown')}",
        "",
        f"### D11 引用与证据方式",
        f"- 主导：{citation.get('dominant', 'unknown')}",
        f"- 分布：{citation.get('distribution', {})}",
        "",
        f"### D12 开头方式",
        f"- 主导：{oe_analysis['opening']['dominant']}",
        f"- 分布：{oe_analysis['opening']['distribution']}",
        "",
        f"### D13 结尾方式",
        f"- 主导：{oe_analysis['ending']['dominant']}",
        f"- 分布：{oe_analysis['ending']['distribution']}",
        "",
        f"### D14 节奏与呼吸感",
        f"- 主导：{rhythm.get('dominant', 'unknown')}",
        f"- 长短句交替比例：{rhythm.get('alternation_ratio', 0)}",
        f"- 停顿密度（每千字）：{rhythm.get('pause_density_per_1k', 0)}",
        f"- 平均句长：{rhythm.get('avg_sentence_length', 0)} 字",
        "",
        "## 标点偏好",
        "",
        "| 标点 | 每千字密度 |",
        "|------|-----------|",
    ]
    for k, v in punctuation_analysis.get("density_per_1k", {}).items():
        lines.append(f"| {k} | {v} |")

    lines.extend([
        "",
        "## 段落配方",
        "",
    ])
    if paragraph_formulas:
        for pf in paragraph_formulas:
            lines.append(f"- **{pf['name']}**：出现频率 {pf['frequency']}，典型长度 {pf['typical_length']}")
    else:
        lines.append("- 未检测到显著高频段落配方（需更多样文或更精细分析）")

    lines.extend([
        "",
        "## 叙述方法",
        "",
    ])
    if narrative_moves:
        for nm in narrative_moves:
            lines.append(f"- **{nm['move']}**（置信度：{nm['confidence']}）：{nm['evidence']}")
    else:
        lines.append("- 未检测到显著叙述方法特征")

    lines.extend([
        "",
        "## 风格证据（few-shot）",
        "",
    ])
    for i, shot in enumerate(few_shots, 1):
        lines.append(f"### 片段 {i}")
        lines.append(f"> {shot}")
        lines.append("")

    style_profile_path.write_text("\n".join(lines), encoding="utf-8")

    # 写入 style-memory.json
    memory_path = skill_dir / "assets" / "style-memory.json"
    memory_path.write_text(json.dumps(style_memory, ensure_ascii=False, indent=2), encoding="utf-8")

    # 生成/更新 examples.md
    examples_path = skill_dir / "references" / "examples.md"
    example_lines = [
        f"# {child_name} 风格示例",
        "",
        "> 以下示例从样文中提取，用于 few-shot 风格引导。",
        "",
        "## 正例",
        "",
    ]
    for i, shot in enumerate(few_shots, 1):
        example_lines.append(f"### 示例 {i}")
        example_lines.append(f"")
        example_lines.append(f"> {shot}")
        example_lines.append("")
        example_lines.append("**风格要点**：")
        # 自动生成简单风格要点
        style_notes = []
        if len(shot) < 100:
            style_notes.append("- 简短有力")
        elif len(shot) > 180:
            style_notes.append("- 信息密度较高")
        if '，' in shot:
            style_notes.append("- 善用逗号营造节奏")
        if '。' in shot:
            style_notes.append("- 句号收束明确")
        if not style_notes:
            style_notes.append("- 自然流畅")
        example_lines.extend(style_notes)
        example_lines.append("")

    example_lines.extend([
        "## 反例",
        "",
        "### 反例 1：AI 套路句",
        "> 在当今社会，随着科技的发展，人们越来越关注...",
        "",
        "**问题**：空泛开头、套路化表达、无具体情境。",
        "",
        "### 反例 2：伪造经历",
        "> 我曾经亲自经历过一次类似的危机，当时我感到无比焦虑...",
        "",
        "**问题**：若无明确标记，AI 不应声称拥有第一手经历。",
        "",
        "### 反例 3：空泛收束",
        "> 让我们一起期待更美好的未来吧！",
        "",
        "**问题**：口号式收束，无实质判断。",
        "",
        "## 使用说明",
        "",
        "- 正例用于引导生成方向",
        "- 反例用于拦截常见 AI 味",
        "- 示例会随学习更新而扩充",
    ])
    examples_path.write_text("\n".join(example_lines), encoding="utf-8")

    # 保存原始分析到 profiles
    profile_path = state_dir / "profiles" / f"style-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json"
    profile_data = {
        "child_name": child_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sample_count": len(samples),
        "sentence_analysis": sentence_analysis,
        "paragraph_analysis": paragraph_analysis,
        "paragraph_structure": paragraph_structure,
        "punctuation_analysis": punctuation_analysis,
        "connector_analysis": connector_analysis,
        "rhetoric_analysis": rhetoric_analysis,
        "person_analysis": person_analysis,
        "tense_analysis": tense_analysis,
        "info_density": info_density,
        "emotional": emotional,
        "terminology": terminology,
        "citation": citation,
        "opening_ending": oe_analysis,
        "rhythm": rhythm,
        "few_shots": few_shots,
        "paragraph_formulas": paragraph_formulas,
        "narrative_moves": narrative_moves,
    }
    profile_path.write_text(json.dumps(profile_data, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("Style profile saved to %s", style_profile_path)
    logger.info("Style memory saved to %s", memory_path)
    logger.info("Examples saved to %s", examples_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build style profile for a writer child")
    parser.add_argument("child_name", help="Child skill name")
    parser.add_argument("samples_dir", help="Directory containing sample articles")
    parser.add_argument("--factory-dir", default=".claude/writing-factory/children", help="Factory base dir")
    args = parser.parse_args()
    build_style_profile(args.child_name, args.samples_dir, args.factory_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
