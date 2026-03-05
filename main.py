import streamlit as st
import os
import hashlib
from dotenv import load_dotenv
from openai import OpenAI
import json
import PyPDF2
from docx import Document

import concurrent.futures
import math
import altair as alt
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re
from duckduckgo_search import DDGS
from examples import EXAMPLE_AI, EXAMPLE_HUMAN

try:
    import jieba
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False

# Load environment variables
load_dotenv(override=True)

# Configuration
API_KEY = os.getenv("LLM_API_KEY")
BASE_URL = os.getenv("LLM_BASE_URL")
MODEL_NAME = os.getenv("LLM_MODEL_NAME")
CHUNK_SIZE = 4000  # Characters per chunk for processing

# Forbidden Vocabulary Categories
FORBIDDEN_VOCABULARY = {
    "神态描写类": {
        "words": ["眼神", "嘴角", "睫毛", "空洞", "鼻音", "哭腔", "狡黠", "沙哑", "低沉"],
        "logic": "避免主观神态解读，强制客观描写"
    },
    "动作修饰类": {
        "words": ["泛白", "发白", "攥紧", "绷紧", "凝滞", "闪过", "投入", "呜咽", "擂鼓"],
        "logic": "防止过度聚焦微观动作，如手指特写"
    },
    "抽象感知类": {
        "words": ["感到", "知道", "复杂", "生理性", "难以言喻", "四肢百骸"],
        "logic": "将抽象情绪转化为可观察行为"
    },
    "比喻禁用类": {
        "words": ["羽毛", "湖面", "心湖", "涟漪", "石子", "手术刀", "弓弦"],
        "logic": "避免陈腐比喻"
    },
    "程度副词类": {
        "words": ["几分", "一丝", "某种", "近乎", "微不可查"],
        "logic": "减少不确定性表达"
    },
    "否定结构类": {
        "words": ["不是", "不再", "没什么", "而是"],
        "logic": "简化反转句式"
    },
    "冗余修饰类": {
        "words": ["更是", "如同", "仿佛", "就像", "带着", "不容"],
        "logic": "减少无效修饰"
    }
}

DEFAULT_CATCHPHRASES = [
    "投石入水", "不是X而是X", "交响曲", "喧嚣", "静谧", "蜕变", "不可否认",
    "值得注意的是", "总而言之", "首先...其次...最后...", "某种意义上", "由此可见",
    "换言之", "简而言之", "归根结底", "复杂的", "多层面的", "不仅...而且...",
    "一方面...另一方面...", "不可或缺", "至关重要", "显而易见", "毫无疑问",
    "核心", "关键", "框架", "机制", "模式", "体系", "赋能", "驱动",
    "引领", "重塑", "革新", "突破", "挑战", "机遇", "趋势", "愿景"
]

# Append forbidden words to DEFAULT_CATCHPHRASES
for category, data in FORBIDDEN_VOCABULARY.items():
    DEFAULT_CATCHPHRASES.extend(data["words"])



# Streamlit Page Config
st.set_page_config(
        page_title="AI 文本检测与分析工具",
        page_icon="🔍",
        layout="wide",
        initial_sidebar_state="expanded"
    )

# Custom CSS for "Clean Light" theme
st.markdown("""
<style>
    /* Global Background & Text */
    .stApp {
        background-color: #ffffff;
        color: #31333F;
    }

    /* Titles & Headers */
    h1, h2, h3 {
        color: #1f77b4 !important;
        font-family: 'Segoe UI', sans-serif;
        font-weight: 600;
    }

    /* Metric Values */
    [data-testid="stMetricValue"] {
        color: #2ca02c;
        font-size: 2.5rem !important;
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #f8f9fa;
        border-right: 1px solid #dee2e6;
    }
    
    /* Buttons - Modern Glassmorphism (Light) */
    .stButton>button {
        background: linear-gradient(145deg, #ffffff, #f0f2f6);
        color: #31333F;
        border: 1px solid #d1d5db;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        transition: all 0.2s ease-in-out;
        font-weight: 600;
    }
    .stButton>button:hover {
        background: linear-gradient(145deg, #f0f2f6, #e6e8eb);
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        border-color: #1f77b4;
    }

    /* Text Areas & Inputs */
    .stTextArea>div>div>textarea {
        background-color: #ffffff;
        color: #31333F;
        border: 1px solid #dee2e6;
        border-radius: 6px;
    }
    .stTextArea>div>div>textarea:focus {
        border-color: #1f77b4;
        box-shadow: 0 0 0 2px rgba(31, 119, 180, 0.2);
    }

    /* Cards/Containers */
    div[data-testid="stExpander"] {
        background-color: #ffffff;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    
    /* Success/Warning/Error Messages */
    .stAlert {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        color: #31333F;
    }
    
    /* Progress Bar */
    .stProgress > div > div > div > div {
        background-image: linear-gradient(to right, #2ca02c, #98df8a);
    }
</style>
""", unsafe_allow_html=True)



# Initialize Client
if not API_KEY or not BASE_URL or not MODEL_NAME:
    st.error("请检查 .env 文件配置是否正确 (LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME)")
    st.stop()

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

def extract_text_from_file(uploaded_file):
    """Extract plain text from txt, pdf, or docx."""
    file_type = uploaded_file.name.split(".")[-1].lower()
    text = ""
    
    try:
        if file_type == "txt":
            text = uploaded_file.read().decode("utf-8")
        elif file_type == "pdf":
            reader = PyPDF2.PdfReader(uploaded_file)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        elif file_type == "docx":
            doc = Document(uploaded_file)
            for para in doc.paragraphs:
                text += para.text + "\n"
    except Exception as e:
        return None, f"文件读取失败: {str(e)}"
        
    return text, None

def split_text_into_chunks(text, chunk_size=CHUNK_SIZE):
    """Split text into manageable chunks"""
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

def fetch_latest_catchphrases():
    """Fetch latest AI catchphrases from the web (Chinese-focused)"""
    try:
        results = DDGS().text("AI写作套话 AI口癖词 AI文章特征词 2025 常见套话", max_results=5)
        snippets = "\n".join([r['body'] for r in results])
        
        prompt = f"""
        从以下搜索结果中，提取 AI 写作中常见的中文口癖词汇、特征短语和套话。
        只返回逗号分隔的词语列表（例如："总而言之, 值得注意的是, 不可否认"）。
        不要包含任何解释，只返回中文词条。
        
        搜索结果:
        {snippets}
        """
        
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        new_phrases = response.choices[0].message.content.strip()
        new_phrases = new_phrases.replace('"', '').replace('\n', ',')
        return new_phrases
    except Exception as e:
        return f"Error: {str(e)}"

