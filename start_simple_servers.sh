#!/bin/bash
# 简化的MCP服务器启动脚本
# 支持本地测试和FRP远程注册两种模式

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"

# 日志文件
LOG_DIR="$PROJECT_DIR/logs"
SERVER_LOG="$LOG_DIR/mcp_servers.log"

# 创建日志目录
mkdir -p "$LOG_DIR"

# PID文件
PID_FILE="$PROJECT_DIR/mcp_servers.pid"

# 帮助信息
show_help() {
    echo "🚀 简化的MCP服务器管理工具"
    echo ""
    echo "用法: $0 [命令] [选项]"
    echo ""
    echo "命令:"
    echo "  start         启动服务器 (本地模式)"
    echo "  start-frp     启动服务器 (FRP远程注册模式)" 
    echo "  stop          停止所有服务器"
    echo "  restart       重启服务器"
    echo "  status        显示服务器状态"
    echo "  logs          显示日志"
    echo "  list          列出可用服务器"
    echo "  single <name> 启动单个服务器"
    echo ""
    echo "选项:"
    echo "  --no-custom   跳过自定义服务器"
    echo "  --registry-url <url>  设置MCP客户端注册地址"
    echo ""
    echo "示例:"
    echo "  $0 start                    # 本地模式启动"
    echo "  $0 start-frp                # FRP模式启动"
    echo "  $0 single audio_slicer      # 启动单个服务器"
    echo "  $0 status                   # 查看状态"
}

# 检查Python和依赖
check_dependencies() {
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ 未找到 python3${NC}"
        exit 1
    fi
    
    # 检查必要的Python模块
    python3 -c "import yaml, requests" 2>/dev/null || {
        echo -e "${YELLOW}⚠️ 缺少依赖，正在安装...${NC}"
        pip3 install pyyaml requests httpx || {
            echo -e "${RED}❌ 依赖安装失败${NC}"
            exit 1
        }
    }
}

# 获取服务器状态
get_status() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ 服务器运行中 (PID: $pid)${NC}"
            
            # 获取详细状态
            cd "$PROJECT_DIR/mcp-server"
            python3 simple_launcher.py --status 2>/dev/null || echo "  无法获取详细状态"
            
            return 0
        else
            echo -e "${YELLOW}⚠️ PID文件存在但进程不存在${NC}"
            rm -f "$PID_FILE"
            return 1
        fi
    else
        echo -e "${RED}❌ 服务器未运行${NC}"
        return 1
    fi
}

# 启动服务器
start_servers() {
    local enable_frp="$1"
    local extra_args="$2"
    
    echo -e "${BLUE}🚀 启动MCP服务器...${NC}"
    echo -e "${BLUE}📁 项目目录: $PROJECT_DIR${NC}"
    
    # 检查是否已经运行
    if [ -f "$PID_FILE" ] && ps -p "$(cat "$PID_FILE")" > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️ 服务器已在运行${NC}"
        get_status
        return 0
    fi
    
    # 检查依赖
    check_dependencies
    
    # 构建启动命令
    local cmd="python3 simple_launcher.py"
    
    if [ "$enable_frp" = "true" ]; then
        cmd="$cmd --enable-frp"
        echo -e "${BLUE}🌐 启用FRP反向代理模式${NC}"
    else
        echo -e "${BLUE}🔒 本地测试模式${NC}"
    fi
    
    if [ -n "$extra_args" ]; then
        cmd="$cmd $extra_args"
    fi
    
    # 设置环境变量
    export MCP_CLIENT_URL="${MCP_CLIENT_URL:-http://localhost:8080}"
    echo -e "${BLUE}📡 MCP客户端地址: $MCP_CLIENT_URL${NC}"
    
    # 启动服务器
    cd "$PROJECT_DIR/mcp-server"
    
    echo -e "${BLUE}▶️ 执行命令: $cmd${NC}"
    echo -e "${BLUE}📋 日志文件: $SERVER_LOG${NC}"
    
    # 后台启动
    nohup $cmd > "$SERVER_LOG" 2>&1 &
    local pid=$!
    echo "$pid" > "$PID_FILE"
    
    # 等待启动
    sleep 3
    
    # 检查是否成功启动
    if ps -p "$pid" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ 服务器启动成功 (PID: $pid)${NC}"
        
        if [ "$enable_frp" = "true" ]; then
            echo -e "${GREEN}💡 FRP模式已启用，服务器端MCP客户端现在可以连接${NC}"
        fi
        
        # 显示快速状态
        sleep 2
        get_status
    else
        echo -e "${RED}❌ 服务器启动失败${NC}"
        echo -e "${YELLOW}📋 查看日志: tail -f $SERVER_LOG${NC}"
        rm -f "$PID_FILE"
        return 1
    fi
}

