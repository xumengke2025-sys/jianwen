@echo off
chcp 65001 >nul
echo 正在检查虚拟环境...

if not exist ".venv" (
    echo 创建新的虚拟环境...
    python -m venv .venv
)

echo 激活虚拟环境...
call .venv\Scripts\activate

echo 检查依赖更新...
pip install -r requirements.txt

echo 启动应用...
streamlit run main.py

pause
