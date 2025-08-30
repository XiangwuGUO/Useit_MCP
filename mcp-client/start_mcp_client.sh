#!/bin/bash

# MCP Client (Gateway) 启动脚本
# 确保在正确的conda环境和目录下启动

set -e  # 遇到错误时退出

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "🔧 脚本目录: $SCRIPT_DIR"

# 切换到mcp-client目录
cd "$SCRIPT_DIR"
echo "📁 当前目录: $(pwd)"

# 激活conda环境
echo "🐍 激活conda环境: dify"
source ~/miniconda3/etc/profile.d/conda.sh
conda activate dify

# 检查Python和必要的依赖
echo "🔍 检查Python环境..."
python --version
echo "📦 检查关键依赖..."
python -c "import fastapi, uvicorn, httpx; print('✅ 核心依赖可用')" || {
    echo "❌ 缺少核心依赖，请安装: pip install fastapi uvicorn httpx"
    exit 1
}

# 检查.env文件
if [ -f ".env" ]; then
    echo "✅ 找到.env配置文件"
    # 显示配置信息（不显示敏感信息）
    echo "📋 配置信息:"
    grep -E "^(MCP_GATEWAY_HOST|MCP_GATEWAY_PORT|LOG_LEVEL)" .env || echo "   未找到基础配置"
    if grep -q "^ANTHROPIC_API_KEY=" .env; then
        echo "   ✅ ANTHROPIC_API_KEY: 已设置"
    else
        echo "   ⚠️ ANTHROPIC_API_KEY: 未设置"
    fi
else
    echo "⚠️ 未找到.env文件，将使用默认配置"
fi

# 检查日志文件权限
if [ -f "gateway.log" ]; then
    echo "📝 日志文件已存在"
else
    echo "📝 将创建新的日志文件"
fi

# 启动服务器
echo ""
echo "🚀 启动MCP Gateway服务器..."
echo "   - 服务器将在 http://localhost:8080 启动"
echo "   - 按 Ctrl+C 停止服务器"
echo "   - 日志将输出到控制台和 gateway.log 文件"
echo ""

# 设置PYTHONPATH并直接运行server.py
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"
python server.py

echo ""
echo "🛑 MCP Gateway服务器已停止"