# 停止服务器
stop_servers() {
    echo -e "${BLUE}🛑 停止MCP服务器...${NC}"
    
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo -e "${BLUE}📤 发送停止信号到进程 $pid${NC}"
            kill -TERM "$pid"
            
            # 等待进程结束
            local count=0
            while ps -p "$pid" > /dev/null 2>&1 && [ $count -lt 10 ]; do
                sleep 1
                count=$((count + 1))
            done
            
            if ps -p "$pid" > /dev/null 2>&1; then
                echo -e "${YELLOW}⚠️ 进程未正常结束，强制终止${NC}"
                kill -KILL "$pid"
                sleep 1
            fi
            
            echo -e "${GREEN}✅ 服务器已停止${NC}"
        else
            echo -e "${YELLOW}⚠️ 进程不存在${NC}"
        fi
        rm -f "$PID_FILE"
    else
        echo -e "${YELLOW}⚠️ 服务器未运行${NC}"
    fi
}

# 重启服务器
restart_servers() {
    local enable_frp="$1"
    local extra_args="$2"
    
    echo -e "${BLUE}🔄 重启MCP服务器...${NC}"
    stop_servers
    sleep 2
    start_servers "$enable_frp" "$extra_args"
}

# 显示日志
show_logs() {
    if [ -f "$SERVER_LOG" ]; then
        echo -e "${BLUE}📋 服务器日志:${NC}"
        echo "=================================="
        tail -50 "$SERVER_LOG"
        echo ""
        echo -e "${YELLOW}💡 实时查看日志: tail -f $SERVER_LOG${NC}"
    else
        echo -e "${YELLOW}⚠️ 日志文件不存在: $SERVER_LOG${NC}"
    fi
}

# 列出服务器
list_servers() {
    echo -e "${BLUE}📋 列出可用服务器...${NC}"
    
    check_dependencies
    cd "$PROJECT_DIR/mcp-server"
    python3 simple_launcher.py --list
}

# 启动单个服务器
start_single_server() {
    local server_name="$1"
    local enable_frp="$2"
    
    if [ -z "$server_name" ]; then
        echo -e "${RED}❌ 请指定服务器名称${NC}"
        list_servers
        return 1
    fi
    
    echo -e "${BLUE}🚀 启动单个服务器: $server_name${NC}"
    
    # 检查依赖
    check_dependencies
    
    # 构建启动命令
    local cmd="python3 simple_launcher.py --single $server_name"
    
    if [ "$enable_frp" = "true" ]; then
        cmd="$cmd --enable-frp"
        echo -e "${BLUE}🌐 启用FRP反向代理${NC}"
    fi
    
    # 设置环境变量
    export MCP_CLIENT_URL="${MCP_CLIENT_URL:-http://localhost:8080}"
    
    # 启动服务器
    cd "$PROJECT_DIR/mcp-server"
    echo -e "${BLUE}▶️ 执行命令: $cmd${NC}"
    $cmd
}

# 主逻辑
main() {
    case "$1" in
        start)
            start_servers "false" "$2"
            ;;
        start-frp)
            start_servers "true" "$2"
            ;;
        stop)
            stop_servers
            ;;
        restart)
            restart_servers "false" "$2"
            ;;
        restart-frp)
            restart_servers "true" "$2"
            ;;
        status)
            get_status
            ;;
        logs)
            show_logs
            ;;
        list)
            list_servers
            ;;
        single)
            start_single_server "$2" "false"
            ;;
        single-frp)
            start_single_server "$2" "true"
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            echo -e "${RED}❌ 未知命令: $1${NC}"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# 检查参数
if [ $# -eq 0 ]; then
    show_help
    exit 1
fi

# 运行主逻辑
main "$@"