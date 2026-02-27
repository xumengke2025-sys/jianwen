# AI 文本检测与分析工具 (Jianwen)

这是一个基于 Streamlit 的 AI 文本检测与分析工具，旨在帮助用户识别和分析文本是否由 AI 生成。本项目结合了深度语义分析、统计学特征工程（如爆发度、困惑度）以及可视化的逻辑脉络分析，提供多维度的检测报告。

## ✨ 核心功能

*   **🕵️ 多维度检测**: 结合 LLM 深度分析与统计学指标（Burstiness, Perplexity）。
*   **🧬 逻辑脉络 DNA 图谱**: 独创的逻辑流可视化，通过“健康度”和“篇章进度”展示文章的逻辑演进，直观识别逻辑断层和 AI 生成痕迹。
*   **🖍️ 语言指纹识别**: 自动检测并高亮显示常见的 AI 口癖、结构僵化用语和过度修饰词汇。
*   **📊 详细分析报告**: 提供包括感官断层、注意力机制伪聚焦等在内的深度分析。
*   **📄 多格式支持**: 支持直接输入文本，或上传 TXT, PDF, DOCX 文件。

## 🛠️ 安装与部署

### 1. 克隆项目

```bash
git clone https://github.com/xumengke2025-sys/jianwen.git
cd jianwen
```

### 2. 安装依赖

确保您的环境已安装 Python 3.8+。

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

在项目根目录下创建一个 `.env` 文件，并填入您的 LLM API 配置信息：

```env
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=your_base_url_here
LLM_MODEL_NAME=your_model_name_here (e.g., gpt-4o, claude-3-5-sonnet)
```

> **注意**: 请勿将 `.env` 文件上传到版本控制系统中。

### 4. 运行应用

**推荐方式 (Windows)**:
直接双击运行项目目录下的 `start.bat` 脚本即可。它会自动创建虚拟环境、安装依赖并启动应用。

**手动方式**:

```bash
# 创建并激活虚拟环境 (可选，推荐)
python -m venv .venv
.venv\Scripts\activate

# 安装依赖 (首次运行或依赖变更时执行)
pip install -r requirements.txt

# 启动应用
streamlit run main.py
```

## 🧩 技术栈

*   **Frontend**: [Streamlit](https://streamlit.io/)
*   **Data Visualization**: [Plotly](https://plotly.com/), Altair
*   **LLM Integration**: OpenAI SDK (Compatible with various providers)
*   **Document Processing**: PyPDF2, python-docx

## 📝 许可证

[MIT License](LICENSE)
