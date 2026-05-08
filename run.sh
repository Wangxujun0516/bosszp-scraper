#!/usr/bin/env bash
set -e

# BOSS 直聘爬虫 - 一键运行脚本
# 用法:
#   bash run.sh              # 爬取 + 分析
#   bash run.sh --scrape     # 只爬取
#   bash run.sh --analyze    # 只分析最新数据

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d "venv" ]; then
    echo "[setup] 创建虚拟环境..."
    python3 -m venv venv
fi

source venv/bin/activate

if [ "$1" = "--analyze" ]; then
    echo "[run] 只分析数据..."
    python analyze.py
    exit 0
fi

if [ "$1" = "--scrape" ]; then
    echo "[run] 只爬取数据..."
    python scraper.py
    exit 0
fi

# 默认：先爬取，再分析
echo "[run] 开始爬取..."
python scraper.py

echo ""
echo "[run] 开始分析..."
python analyze.py

echo ""
echo "[run] 完成！"