def analyze_chunk(chunk, chunk_id, total_chunks, catchphrases_str):
    try:
        system_prompt = (
            f"You are an AI text detection expert. You are analyzing chunk {chunk_id + 1}/{total_chunks}. "
            f"Focus on three distinct dimensions: language fingerprints, logic/context breaks, attention artifacts. "
            f"Catchphrase lexicon: {catchphrases_str}. "
            "Return strict JSON with keys: "
            "score (0-100, overall AI probability), "
            "rule1_score (0-100, language fingerprints & catchphrase density), "
            "rule2_score (0-100, logic and context inconsistencies), "
            "rule3_score (0-100, attention artifacts & pacing issues), "
            "key_issues (string list), evidence (string list)."
        )
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": chunk}
            ],
            response_format={"type": "json_object"}
        )
        res = json.loads(response.choices[0].message.content)
        if isinstance(res, list) and len(res) > 0:
            return res[0] if isinstance(res[0], dict) else {"score": 0, "error": "Invalid JSON list"}
        return res if isinstance(res, dict) else {"score": 0, "error": "Invalid JSON type"}
    except Exception as e:
        return {"score": 0, "rule1_score": 0, "rule2_score": 0, "rule3_score": 0, "key_issues": [f"Chunk error: {str(e)}"], "evidence": []}

def detect_catchphrases_regex(text, catchphrases_list, freq_threshold=1):
    """
    Use Regex to find exact matches of catchphrases in the text.
    Only positions for words that meet freq_threshold are returned for highlighting.
    Returns:
        - stats: List of dicts [{'word': 'xxx', 'count': N, 'above_threshold': bool}]
        - positions: List of dicts [{'word': 'xxx', 'start': N, 'end': N}] (threshold-filtered)
    """
    stats = {}
    all_word_positions = {}

    for phrase in catchphrases_list:
        phrase = phrase.strip()
        if not phrase: continue

        # Escape special regex chars
        pattern = re.escape(phrase)
        matches = list(re.finditer(pattern, text))

        if matches:
            stats[phrase] = len(matches)
            all_word_positions[phrase] = [
                {"word": phrase, "start": m.start(), "end": m.end()} for m in matches
            ]

    # Only include positions for words that met threshold (for highlighting)
    positions = []
    for phrase, count in stats.items():
        if count >= freq_threshold:
            positions.extend(all_word_positions[phrase])

    # Convert stats to list format with threshold flag
    stats_list = [
        {"word": k, "count": v, "above_threshold": v >= freq_threshold}
        for k, v in stats.items()
    ]
    stats_list.sort(key=lambda x: x['count'], reverse=True)

    return stats_list, positions

