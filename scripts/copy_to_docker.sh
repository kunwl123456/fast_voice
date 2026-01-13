#!/bin/bash

# 获取脚本所在目录的父目录（项目根目录）
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

echo "📦 复制文件到 Docker 容器..."
echo "项目根目录: $PROJECT_ROOT"
echo ""

# 复制导入脚本
echo "📄 复制导入脚本..."
docker cp "$PROJECT_ROOT/scripts/import_vocu_docker.py" fast-voice-api:/app/import_vocu_docker.py
docker cp "$PROJECT_ROOT/scripts/import_vocu_market.py" fast-voice-api:/app/import_vocu_market.py

# 复制数据目录
echo "📁 复制数据目录..."
docker cp "$PROJECT_ROOT/vocu_data" fast-voice-api:/app/vocu_data
docker cp "$PROJECT_ROOT/vocu_market_data" fast-voice-api:/app/vocu_market_data

echo "✅ 文件复制完成！"
echo ""
echo "📥 执行导入脚本..."
echo ""

# 导入官方市场数据
echo "=" | awk '{printf "%80s\n", $0}' | tr " " "="
echo "导入官方市场数据 (vocu_data)"
echo "=" | awk '{printf "%80s\n", $0}' | tr " " "="
docker exec fast-voice-api bash -c "cd /app && uv run python import_vocu_docker.py"

echo ""
echo ""

# 导入社区市场数据
echo "=" | awk '{printf "%80s\n", $0}' | tr " " "="
echo "导入社区市场数据 (vocu_market_data)"
echo "=" | awk '{printf "%80s\n", $0}' | tr " " "="
docker exec fast-voice-api bash -c "cd /app && uv run python import_vocu_market.py"

echo ""
echo "✨ 全部导入完成！"
