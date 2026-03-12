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
        "words": [
            "眼神", "嘴角", "睫毛", "空洞", "鼻音", "哭腔", "狡黠", "沙哑", "低沉", 
            "微微挑眉", "微微上扬", "波涛汹涌", "深邃", "热切", "毫不遮掩", "不卑不亢", 
            "锐利", "不易察觉", "眼神暗了暗", "瞳孔缩成针尖", "喉结滚了滚"
        ],
        "logic": "避免主观神态解读，强制客观描写"
    },
    "动作修饰类": {
        "words": [
            "泛白", "发白", "攥紧", "绷紧", "凝滞", "闪过", "投入", "呜咽", "擂鼓", 
            "勾起", "炸开", "深吸一口气", "缓缓地说", "猛地", "闪烁", "裹挟", "扭曲", 
            "撕裂", "洇出墨团", "无意识的摩挲", "指尖发白", "指尖发麻", "指尖发冷", 
            "手指", "指节", "划过第x行"
        ],
        "logic": "防止过度聚焦微观动作，如手指特写"
    },
    "心理活动类": {
        "words": [
            "心中一凛", "心下了然", "一时间", "隐隐有了猜测", "心中一片平静", 
            "心中一动", "不动声色", "小心翼翼", "沉吟片刻", "意识到", "感觉到", 
            "心跳"
        ],
        "logic": "避免直接描写心理状态，提倡通过行为表现"
    },
    "俗套夸张类": {
        "words": [
            "行云流水", "不可估量", "无法想象", "无法用言语形容", "淬了毒的匕首", 
            "目瞪口呆", "能塞下一个鸡蛋", "还要冰冷", "透露出的寒意", "下降了几度", 
            "显得更加……", "xx的眼神", "嘴角勾起一个……的弧度", "……看得目瞪口呆", 
            "像在看一个……的人", "幼兽般的呜咽"
        ],
        "logic": "避免网文或AI常用的陈腐夸张修辞"
    },
    "逻辑连接类": {
        "words": [
            "取而代之的是", "接下来", "话锋一转", "由此可见", "换言之", "总而言之", 
            "值得注意的是", "不可否认", "这一刻", "这一次", "再次", "首先...其次...最后...", 
            "某种意义上", "简而言之", "归根结底", "不仅...而且...", "一方面...另一方面...", 
            "当...突然"
        ],
        "logic": "减少僵化的逻辑连接词"
    },
    "抽象词汇类": {
        "words": [
            "复杂的", "多层面的", "核心", "关键", "框架", "机制", "模式", "体系", 
            "赋能", "驱动", "引领", "重塑", "革新", "突破", "挑战", "机遇", "趋势", 
            "愿景", "蜕变", "终极", "隐喻", "暗喻", "公式"
        ],
        "logic": "减少AI常用的宏大叙事或商业黑话"
    },
    "特定名词类": {
        "words": [
            "第三根肋骨", "皮带扣", "第三颗纽扣", "第三根手指", "钢笔", "纽扣", 
            "第三（次/个/重...）", "防冻液", "冷却液", "电解液", "电子流", "磁悬浮"
        ],
        "logic": "针对特定套路化细节或科技词汇的检测"
    },
    "抽象感知类": {
        "words": [
            "感到", "知道", "复杂", "生理性", "难以言喻", "四肢百骸", "清冷", 
            "沸腾", "漆黑", "窒息", "剧痛", "纯粹", "喧嚣", "静谧"
        ],
        "logic": "将抽象情绪转化为可观察行为"
    },
    "比喻禁用类": {
        "words": [
            "羽毛", "湖面", "心湖", "涟漪", "石子", "手术刀", "弓弦", "投石入水", 
            "交响曲", "不是X而是X"
        ],
        "logic": "避免陈腐比喻"
    },
    "程度修饰类": {
        "words": [
            "几分", "一丝", "某种", "近乎", "微不可查", "几不可察", "难以置信", 
            "不容置疑"
        ],
        "logic": "减少不确定性或过度修饰表达"
    }
}

DEFAULT_CATCHPHRASES = [] # Will be populated by loop below

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