def calculate_text_metrics(text):
    """
    Calculate statistical metrics for AI detection:
    1. Burstiness (Sentence Length Standard Deviation)
    2. Perplexity Proxy (Type-Token Ratio via jieba for Chinese, or regex fallback)
    """
    if not text:
        return {"avg_len": 0, "std_dev_len": 0, "ttr": 0, "burstiness_score": 0, "perplexity_score": 0}

    # Split into sentences
    sentences = re.split(r'[.!?。！？]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return {"avg_len": 0, "std_dev_len": 0, "ttr": 0, "burstiness_score": 0, "perplexity_score": 0}

    # Calculate sentence lengths (in characters for Chinese/mixed)
    lengths = [len(s) for s in sentences]
    avg_len = sum(lengths) / len(lengths)

    # Standard Deviation (Burstiness)
    variance = sum((x - avg_len) ** 2 for x in lengths) / len(lengths)
    std_dev_len = math.sqrt(variance)

    # Type-Token Ratio (Perplexity Proxy - Repetitiveness)
    # Use jieba for Chinese word segmentation if available (avoids char-level TTR always = 1.0)
    chinese_char_count = len(re.findall(r'[\u4e00-\u9fff]', text))
    total_non_space = len(text.replace(' ', '').replace('\n', ''))
    is_chinese = total_non_space > 0 and chinese_char_count / total_non_space > 0.3

    if JIEBA_AVAILABLE and is_chinese:
        words = [w.strip() for w in jieba.cut(text) if w.strip() and not re.match(r'^\s+$', w)]
    elif is_chinese:
        # 2-gram proxy when jieba is unavailable
        words = list(re.findall(r'[\u4e00-\u9fff]{2}', text))
    else:
        words = re.findall(r'\w+', text)

    if not words:
        ttr = 0
    else:
        unique_words = set(words)
        ttr = len(unique_words) / len(words)

    # Normalize scores (0-100 scale for UI)
    burstiness_score = max(0, min(100, 100 - (std_dev_len - 5) * 4))
    perplexity_score = max(0, min(100, (0.7 - ttr) * 200))

    return {
        "avg_len": round(avg_len, 2),
        "std_dev_len": round(std_dev_len, 2),
        "ttr": round(ttr, 3),
        "burstiness_score": int(burstiness_score),
        "perplexity_score": int(perplexity_score),
        "jieba_used": JIEBA_AVAILABLE and is_chinese
    }

def highlight_text(text, positions):
    """
    Generate HTML with highlighted text based on positions.
    """
    if not positions:
        return text.replace("\n", "<br>")
        
    # Sort positions by start index
    positions.sort(key=lambda x: x['start'])
    
    # Merge overlapping intervals (simple approach: if overlap, skip/merge)
    # Since we are just highlighting, we can just insert spans. 
    # But for simplicity, let's process from end to start to avoid index shifting.
    
    highlighted_text = text
    # Reverse sort to handle index shifting
    positions.sort(key=lambda x: x['start'], reverse=True)
    
    for pos in positions:
        start = pos['start']
        end = pos['end']
        word = pos['word']
        
        # Insert span
        span = f"<span style='background-color: #ffcccc; color: #cc0000; font-weight: bold; padding: 0 2px; border-radius: 3px;' title='AI口癖: {word}'>{word}</span>"
        highlighted_text = highlighted_text[:start] + span + highlighted_text[end:]
        
    return highlighted_text.replace("\n", "<br>")

def aggregate_results(chunk_results):
    """Aggregate results from multiple chunks, tracking 3 dimensions independently."""
    total_score = 0
    rule1_total = 0
    rule2_total = 0
    rule3_total = 0
    all_issues = []
    all_evidence = []

    for res in chunk_results:
        s = res.get("score", 0)
        total_score += s
        rule1_total += res.get("rule1_score", s)
        rule2_total += res.get("rule2_score", s)
        rule3_total += res.get("rule3_score", s)
        all_issues.extend(res.get("key_issues", []))
        all_evidence.extend(res.get("evidence", []))

    n = len(chunk_results) if chunk_results else 1
    avg_score = total_score / n
    avg_rule1 = rule1_total / n
    avg_rule2 = rule2_total / n
    avg_rule3 = rule3_total / n

    # Determine intensity based on average score
    if avg_score < 30: intensity = "Level 1 (微量)"
    elif avg_score < 60: intensity = "Level 2 (辅助)"
    elif avg_score < 80: intensity = "Level 3 (生成)"
    else: intensity = "Level 4 (严重)"

    # Construct a Logic Graph from chunks for visualization
    # We map "AI Score" (High=Bad) to "Logic Score" (High=Good) roughly as (100 - score) / 10
    graph_nodes = []
    graph_transitions = []
    
    for i, res in enumerate(chunk_results):
        score = res.get("score", 0)
        issues = res.get("key_issues", [])
        short_issue = issues[0] if issues else "正常"
        
        # Create a node for this chunk
        node_name = f"§{i+1}: {short_issue[:10]}"
        graph_nodes.append(node_name)
        
        # Create transition from previous to current (except for first)
        if i > 0:
            # Previous score
            prev_score = chunk_results[i-1].get("score", 0)
            # Transition score: Average of health (inverse of AI score)
            # If AI score is 80, Health is 20. Logic Score ~ 2.
            avg_ai_score = (score + prev_score) / 2
            logic_score = max(0, min(10, (100 - avg_ai_score) / 10))
            
            graph_transitions.append({
                "source": i - 1,
                "target": i,
                "label": "承接",
                "score": round(logic_score, 1)
            })

    top_issues = ', '.join(all_issues[:5]) if all_issues else "无明显问题"
    return {
        "total_score": int(avg_score),
        "intensity_level": intensity,
        "summary": f"基于 {n} 个分段的综合分析。主要问题集中在: {top_issues}",
        "rule1_analysis": {"score": int(avg_rule1), "reason": "综合分段分析结果（语言指纹维度）", "evidence": all_evidence[:3]},
        "rule2_analysis": {"score": int(avg_rule2), "reason": "综合分段分析结果（逻辑连贯性维度）", "evidence": all_evidence[3:6]},
        "rule3_analysis": {"score": int(avg_rule3), "reason": "综合分段分析结果（注意力伪聚焦维度）", "evidence": all_evidence[6:9]},
        "full_evidence": all_evidence,
        "logic_graph": {
            "nodes": graph_nodes,
            "transitions": graph_transitions,
            "chunk_scores": [r.get("score", 0) for r in chunk_results]
        }
    }

def generate_markdown_report(result, text):
    """Generate a Markdown report from analysis results."""
    score = result.get("total_score", 0)
    intensity = result.get("intensity_level", "Unknown")
    summary = result.get("summary", "")
    r1 = result.get("rule1_analysis", {})
    r2 = result.get("rule2_analysis", {})
    r3 = result.get("rule3_analysis", {})
    metrics = result.get("text_metrics", {})
    catchphrase_stats = result.get("catchphrase_stats", [])
    top_phrases = "\n".join([f"- `{s['word']}`: {s['count']} 次" for s in catchphrase_stats[:10]]) or "未检测到显著口癖"
    ev1 = "\n".join([f"- {e}" for e in r1.get("evidence", [])]) or "无"
    ev2 = "\n".join([f"- {e}" for e in r2.get("evidence", [])]) or "无"
    ev3 = "\n".join([f"- {e}" for e in r3.get("evidence", [])]) or "无"
    jieba_flag = "✅ 已启用 (jieba)" if metrics.get("jieba_used") else "⚠️ 降级模式 (无 jieba)"
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""# AI 文本检测报告

> 由 **AI 文章含量检测工具 (Jianwen)** 生成 · {now}

## 综合评分

| 指标 | 结果 |
|---|---|
| **AI 疑似度** | {score}% |
| **强度评级** | {intensity} |

## 综合摘要

{summary}

## 详细分析

### 1. 语言指纹与口癖（得分: {r1.get('score', 0)}%）
**分析**: {r1.get('reason', '')}
**证据**:
{ev1}

### 2. 逻辑与上下文（得分: {r2.get('score', 0)}%）
**分析**: {r2.get('reason', '')}
**证据**:
{ev2}

### 3. 注意力机制伪聚焦（得分: {r3.get('score', 0)}%）
**分析**: {r3.get('reason', '')}
**证据**:
{ev3}

## 统计指标

| 指标 | 数值 |
|---|---|
| 平均句长 | {metrics.get('avg_len', 0)} 字符 |
| 句长标准差 (Burstiness) | {metrics.get('std_dev_len', 0)} |
| 词汇丰富度 (TTR) | {metrics.get('ttr', 0):.3f} |
| 中文分词 | {jieba_flag} |

## 高频 AI 口癖 Top 10

{top_phrases}

---
*检测工具: Jianwen · 生成时间: {now}*
"""


def analyze_text(text, freq_threshold, window_size):
    # Get custom catchphrases from session state or default
    catchphrases_str = st.session_state.get("custom_catchphrases", ", ".join(DEFAULT_CATCHPHRASES))
    catchphrases_list = sorted(list(set([p.strip() for p in catchphrases_str.split(",") if p.strip()])))

    # --- Cache check (same text + same threshold = skip LLM call) ---
    cache_key = hashlib.md5((text + str(freq_threshold)).encode("utf-8")).hexdigest()
    if "analysis_cache" not in st.session_state:
        st.session_state.analysis_cache = {}
    cached = st.session_state.analysis_cache.get(cache_key)
    if cached:
        return cached["result_str"], cached["positions"], cached["html"], True

    # 1. Python-side Regex Detection (Fast & Accurate, freq_threshold applied)
    regex_stats, regex_positions = detect_catchphrases_regex(text, catchphrases_list, freq_threshold)
    highlighted_html = highlight_text(text, regex_positions)

    # 2. Statistical Metrics Calculation (Burstiness & Perplexity Proxy)
    text_metrics = calculate_text_metrics(text)

    llm_result = {}

    if len(text) > CHUNK_SIZE * 1.5:
        # Long text mode: Chunking + Parallel Processing
        chunks = split_text_into_chunks(text)
        st.info(f"📄 文本较长，已自动拆分为 {len(chunks)} 个片段进行并行分析..")

        progress_bar = st.progress(0)
        results = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_chunk = {executor.submit(analyze_chunk, chunk, i, len(chunks), catchphrases_str): i for i, chunk in enumerate(chunks)}

            completed_count = 0
            for future in concurrent.futures.as_completed(future_to_chunk):
                try:
                    res = future.result()
                    results.append(res)
                except Exception as e:
                    st.error(f"Chunk processing failed: {e}")

                completed_count += 1
                progress_bar.progress(completed_count / len(chunks))

        llm_result = aggregate_results(results)

    else:
        system_prompt = (
            "You are an AI writing detector. Evaluate the text and return strict JSON. "
            "Signals: language fingerprints, logic/context breaks, attention artifacts. "
            f"Frequency threshold: > {freq_threshold} times in {window_size} chars. "
            f"Regex pre-check: {json.dumps(regex_stats, ensure_ascii=False)}. "
            f"Metrics: std_dev_len={text_metrics['std_dev_len']}, ttr={text_metrics['ttr']}, "
            f"burstiness_score={text_metrics['burstiness_score']}. "
            f"Catchphrase lexicon: {catchphrases_str}. "
            "Output keys: total_score, intensity_level, summary, "
            "rule1_analysis (score, reason, evidence list), "
            "rule2_analysis (score, reason, evidence list), "
            "rule3_analysis (score, reason, evidence list), "
            "logic_graph (nodes list, transitions list with source/target/label/score 0-10)."
        )

        user_prompt = f"Analyze this text:\n\n{text}"

        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}
            )
            llm_result = json.loads(response.choices[0].message.content)
            if isinstance(llm_result, list) and len(llm_result) > 0:
                llm_result = llm_result[0]
            if not isinstance(llm_result, dict):
                llm_result = {"error": "Invalid response format"}
        except Exception as e:
            return f"Error: {str(e)}", None, None, False

    # Robustness: Ensure llm_result is a dict (some models might return a list containing the dict)
    if isinstance(llm_result, list) and len(llm_result) > 0:
        llm_result = llm_result[0]
    
    if not isinstance(llm_result, dict):
        # Fallback if it's still not a dict
        llm_result = {"total_score": 0, "intensity_level": "Error", "summary": f"Unexpected LLM output format: {type(llm_result)}"}

    # Merge Regex stats & Text Metrics into LLM result
    llm_result["catchphrase_stats"] = regex_stats
    llm_result["text_metrics"] = text_metrics

    result_str = json.dumps(llm_result, ensure_ascii=False)

    # Save to cache
    st.session_state.analysis_cache[cache_key] = {
        "result_str": result_str,
        "positions": regex_positions,
        "html": highlighted_html
    }

    return result_str, regex_positions, highlighted_html, False


# Sidebar - What's New & Settings
with st.sidebar:
    st.image("https://img.icons8.com/color/96/artificial-intelligence.png", width=80)
    st.title("AI 检测工具 Pro")

    with st.expander("设置 (Settings)", expanded=False):
        st.write("自定义 AI 口癖词库")
        if "custom_catchphrases" not in st.session_state:
            st.session_state.custom_catchphrases = ", ".join(DEFAULT_CATCHPHRASES)

        catchphrases_input = st.text_area(
            "输入关键词（逗号分隔）",
            value=st.session_state.custom_catchphrases,
            height=150,
            help="可增删高频词，用于词频检测。",
            key="catchphrases_input_area"
        )

        if st.button("联网更新词库 (Search & Update)", help="抓取最新常见 AI 套话"):
            with st.spinner("正在联网搜索..."):
                new_phrases = fetch_latest_catchphrases()
                if "Error" in new_phrases:
                    st.error(f"更新失败: {new_phrases}")
                else:
                    current_set = set([p.strip() for p in st.session_state.custom_catchphrases.split(",") if p.strip()])
                    new_set = set([p.strip() for p in new_phrases.split(",") if p.strip()])
                    updated_set = current_set.union(new_set)
                    st.session_state.custom_catchphrases = ", ".join(sorted(list(updated_set)))
                    st.success(f"新增 {len(new_set - current_set)} 个词条")
                    st.rerun()

        if catchphrases_input != st.session_state.custom_catchphrases:
            st.session_state.custom_catchphrases = catchphrases_input
            st.success("词库已更新")

        st.divider()
        st.write("检测灵敏度")
        freq_threshold = st.slider(
            "词频阈值 (Frequency Threshold)",
            min_value=1,
            max_value=10,
            value=3,
            help="同一关键词在窗口内出现次数超过该值才标记。"
        )
        window_size = st.number_input(
            "窗口大小 (Window Size)",
            min_value=100,
            max_value=2000,
            value=500,
            step=100,
            help="统计词频时使用的字符窗口大小。"
        )

    st.info("检测维度：语言指纹、逻辑上下文、注意力伪聚焦")
    st.divider()
    st.write("Current Model")
    st.code(MODEL_NAME, language="text")

# Main Content
# Modern Hero Header
st.markdown("""
<div style="background: linear-gradient(135deg, #1f77b4 0%, #2ca02c 100%); padding: 30px; border-radius: 15px; margin-bottom: 25px; color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
    <h1 style="color: white !important; margin: 0; font-size: 2.5rem;">🔍 AI 文章含量深度鉴定</h1>
    <p style="opacity: 0.9; font-size: 1.1rem; margin-top: 10px;">基于 <b>语言指纹</b>、<b>逻辑连贯性</b>、<b>注意力机制伪聚焦</b> 的多维度深度鉴定工具</p>
</div>
""", unsafe_allow_html=True)

# Input Section
st.subheader("📝 待检测文本")
input_text = ""

# Session State for Text Area
if "input_content" not in st.session_state:
    st.session_state.input_content = ""

def load_example(example_type):
    if example_type == "high_ai":
        st.session_state.input_content = EXAMPLE_AI
        st.session_state.text_area_input = EXAMPLE_AI
    else:
        st.session_state.input_content = EXAMPLE_HUMAN
        st.session_state.text_area_input = EXAMPLE_HUMAN

tab_input_text, tab_input_file = st.tabs(["✍️ 文本粘贴", "📂 文件上传"])

with tab_input_text:
    col1, col2 = st.columns([3, 2])
    with col1:
        st.write("请粘贴文本，或加载示例文本进行检测。")
    with col2:
        example_option = st.selectbox(
            "选择示例类型",
            ["高 AI 含量文本 (AI Text)", "人类写作文本 (Human Text)"],
            index=0,
            label_visibility="collapsed"
        )
        if st.button("加载选中示例", help="将示例填充到输入框"):
            if "AI" in example_option:
                load_example("high_ai")
            else:
                load_example("human")
            st.rerun()

    input_text_raw = st.text_area(
        "在此粘贴文本",
        value=st.session_state.input_content,
        height=200,
        placeholder="建议输入不少于 500 字，以获得更稳定结果。",
        key="text_area_input"
    )
    
    # Sync manual input back to session state if needed (optional, but good practice if mixed)
    if input_text_raw:
        input_text = input_text_raw
        st.session_state.input_content = input_text_raw

with tab_input_file:
    uploaded_file = st.file_uploader("上传文件 (支持 TXT / PDF / DOCX)", type=["txt", "pdf", "docx"])
    if uploaded_file is not None:
        text, error = extract_text_from_file(uploaded_file)
        if error:
            st.error(error)
        else:
            input_text = text
            st.success(f"已加载文件：{uploaded_file.name}（{len(input_text)} 字符）")
            if len(input_text) > 100000:
                st.warning(f"文本很长（{len(input_text)} 字符），建议分段检测。")
            elif len(input_text) > 50000:
                st.warning(f"文本较长（{len(input_text)} 字符），分析可能耗时更久。")

# Analysis Button
if st.button("开始深度鉴定", type="primary", use_container_width=True):
    if not input_text:
        st.warning("请先输入文本或上传文件。")
    else:
        with st.spinner("正在进行多维度分析，请稍候..."):
            result_str, regex_positions, highlighted_html, is_from_cache = analyze_text(input_text, freq_threshold, window_size)
            
            if is_from_cache:
                st.toast("⚡ 已加载缓存结果", icon="✅")

            if result_str.startswith("Error"):
                st.error(result_str)
            else:
                try:
                    result = json.loads(result_str)
                    
                    # --- Results Display ---
                    
                    # 1. Top Metrics with Gauge
                    st.divider()
                    score = result.get("total_score", 0)
                    intensity = result.get("intensity_level", "Unknown")
                    
                    col_score, col_meta = st.columns([1.5, 2])
                    
                    with col_score:
                        # Circular Gauge for AI Risk
                        fig_gauge = go.Figure(go.Indicator(
                            mode = "gauge+number",
                            value = score,
                            domain = {'x': [0, 1], 'y': [0, 1]},
                            title = {'text': "AI 疑似度", 'font': {'size': 24}},
                            number = {'suffix': "%", 'font': {'size': 40}},
                            gauge = {
                                'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "darkblue"},
                                'bar': {'color': "#1f77b4"},
                                'bgcolor': "white",
                                'borderwidth': 2,
                                'bordercolor': "gray",
                                'steps': [
                                    {'range': [0, 30], 'color': '#eaf7ee'},
                                    {'range': [30, 70], 'color': '#fff6e5'},
                                    {'range': [70, 100], 'color': '#fdecea'}],
                                'threshold': {
                                    'line': {'color': "red", 'width': 4},
                                    'thickness': 0.75,
                                    'value': 80}}))
                        
                        fig_gauge.update_layout(height=300, margin=dict(l=30, r=30, t=50, b=20), paper_bgcolor='rgba(0,0,0,0)')
                        st.plotly_chart(fig_gauge, use_container_width=True)

                    with col_meta:
                        st.markdown(f"### 鉴定结论: <span style='color: #1f77b4;'>{intensity.split('(')[0]}</span>", unsafe_allow_html=True)
                        st.markdown(f"**风险评级**: {intensity.split('(')[-1].replace(')', '') if '(' in intensity else intensity}")
                        
                        # Summary Box
                        st.info(result.get("summary"))
                        
                        # Export Button
                        report_md = generate_markdown_report(result, input_text)
                        st.download_button(
                            label="📥 导出分析报告 (Markdown)",
                            data=report_md,
                            file_name=f"AI_Detection_Report_{hashlib.md5(input_text[:20].encode()).hexdigest()[:8]}.md",
                            mime="text/markdown",
                            use_container_width=True
                        )

                    # 2. Detailed Analysis Tabs
                    st.divider()
                    tab_charts, tab_highlight, tab_deep, tab_method = st.tabs(["📊 酷炫图表 (Charts)", "🖍️ 文本高亮 (Highlight)", "🔍 深度分析 (Analysis)", "📖 方法论 (Methodology)"])
                    
                    with tab_charts:
                        st.subheader("AI 特征多维可视化")
                        
                        # Display Statistical Metrics
                        metrics = result.get("text_metrics", {})
                        m1, m2, m3 = st.columns(3)
                        m1.metric("平均句长 (Avg Len)", f"{metrics.get('avg_len', 0)} 词", help="AI 生成文本通常句长适中且平均")
                        m2.metric("句子长度标准差 (Burstiness)", f"{metrics.get('std_dev_len', 0)}", delta="高 (Human)" if metrics.get('std_dev_len', 0) > 20 else "低 (AI)", delta_color="normal" if metrics.get('std_dev_len', 0) > 20 else "inverse", help="标准差越高，代表句式变化越丰富（人类特征）")
                        m3.metric("词汇丰富度 (TTR)", f"{metrics.get('ttr', 0):.3f}", delta="高 (Human)" if metrics.get('ttr', 0) > 0.5 else "低 (AI)", delta_color="normal" if metrics.get('ttr', 0) > 0.5 else "inverse", help="Type-Token Ratio: 唯一词汇占比")
                        
                        st.divider()
                        
                        col_chart1, col_chart2 = st.columns(2)
                        
                        with col_chart1:
                            # 1. Radar Chart (Plotly)
                            # Update categories to include statistical metrics
                            categories = ['语言指纹', '逻辑上下文', '注意力伪聚焦', '低爆发度(AI)', '重复度(AI)']
                            
                            # Get metrics safely
                            metrics = result.get("text_metrics", {})
                            burst_score = metrics.get("burstiness_score", 50) # Default mid
                            perp_score = metrics.get("perplexity_score", 50)
                            
                            r_values = [
                                result.get("rule1_analysis", {}).get("score", 0),
                                result.get("rule2_analysis", {}).get("score", 0),
                                result.get("rule3_analysis", {}).get("score", 0),
                                burst_score,
                                perp_score
                            ]
                            
                            # Hover descriptions for Radar Chart
                            radar_descriptions = [
                                "分析词汇选择、句式结构等语言统计特征",
                                "检测上下文逻辑连贯性、感官描写深度",
                                "识别无效细节描写和注意力分散现象",
                                "句子长度变化少，节奏单调（AI特征）",
                                "文本困惑度低，缺乏惊喜欢度（AI特征）"
                            ]
                            
                            # Close the loop
                            r_values.append(r_values[0])
                            categories.append(categories[0])
                            radar_descriptions.append(radar_descriptions[0])
                            
                            fig_radar = go.Figure()
                            fig_radar.add_trace(go.Scatterpolar(
                                r=r_values,
                                theta=categories,
                                fill='toself',
                                name='AI 特征值',
                                line_color='#1f77b4',
                                fillcolor='rgba(31, 119, 180, 0.2)',
                                hovertemplate='<b>%{theta}</b><br>得分: %{r}<br>%{customdata}<extra></extra>',
                                customdata=radar_descriptions
                            ))
                            fig_radar.update_layout(
                                polar=dict(
                                    radialaxis=dict(visible=True, range=[0, 100], showline=False, gridcolor='rgba(0,0,0,0.1)'),
                                    angularaxis=dict(gridcolor='rgba(0,0,0,0.1)'),
                                    bgcolor='rgba(0,0,0,0)'
                                ),
                                showlegend=False,
                                title=dict(text="🛡️ AI 特征多维雷达图", font=dict(color='#31333F')),
                                height=350,
                                margin=dict(l=40, r=40, t=40, b=40),
                                paper_bgcolor='rgba(0,0,0,0)',
                                font=dict(color='#31333F')
                            )
                            st.plotly_chart(fig_radar, use_container_width=True)

                        with col_chart2:
                            # 2. Catchphrase Frequency Bar Chart (Plotly)
                            catchphrase_stats = result.get("catchphrase_stats", [])
                            if catchphrase_stats:
                                df_freq = pd.DataFrame(catchphrase_stats)
                                # Color bars differently if below threshold
                                fig_bar = px.bar(
                                    df_freq, 
                                    x='count', 
                                    y='word', 
                                    orientation='h',
                                    title="⚠️ AI 口癖频次 (颜色代表是否超阈值)",
                                    labels={'count': '出现频次', 'word': '口癖词汇'},
                                    color='above_threshold',
                                    color_discrete_map={True: '#1f77b4', False: '#d3d3d3'},
                                    template="plotly_white"
                                )
                                fig_bar.update_traces(
                                    hovertemplate='<b>%{y}</b><br>出现次数: %{x}<br>状态: %{customdata}<extra></extra>',
                                    customdata=["超阈值 (高风险)" if val else "未达阈值 (低关注)" for val in df_freq['above_threshold']]
                                )
                                fig_bar.update_layout(
                                    height=350, 
                                    yaxis={'categoryorder':'total ascending'},
                                    showlegend=False,
                                    plot_bgcolor='rgba(0,0,0,0)',
                                    paper_bgcolor='rgba(0,0,0,0)',
                                    font=dict(color='#31333F')
                                )
                                st.plotly_chart(fig_bar, use_container_width=True)
                            else:
                                st.info("✅ 未检测到显著的高频 AI 口癖。")

                        # 3. Burstiness Scatter Plot (Distribution)
                        st.subheader("📊 AI 口癖分布密度 (Burstiness Analysis)")
                        if regex_positions:
                            df_pos = pd.DataFrame(regex_positions)
                            # Add a jitter or dummy y-axis for simple 1D distribution
                            df_pos['y'] = 1 
                            
                            fig_scatter = px.scatter(
                                df_pos, 
                                x='start', 
                                y='word', 
                                color='word', 
                                title="📍 AI 特征词在文本中的分布位置",
                                labels={'start': '文本字符位置', 'word': '检测到的词汇'},
                                opacity=0.7,
                                template="plotly_white"
                            )
                            fig_scatter.update_traces(
                                marker=dict(size=10, symbol='circle', line=dict(width=1, color='Gray')),
                                hovertemplate='<b>%{y}</b><br>位置: %{x}<br>说明: 密集分布可能暗示AI生成的重复模式<extra></extra>'
                            )
                            fig_scatter.update_layout(
                                xaxis=dict(title='文本进度 (字符位置)', showgrid=False),
                                yaxis=dict(categoryorder='category ascending', showgrid=True, gridcolor='rgba(0,0,0,0.1)'),
                                showlegend=False,
                                height=400,
                                hovermode="closest",
                                plot_bgcolor='rgba(0,0,0,0)',
                                paper_bgcolor='rgba(0,0,0,0)',
                                font=dict(color='#31333F')
                            )
                            st.plotly_chart(fig_scatter, use_container_width=True)
                        else:
                            st.info("无特征词分布数据。")

                    with tab_highlight:
                        st.subheader("🖍️ 全文 AI 特征高亮")
                        st.caption("红色高亮部分为检测到的疑似 AI 口癖或特征词汇。")
                        
                        html_box = (
                            "<div style='border:1px solid #ddd;padding:20px;border-radius:5px;"
                            "background-color:#f9f9f9;max-height:600px;overflow-y:auto;"
                            "line-height:1.6;font-family:sans-serif;'>"
                            + highlighted_html +
                            "</div>"
                        )
                        st.markdown(html_box, unsafe_allow_html=True)

                    with tab_deep:
                        st.subheader("综合评价")
                        st.info(result.get("summary"))
                        
                        # Rule 1
                        r1 = result.get("rule1_analysis", {})
                        with st.expander(f"1. 语言指纹与口癖 (得分: {r1.get('score')}%)", expanded=True):
                            st.write(f"**分析**: {r1.get('reason')}")
                            st.caption("检测重点: 语言爆发度 (Burstiness), 文本困惑度 (Perplexity), 特定口癖词库")
                            if r1.get("evidence"):
                                st.error(f"❌ 发现特征: {', '.join(r1.get('evidence'))}")
                            else:
                                st.success("✅ 未发现明显 AI 口癖特征")

        # Logic flow visualization (optimized)
                        with st.expander("🧬 逻辑脉络 DNA 图谱 (Logic DNA Map)", expanded=True):
                            st.caption("横轴是文本推进阶段，纵轴是逻辑健康度（越高越连贯）。")

                            logic_graph = result.get("logic_graph", {})
                            nodes = logic_graph.get("nodes", [])
                            transitions = logic_graph.get("transitions", [])
                            chunk_scores = logic_graph.get("chunk_scores", [])

                            if not nodes:
                                paras = [p for p in input_text.split('\n') if len(p.strip()) > 50]
                                if 2 <= len(paras) <= 15:
                                    nodes = [f"段落 {i+1}: {p[:12]}..." for i, p in enumerate(paras)]
                                else:
                                    nodes = ["开场", "观点提出", "论据展开", "推理收束", "结论"]

                            node_count = len(nodes)
                            if node_count == 0:
                                st.info("暂无可视化节点数据。")
                            else:
                                cleaned_transitions = []
                                for t in transitions:
                                    try:
                                        src = int(t.get("source", -1))
                                        tgt = int(t.get("target", -1))
                                        score = float(t.get("score", 5))
                                        score = max(0.0, min(10.0, score))
                                    except (TypeError, ValueError):
                                        continue
                                    if 0 <= src < node_count and 0 <= tgt < node_count and src != tgt:
                                        cleaned_transitions.append({
                                            "source": src,
                                            "target": tgt,
                                            "score": score,
                                            "label": str(t.get("label", "过渡"))
                                        })

                                node_health = [6.0] * node_count
                                if chunk_scores and len(chunk_scores) == node_count:
                                    parsed_scores = []
                                    for s in chunk_scores:
                                        try:
                                            parsed_scores.append(max(0.0, min(10.0, (100 - float(s)) / 10.0)))
                                        except (TypeError, ValueError):
                                            parsed_scores.append(6.0)
                                    node_health = parsed_scores
                                elif cleaned_transitions:
                                    incoming = [[] for _ in range(node_count)]
                                    outgoing = [[] for _ in range(node_count)]
                                    for t in cleaned_transitions:
                                        outgoing[t["source"]].append(t["score"])
                                        incoming[t["target"]].append(t["score"])
                                    for i in range(node_count):
                                        local = incoming[i] + outgoing[i]
                                        if local:
                                            node_health[i] = sum(local) / len(local)
                                else:
                                    r2 = float(result.get("rule2_analysis", {}).get("score", 0))
                                    r3 = float(result.get("rule3_analysis", {}).get("score", 0))
                                    base = max(1.0, min(9.0, 8.5 - (r2 + r3) / 25.0))
                                    node_health = [base] * node_count

                                transitions_for_plot = cleaned_transitions[:]
                                if not transitions_for_plot and node_count >= 2:
                                    for i in range(node_count - 1):
                                        transitions_for_plot.append({
                                            "source": i,
                                            "target": i + 1,
                                            "score": (node_health[i] + node_health[i + 1]) / 2.0,
                                            "label": "顺序推进"
                                        })

                                node_x = [i + 1 for i in range(node_count)]
                                node_text = []
                                node_hover = []
                                for i, name in enumerate(nodes):
                                    short_name = f"{name[:10]}..." if len(name) > 10 else name
                                    status = "顺畅" if node_health[i] >= 7 else ("存疑" if node_health[i] >= 4 else "断层")
                                    node_text.append(f"{i+1}. {short_name}")
                                    node_hover.append(
                                        f"<b>{name}</b><br>阶段: {i+1}/{node_count}<br>健康度: {node_health[i]:.1f}/10<br>状态: {status}"
                                    )

                                fig_logic = go.Figure()
                                fig_logic.add_hrect(y0=0, y1=4, fillcolor="#fdecea", opacity=0.55, layer="below", line_width=0)
                                fig_logic.add_hrect(y0=4, y1=7, fillcolor="#fff6e5", opacity=0.55, layer="below", line_width=0)
                                fig_logic.add_hrect(y0=7, y1=10, fillcolor="#eaf7ee", opacity=0.55, layer="below", line_width=0)

                                for t in transitions_for_plot:
                                    ts = t["score"]
                                    edge_color = "#2ca02c" if ts >= 7 else ("#ff7f0e" if ts >= 4 else "#d62728")
                                    fig_logic.add_trace(go.Scatter(
                                        x=[node_x[t["source"]], node_x[t["target"]]],
                                        y=[node_health[t["source"]], node_health[t["target"]]],
                                        mode="lines",
                                        line=dict(color=edge_color, width=1.8 + ts * 0.25, dash="dot" if ts < 5 else "solid"),
                                        hovertemplate=f"过渡: {t['label']}<br>评分: {ts:.1f}/10<extra></extra>",
                                        showlegend=False
                                    ))

                                fig_logic.add_trace(go.Scatter(
                                    x=node_x,
                                    y=node_health,
                                    mode="markers+text",
                                    text=node_text,
                                    textposition="top center",
                                    marker=dict(
                                        size=[24 if h < 4 else 18 for h in node_health],
                                        color=node_health,
                                        colorscale="RdYlGn",
                                        cmin=0,
                                        cmax=10,
                                        line=dict(width=1.8, color="white")
                                    ),
                                    hovertemplate="%{hovertext}<extra></extra>",
                                    hovertext=node_hover,
                                    showlegend=False
                                ))

                                avg_health = sum(node_health) / node_count
                                weak_nodes = sum(1 for h in node_health if h < 4)
                                weakest_link_score = min([t["score"] for t in transitions_for_plot], default=avg_health)

                                k1, k2, k3 = st.columns(3)
                                k1.metric("平均健康度", f"{avg_health:.1f}/10")
                                k2.metric("低健康节点", f"{weak_nodes} 个")
                                k3.metric("最弱过渡", f"{weakest_link_score:.1f}/10")

                                weakest_links = sorted(transitions_for_plot, key=lambda x: x["score"])[:3]
                                if weakest_links:
                                    weak_text = []
                                    for t in weakest_links:
                                        weak_text.append(
                                            f"- 第 {t['source']+1} → {t['target']+1} 阶段（{t['label']}）：{t['score']:.1f}/10"
                                        )
                                    st.markdown("**薄弱衔接 Top 3**")
                                    st.markdown("\n".join(weak_text))

                                # Add background quality bands (Intuitive zones)
                                fig_logic.add_hrect(y0=0, y1=4, fillcolor="#FFEBEE", opacity=0.3, layer="below", line_width=0)
                                fig_logic.add_hrect(y0=4, y1=7, fillcolor="#FFF3E0", opacity=0.3, layer="below", line_width=0)
                                fig_logic.add_hrect(y0=7, y1=10.5, fillcolor="#E8F5E9", opacity=0.3, layer="below", line_width=0)

                                fig_logic.update_layout(
                                    title=dict(text="🧬 逻辑脉络健康轨迹图 (Logic DNA)", font=dict(size=18, color='#1f77b4')),
                                    height=max(400, 300 + node_count * 20),
                                    xaxis=dict(
                                        title="文本推进阶段 (Sections)",
                                        range=[0.5, node_count + 0.5],
                                        tickvals=node_x,
                                        ticktext=[f"阶段{i}" for i in node_x],
                                        showgrid=False,
                                        zeroline=False
                                    ),
                                    yaxis=dict(
                                        title="逻辑健康度 (0-10)",
                                        range=[0, 10.5],
                                        tickvals=[2, 5.5, 8.8],
                                        ticktext=["❌ 断层", "⚠️ 存疑", "✅ 顺畅"],
                                        gridcolor="rgba(0,0,0,0.05)",
                                        zeroline=False
                                    ),
                                    plot_bgcolor="rgba(0,0,0,0)",
                                    paper_bgcolor="rgba(0,0,0,0)",
                                    font=dict(family="Segoe UI", size=13),
                                    margin=dict(l=40, r=40, t=60, b=40),
                                    showlegend=False
                                )

                                # Annotations for clarity
                                fig_logic.add_annotation(x=0.55, y=2, text="高危断层区", showarrow=False, font=dict(color="#C62828", size=10), xanchor="left")
                                fig_logic.add_annotation(x=0.55, y=5.5, text="逻辑存疑区", showarrow=False, font=dict(color="#EF6C00", size=10), xanchor="left")
                                fig_logic.add_annotation(x=0.55, y=8.8, text="逻辑顺畅区", showarrow=False, font=dict(color="#2E7D32", size=10), xanchor="left")

                                st.plotly_chart(fig_logic, use_container_width=True)

                        # Rule 2
                        r2 = result.get("rule2_analysis", {})
                        with st.expander(f"2. 逻辑与上下文 (得分: {r2.get('score')}%)", expanded=True):
                            st.write(f"**分析**: {r2.get('reason')}")
                            st.caption("检测重点: 感官断层 (Sensory Disconnect), 角色崩坏 (OOC), 逻辑前后矛盾")
                            if r2.get("evidence"):
                                st.error(f"❌ 发现特征: {', '.join(r2.get('evidence'))}")

                        # Rule 3
                        r3 = result.get("rule3_analysis", {})
                        with st.expander(f"3. 注意力机制伪聚焦 (得分: {r3.get('score')}%)", expanded=True):
                            st.write(f"**分析**: {r3.get('reason')}")
                            st.caption("检测重点: 碎片化无关性 (Fractal Irrelevance), 香炉烟效应, 叙事节奏失衡")
                            if r3.get("evidence"):
                                st.error(f"❌ 发现特征: {', '.join(r3.get('evidence'))}")

                    with tab_method:
                        st.markdown("""
                        ### 核心鉴定体系 (Methodology v3.0 - Enhanced)
                        
                        本工具结合了 **LLM 深度语义分析** 与 **统计学特征工程**，参考了 GLTR、GPTZero 等先进检测理念。
                        
                        #### 1. 统计学特征 (Statistical Metrics)
                        *   **Burstiness (爆发度/句子标准差)**: 
                            *   **原理**: 人类写作时句式长短不一，情绪波动大；AI 模型受限于概率最大化，生成的句子长度倾向于平均。
                            *   **指标**: 句子长度标准差 (Std Dev)。> 20 通常为人类特征。
                        *   **Perplexity Proxy (困惑度/词汇丰富度)**:
                            *   **原理**: AI 倾向于使用高频词汇以降低预测错误率。
                            *   **指标**: Type-Token Ratio (TTR)。数值越低，代表词汇重复率越高，AI 嫌疑越大。
                        
                        #### 2. 语言指纹 (Linguistic Fingerprints)
                        *   **特定口癖**: 检测 "投石入水", "交响曲", "织锦" 等 RLHF (Reinforcement Learning from Human Feedback) 训练过程中产生的高频安全词汇。
                        *   **结构僵化**: "首先...其次...最后...", "总而言之" 等八股文结构。
                        
                        #### 3. 逻辑与上下文 (Logic & Context)
                        *   **Sensory Disconnect (感官断层)**: AI 缺乏真实身体体验，描写往往局限于视觉，缺乏触觉、嗅觉、温度感。
                        *   **Hallucination**: 事实性错误或逻辑跳跃。
                        
                        #### 4. 注意力机制伪聚焦 (Attention Artifacts)
                        *   **Fractal Irrelevance (碎片化无关性)**: 对背景物体（如 墙上的裂缝）进行无限递归的细节描写，忽略主线剧情。
                        *   **Pacing**: 叙事节奏的崩溃。
                        """)

                except json.JSONDecodeError:
                    st.error("解析结果失败，LLM 返回格式有误。")
                    st.text(result_str)