# Custom CSS for "Vintage Paper" theme
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700&family=IM+Fell+English:ital@0;1&family=Noto+Serif+SC:wght@400;700&display=swap');

    /* Global Background & Text */
    .stApp {
        background-color: #F2E8D5;
        background-image: url("https://www.transparenttextures.com/patterns/aged-paper.png");
        color: #3e2723;
        font-family: 'IM Fell English', 'Noto Serif SC', serif;
    }

    /* Titles & Headers */
    h1, h2, h3, h4, h5, h6 {
        color: #5d4037 !important;
        font-family: 'Cinzel', 'Noto Serif SC', serif !important;
        font-weight: 700;
        text-shadow: 1px 1px 0px rgba(255,255,255,0.5);
    }

    /* Metric Values */
    [data-testid="stMetricValue"] {
        color: #8B4513;
        font-family: 'Cinzel', serif;
        font-size: 2.2rem !important;
    }
    
    [data-testid="stMetricLabel"] {
        color: #5d4037;
        font-family: 'Noto Serif SC', serif;
        font-weight: bold;
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #E6DCC3;
        border-right: 2px solid #8B4513;
        box-shadow: 2px 0 5px rgba(0,0,0,0.1);
    }
    
    /* Buttons - Vintage Style */
    .stButton>button {
        background: linear-gradient(to bottom, #fdfbf7, #e6dcc3);
        color: #3e2723;
        border: 2px solid #8B4513;
        border-radius: 4px;
        box-shadow: 2px 2px 0px #8B4513;
        transition: all 0.1s ease-in-out;
        font-family: 'Noto Serif SC', serif;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .stButton>button:hover {
        background: #fdfbf7;
        transform: translate(1px, 1px);
        box-shadow: 1px 1px 0px #8B4513;
        color: #8B4513;
        border-color: #5d4037;
    }
    .stButton>button:active {
        transform: translate(2px, 2px);
        box-shadow: none;
    }

    /* Text Areas & Inputs */
    .stTextArea>div>div>textarea, .stTextInput>div>div>input {
        background-color: #fdfbf7;
        color: #3e2723;
        border: 2px solid #8B4513;
        border-radius: 2px;
        font-family: 'Noto Serif SC', serif;
        box-shadow: inset 1px 1px 3px rgba(0,0,0,0.1);
    }
    .stTextArea>div>div>textarea:focus, .stTextInput>div>div>input:focus {
        border-color: #CD5C5C;
        box-shadow: 0 0 5px rgba(205, 92, 92, 0.3);
    }

    /* Cards/Containers/Expanders */
    div[data-testid="stExpander"] {
        background-color: #fdfbf7;
        border: 2px solid #8B4513;
        border-radius: 4px;
        box-shadow: 3px 3px 0px rgba(139, 69, 19, 0.2);
    }
    
    div[data-testid="stExpander"] details {
        border-radius: 4px;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background-color: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #E6DCC3;
        border: 1px solid #8B4513;
        border-bottom: none;
        border-radius: 4px 4px 0 0;
        color: #5d4037;
        font-family: 'Noto Serif SC', serif;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: #fdfbf7;
        border-bottom: 2px solid #fdfbf7;
        font-weight: bold;
    }
    
    /* Success/Warning/Error Messages */
    .stAlert {
        background-color: #fdfbf7;
        border: 2px solid #8B4513;
        color: #3e2723;
        font-family: 'Noto Serif SC', serif;
        box-shadow: 2px 2px 0px rgba(0,0,0,0.1);
    }
    
    /* Progress Bar */
    .stProgress > div > div > div > div {
        background-image: linear-gradient(to right, #8B4513, #CD5C5C);
        border: 1px solid #3e2723;
    }

    /* Custom Scrollbar */
    ::-webkit-scrollbar {
        width: 10px;
        background: #E6DCC3;
    }
    ::-webkit-scrollbar-thumb {
        background: #8B4513;
        border-radius: 5px;
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
            f"你是一位 AI 文本检测专家。你正在分析第 {chunk_id + 1}/{total_chunks} 个文本片段。 "
            "请从以下三个维度进行分析：语言指纹（Language Fingerprints）、逻辑与上下文断层（Logic/Context Breaks）、注意力机制伪聚焦（Attention Artifacts）。"
            f"参考口癖词库：{catchphrases_str}。 "
            "请返回严格的 JSON 格式，包含以下字段： "
            "score (0-100, 整体 AI 疑似度分数), "
            "rule1_score (0-100, 语言指纹与口癖密度得分), "
            "rule2_score (0-100, 逻辑不一致与感官冲突得分), "
            "rule3_score (0-100, 注意力伪聚焦与节奏问题得分), "
            "key_issues (字符串列表，描述发现的主要问题), "
            "evidence (字符串列表，提供具体的文本证据)。"
            "所有返回内容（key_issues, evidence）必须使用中文。"
        )
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": chunk}
            ],
            response_format={"type": "json_object"}
        )
        raw_content = response.choices[0].message.content
        res = json.loads(raw_content)
        if isinstance(res, list) and len(res) > 0:
            res = res[0]
        return res if isinstance(res, dict) else {"score": 0, "rule1_score": 0, "rule2_score": 0, "rule3_score": 0, "key_issues": ["Unexpected JSON format"], "evidence": []}
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

        # Handle wildcards
        pattern = re.escape(phrase)
        pattern = pattern.replace(re.escape("……"), ".{1,10}")
        pattern = pattern.replace(re.escape("xx"), ".{1,10}")
        
        # Handle custom regex patterns like "第三（次/个/重...）"
        if "（" in phrase and "）" in phrase and "/" in phrase:
            # Extract content inside brackets
            inner = re.search(r'（(.*?)）', phrase)
            if inner:
                options = inner.group(1).split('/')
                # Escape options and join with |
                regex_options = f"({'|'.join([re.escape(opt.replace('...', '')) for opt in options])})"
                # Replace the bracket part with regex options
                pattern = re.sub(r'\\（.*?\\）', regex_options, pattern)
                # Handle the trailing ... if it was inside
                pattern = pattern.replace(re.escape("..."), ".*?")

        try:
            matches = list(re.finditer(pattern, text))
        except re.error:
            # Fallback to literal if regex is invalid
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
    if avg_score < 30: intensity = "第 1 级 (微量 AI 痕迹)"
    elif avg_score < 60: intensity = "第 2 级 (疑似辅助生成)"
    elif avg_score < 80: intensity = "第 3 级 (高度疑似 AI 生成)"
    else: intensity = "第 4 级 (确认为 AI 生成)"

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
            "你是一位专业的 AI 文本检测专家。请评估输入的文本并返回严格的 JSON 格式。 "
            "评估信号：语言指纹、逻辑/上下文断层、注意力机制伪聚焦。 "
            f"词频阈值：在 {window_size} 字符窗口内出现超过 {freq_threshold} 次。 "
            f"正则预检结果: {json.dumps(regex_stats, ensure_ascii=False)}。 "
            f"统计指标: 句长标准差={text_metrics['std_dev_len']}, 词汇丰富度={text_metrics['ttr']}, "
            f"爆发度得分={text_metrics['burstiness_score']}。 "
            f"参考词库: {catchphrases_str}。 "
            "输出 JSON 的键名必须为：total_score, intensity_level, summary, "
            "rule1_analysis (包含 score, reason, evidence 列表), "
            "rule2_analysis (包含 score, reason, evidence 列表), "
            "rule3_analysis (包含 score, reason, evidence 列表), "
            "logic_graph (包含 nodes 列表, transitions 列表，每个 transition 包含 source/target/label/score 0-10)。"
            "所有返回的描述性文本（summary, reason, evidence, intensity_level, label）必须使用中文。"
        )

        user_prompt = f"请分析以下文本：\n\n{text}"

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
        except Exception as e:
            return f"Error: {str(e)}", None, None, False

    # Robustness check: Some LLMs might wrap the JSON object in a list, or return a non-dict.
    if isinstance(llm_result, list) and len(llm_result) > 0:
        llm_result = llm_result[0]
    
    if not isinstance(llm_result, dict):
        # Last resort fallback to empty dict with error summary
        llm_result = {
            "total_score": 0, 
            "intensity_level": "Analysis Error", 
            "summary": "AI 分析返回格式异常，请重试。",
            "rule1_analysis": {"score": 0, "reason": "分析失败", "evidence": []},
            "rule2_analysis": {"score": 0, "reason": "分析失败", "evidence": []},
            "rule3_analysis": {"score": 0, "reason": "分析失败", "evidence": []},
            "logic_graph": {"nodes": [], "transitions": []}
        }

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

    with st.expander("设置与词库 (Settings)", expanded=False):
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

        if st.button("联网同步最新 AI 词库 (Sync)", help="抓取互联网上最新的 AI 套话"):
            with st.spinner("正在联网搜索最新 AI 词汇..."):
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
            st.success("词库已保存")

        st.divider()
        st.write("检测灵敏度参数")
        freq_threshold = st.slider(
            "词频触发阈值 (Frequency Threshold)",
            min_value=1,
            max_value=10,
            value=3,
            help="同一关键词在分析窗口内出现次数超过该值才会被标记。"
        )
        window_size = st.number_input(
            "分析窗口大小 (Window Size)",
            min_value=100,
            max_value=2000,
            value=500,
            step=100,
            help="统计词频时使用的字符窗口大小。"
        )

    st.info("核心检测维度：语言指纹、逻辑上下文、注意力机制伪聚焦")
    st.divider()
    st.write("当前运行模型")
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
            ["AI 写作文本 (含逻辑错误)", "人类写作文本 (真实感官)"],
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
                        # Circular Gauge for AI Risk (Vintage Style)
                        fig_gauge = go.Figure(go.Indicator(
                            mode = "gauge+number",
                            value = score,
                            domain = {'x': [0, 1], 'y': [0, 1]},
                            title = {'text': "AI 疑似度", 'font': {'size': 24, 'family': "Cinzel, serif", 'color': "#5d4037"}},
                            number = {'suffix': "%", 'font': {'size': 40, 'family': "Cinzel, serif", 'color': "#8B4513"}},
                            gauge = {
                                'axis': {'range': [None, 100], 'tickwidth': 2, 'tickcolor': "#5d4037", 'tickfont': {'family': "Noto Serif SC", 'color': "#5d4037"}},
                                'bar': {'color': "#8B4513", 'line': {'color': "#3e2723", 'width': 1}},
                                'bgcolor': "#fdfbf7",
                                'borderwidth': 2,
                                'bordercolor': "#5d4037",
                                'steps': [
                                    {'range': [0, 30], 'color': '#A9C5A0'},  # Muted Green
                                    {'range': [30, 70], 'color': '#F4E7C5'},  # Parchment Yellow
                                    {'range': [70, 100], 'color': '#DFA09E'}], # Faded Red
                                'threshold': {
                                    'line': {'color': "#8B0000", 'width': 4},
                                    'thickness': 0.75,
                                    'value': 80}}))
                        
                        fig_gauge.update_layout(height=300, margin=dict(l=30, r=30, t=50, b=20), paper_bgcolor='rgba(0,0,0,0)', font={'family': "Noto Serif SC"})
                        st.plotly_chart(fig_gauge, use_container_width=True)

                    with col_meta:
                        st.markdown(f"### 鉴定结论: <span style='color: #8B4513; font-family: Cinzel;'>{intensity.split('(')[0]}</span>", unsafe_allow_html=True)
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
                    tab_charts, tab_highlight, tab_deep, tab_method = st.tabs(["📊 数据图表", "🖍️ 词汇高亮", "🔍 深度报告", "📖 检测原理"])
                    
                    with tab_charts:
                        st.subheader("AI 特征可视化分析")
                        
                        # Display Statistical Metrics
                        metrics = result.get("text_metrics", {})
                        m1, m2, m3 = st.columns(3)
                        m1.metric("平均句长", f"{metrics.get('avg_len', 0)} 字符", help="AI 生成文本通常句长适中且平均")
                        m2.metric("爆发度 (Burstiness)", f"{metrics.get('std_dev_len', 0)}", delta="变化丰富 (人类)" if metrics.get('std_dev_len', 0) > 20 else "节奏单调 (AI)", delta_color="normal" if metrics.get('std_dev_len', 0) > 20 else "inverse", help="句长标准差越高，代表句式变化越丰富（人类特征）")
                        m3.metric("丰富度 (TTR)", f"{metrics.get('ttr', 0):.3f}", delta="丰富 (人类)" if metrics.get('ttr', 0) > 0.5 else "低 (AI)", delta_color="normal" if metrics.get('ttr', 0) > 0.5 else "inverse", help="词汇唯一性占比（Type-Token Ratio）")
                        
                        st.divider()
                        
                        col_chart1, col_chart2 = st.columns(2)
                        
                        with col_chart1:
                            # 1. Radar Chart (Plotly)
                            categories = ['语言指纹', '逻辑上下文', '注意力机制', '低爆发度(AI)', '词汇重复度(AI)']
                            
                            metrics = result.get("text_metrics", {})
                            burst_score = metrics.get("burstiness_score", 50) 
                            perp_score = metrics.get("perplexity_score", 50)
                            
                            r_values = [
                                result.get("rule1_analysis", {}).get("score", 0),
                                result.get("rule2_analysis", {}).get("score", 0),
                                result.get("rule3_analysis", {}).get("score", 0),
                                burst_score,
                                perp_score
                            ]
                            
                            radar_descriptions = [
                                "词汇选择、句式结构等统计特征",
                                "上下文逻辑连贯性、感官描写深度",
                                "无效细节描写和注意力分散现象",
                                "句子长度变化少，节奏单调",
                                "文本困惑度低，缺乏词汇惊喜感"
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
                                line_color='#8B4513',
                                fillcolor='rgba(139, 69, 19, 0.4)',
                                hovertemplate='<b>%{theta}</b><br>得分: %{r}<br>%{customdata}<extra></extra>',
                                customdata=radar_descriptions
                            ))
                            fig_radar.update_layout(
                                polar=dict(
                                    radialaxis=dict(visible=True, range=[0, 100], showline=True, linecolor='#5d4037', gridcolor='rgba(93, 64, 55, 0.2)', tickfont={'family': "Noto Serif SC"}),
                                    angularaxis=dict(gridcolor='rgba(93, 64, 55, 0.2)', tickfont={'family': "Noto Serif SC", 'size': 12, 'color': "#3e2723"}),
                                    bgcolor='#fdfbf7'
                                ),
                                showlegend=False,
                                title=dict(text="🛡️ AI 特征多维雷达图", font=dict(color='#5d4037', family="Cinzel, serif", size=20)),
                                height=350,
                                margin=dict(l=40, r=40, t=40, b=40),
                                paper_bgcolor='rgba(0,0,0,0)',
                                font=dict(color='#3e2723', family="Noto Serif SC")
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
                                    color_discrete_map={True: '#8B4513', False: '#A9A9A9'},
                                    template="simple_white"
                                )
                                fig_bar.update_traces(
                                    hovertemplate='<b>%{y}</b><br>出现次数: %{x}<br>状态: %{customdata}<extra></extra>',
                                    customdata=["超阈值 (高风险)" if val else "未达阈值 (低关注)" for val in df_freq['above_threshold']],
                                    marker_line_color='#3e2723',
                                    marker_line_width=1.5
                                )
                                fig_bar.update_layout(
                                    height=350, 
                                    yaxis={'categoryorder':'total ascending', 'tickfont': {'family': "Noto Serif SC"}},
                                    xaxis={'tickfont': {'family': "Noto Serif SC"}, 'gridcolor': 'rgba(93, 64, 55, 0.1)'},
                                    showlegend=False,
                                    plot_bgcolor='rgba(0,0,0,0)',
                                    paper_bgcolor='rgba(0,0,0,0)',
                                    font=dict(color='#3e2723', family="Noto Serif SC"),
                                    title_font=dict(family="Cinzel, serif", size=18, color="#5d4037")
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
                                opacity=0.8,
                                template="simple_white",
                                color_discrete_sequence=px.colors.qualitative.Antique
                            )
                            fig_scatter.update_traces(
                                marker=dict(size=12, symbol='diamond', line=dict(width=1, color='#3e2723')),
                                hovertemplate='<b>%{y}</b><br>位置: %{x}<br>说明: 密集分布可能暗示AI生成的重复模式<extra></extra>'
                            )
                            fig_scatter.update_layout(
                                xaxis=dict(title='文本进度 (字符位置)', showgrid=False, zeroline=True, zerolinecolor='#8B4513'),
                                yaxis=dict(categoryorder='category ascending', showgrid=True, gridcolor='rgba(93, 64, 55, 0.1)'),
                                showlegend=False,
                                height=400,
                                hovermode="closest",
                                plot_bgcolor='rgba(0,0,0,0)',
                                paper_bgcolor='rgba(0,0,0,0)',
                                font=dict(color='#3e2723', family="Noto Serif SC"),
                                title_font=dict(family="Cinzel, serif", size=18, color="#5d4037")
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
