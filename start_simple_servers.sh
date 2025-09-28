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
FRP_PID_FILE="$PROJECT_DIR/frp_api_server.pid"

# FRP服务器路径和配置
FRP_SERVER_DIR="$PROJECT_DIR/mcp-server/useit_frp"
FRP_API_PORT=5888

# 帮助信息
show_help() {
    echo "🚀 简化的MCP服务器管理工具"
    echo ""
    echo "用法: $0 [命令] [选项]"
    echo ""
    echo "命令:"
    echo "  start         启动服务器 (本地模式)"
    echo "  start-frp [vm_id] [session_id] [base_dir]  启动服务器 (FRP远程注册模式)" 
    echo "  stop          停止所有服务器"
    echo "  restart       重启服务器"
    echo "  status        显示服务器状态"
    echo "  logs          显示日志"
    echo "  list          列出可用服务器"
    echo "  single <name> 启动单个服务器"
    echo "  frp-start     单独启动FRP API服务器"
    echo "  frp-stop      单独停止FRP API服务器"
    echo "  frp-status    查看FRP API服务器状态"
    echo "  kill-all      强制杀死所有MCP相关进程"
    echo ""
    echo "选项:"
    echo "  --no-custom   跳过自定义服务器"
    echo "  --registry-url <url>  设置MCP客户端注册地址"
    echo ""
    echo "示例:"
    echo "  $0 start                    # 本地模式启动"
    echo "  $0 start-frp vm123 sess456  # FRP模式启动(带vm_id和session_id)"
    echo "  $0 start-frp vm123 sess456 /tmp/mcp_workspace  # 指定基础目录"
    echo "  $0 single audio_slicer      # 启动单个服务器"
    echo "  $0 status                   # 查看状态"
    echo ""
    echo "注意:"
    echo "  - FRP模式会在 base_dir/.useit/ 目录下生成 mcp_server_frp.json 配置文件"
    echo "  - 此文件包含服务器连接信息，可用于MCP客户端注册"
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
    
    # 检查FRP相关依赖
    python3 -c "import flask" 2>/dev/null || {
        echo -e "${YELLOW}⚠️ 缺少FRP API服务器依赖，正在安装...${NC}"
        pip3 install flask || {
            echo -e "${RED}❌ FRP依赖安装失败${NC}"
            exit 1
        }
    }
}

# 检查FRP API服务器状态
check_frp_api_server() {
    curl -s "http://localhost:$FRP_API_PORT/health" >/dev/null 2>&1
    return $?
}

# 获取FRP API服务器状态
get_frp_status() {
    if [ -f "$FRP_PID_FILE" ]; then
        local pid=$(cat "$FRP_PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            if check_frp_api_server; then
                echo -e "${GREEN}✅ FRP API服务器运行中 (PID: $pid, Port: $FRP_API_PORT)${NC}"
                return 0
            else
                echo -e "${YELLOW}⚠️ FRP API服务器进程存在但API不可访问${NC}"
                return 1
            fi
        else
            echo -e "${YELLOW}⚠️ FRP PID文件存在但进程不存在${NC}"
            rm -f "$FRP_PID_FILE"
            return 1
        fi
    else
        if check_frp_api_server; then
            echo -e "${YELLOW}⚠️ FRP API服务器运行中但PID文件丢失${NC}"
            return 0
        else
            echo -e "${RED}❌ FRP API服务器未运行${NC}"
            return 1
        fi
    fi
}

# 启动FRP API服务器
start_frp_api_server() {
    echo -e "${BLUE}🌐 启动FRP API服务器...${NC}"
    
    # 检查FRP服务器目录是否存在
    if [ ! -d "$FRP_SERVER_DIR" ]; then
        echo -e "${RED}❌ FRP服务器目录不存在: $FRP_SERVER_DIR${NC}"
        return 1
    fi
    
    # 检查是否已经运行
    if check_frp_api_server; then
        echo -e "${YELLOW}⚠️ FRP API服务器已在运行${NC}"
        return 0
    fi
    
    # 检查FRP相关文件
    if [ ! -f "$FRP_SERVER_DIR/api_server.py" ]; then
        echo -e "${RED}❌ FRP API服务器文件不存在: $FRP_SERVER_DIR/api_server.py${NC}"
        return 1
    fi
    
    # 启动FRP API服务器
    cd "$FRP_SERVER_DIR"
    echo -e "${BLUE}▶️ 启动FRP API服务器 (端口: $FRP_API_PORT)${NC}"
    
    nohup python3 api_server.py > "$LOG_DIR/frp_api_server.log" 2>&1 &
    local pid=$!
    echo "$pid" > "$FRP_PID_FILE"
    
    # 等待启动
    sleep 3
    
    # 检查是否成功启动
    if ps -p "$pid" > /dev/null 2>&1 && check_frp_api_server; then
        echo -e "${GREEN}✅ FRP API服务器启动成功 (PID: $pid)${NC}"
        echo -e "${BLUE}🔗 API地址: http://localhost:$FRP_API_PORT${NC}"
        return 0
    else
        echo -e "${RED}❌ FRP API服务器启动失败${NC}"
        echo -e "${YELLOW}📋 查看日志: tail -f $LOG_DIR/frp_api_server.log${NC}"
        rm -f "$FRP_PID_FILE"
        return 1
    fi
}

# 停止FRP API服务器
stop_frp_api_server() {
    echo -e "${BLUE}🛑 停止FRP API服务器...${NC}"
    
    if [ -f "$FRP_PID_FILE" ]; then
        local pid=$(cat "$FRP_PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo -e "${BLUE}📤 发送停止信号到FRP API服务器进程 $pid${NC}"
            kill -TERM "$pid"
            
            # 等待进程结束
            local count=0
            while ps -p "$pid" > /dev/null 2>&1 && [ $count -lt 10 ]; do
                sleep 1
                count=$((count + 1))
            done
            
            if ps -p "$pid" > /dev/null 2>&1; then
                echo -e "${YELLOW}⚠️ FRP进程未正常结束，强制终止${NC}"
                kill -KILL "$pid"
                sleep 1
            fi
            
            echo -e "${GREEN}✅ FRP API服务器已停止${NC}"
        else
            echo -e "${YELLOW}⚠️ FRP进程不存在${NC}"
        fi
        rm -f "$FRP_PID_FILE"
    else
        echo -e "${YELLOW}⚠️ FRP API服务器未运行${NC}"
    fi
}

# 强制停止所有MCP相关进程
stop_all_mcp_processes() {
    echo -e "${BLUE}🔥 强制停止所有MCP相关进程...${NC}"
    
    # 杀死所有运行simple_launcher.py的Python进程
    local mcp_pids=$(ps aux | grep "python.*simple_launcher.py" | grep -v grep | awk '{print $2}')
    if [ -n "$mcp_pids" ]; then
        echo -e "${YELLOW}⚠️ 发现MCP进程，正在终止...${NC}"
        for pid in $mcp_pids; do
            echo -e "${BLUE}📤 终止MCP进程: PID $pid${NC}"
            kill -TERM "$pid" 2>/dev/null || true
            sleep 1
            # 如果进程仍然存在，强制杀死
            if ps -p "$pid" > /dev/null 2>&1; then
                echo -e "${YELLOW}🔨 强制终止MCP进程: PID $pid${NC}"
                kill -KILL "$pid" 2>/dev/null || true
            fi
        done
    fi
    
    # 杀死所有运行api_server.py的Python进程 (FRP)
    local frp_pids=$(ps aux | grep "python.*api_server.py" | grep -v grep | awk '{print $2}')
    if [ -n "$frp_pids" ]; then
        echo -e "${YELLOW}⚠️ 发现FRP API进程，正在终止...${NC}"
        for pid in $frp_pids; do
            echo -e "${BLUE}📤 终止FRP API进程: PID $pid${NC}"
            kill -TERM "$pid" 2>/dev/null || true
            sleep 1
            # 如果进程仍然存在，强制杀死
            if ps -p "$pid" > /dev/null 2>&1; then
                echo -e "${YELLOW}🔨 强制终止FRP API进程: PID $pid${NC}"
                kill -KILL "$pid" 2>/dev/null || true
            fi
        done
    fi
    
    # 杀死占用MCP端口的进程 (8002, 8003, 5888)
    local ports=(8002 8003 5888)
    for port in "${ports[@]}"; do
        local port_pids=$(lsof -t -i:$port 2>/dev/null || true)
        if [ -n "$port_pids" ]; then
            echo -e "${YELLOW}⚠️ 发现占用端口 $port 的进程，正在终止...${NC}"
            for pid in $port_pids; do
                echo -e "${BLUE}📤 终止占用端口 $port 的进程: PID $pid${NC}"
                kill -TERM "$pid" 2>/dev/null || true
                sleep 1
                # 如果进程仍然存在，强制杀死
                if ps -p "$pid" > /dev/null 2>&1; then
                    echo -e "${YELLOW}🔨 强制终止进程: PID $pid${NC}"
                    kill -KILL "$pid" 2>/dev/null || true
                fi
            done
        fi
    done
    
    # 清理PID文件
    if [ -f "$PID_FILE" ]; then
        echo -e "${BLUE}🧹 清理MCP PID文件${NC}"
        rm -f "$PID_FILE"
    fi
    if [ -f "$FRP_PID_FILE" ]; then
        echo -e "${BLUE}🧹 清理FRP PID文件${NC}"
        rm -f "$FRP_PID_FILE"
    fi
    
    echo -e "${GREEN}✅ 所有MCP相关进程已强制停止${NC}"
    sleep 1
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
            
            # 显示FRP API服务器状态
            echo ""
            get_frp_status
            
            # 检查FRP配置文件是否存在
            local frp_json
            if [ -n "$base_dir" ]; then
                frp_json="$base_dir/.useit/mcp_server_frp.json"
            else
                frp_json="$PROJECT_DIR/mcp_workspace/.useit/mcp_server_frp.json"
            fi
            if [ -f "$frp_json" ]; then
                echo -e "${GREEN}📄 FRP配置文件: $frp_json${NC}"
                echo -e "${BLUE}📋 服务器数量: $(python3 -c "import json; print(len(json.load(open('$frp_json'))['servers']))" 2>/dev/null || echo "未知")${NC}"
            fi
            
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
    local vm_id="$2"
    local session_id="$3"
    local base_dir="$4"
    local extra_args="$5"
    
    echo -e "${BLUE}🚀 启动MCP服务器...${NC}"
    echo -e "${BLUE}📁 项目目录: $PROJECT_DIR${NC}"
    
    # 强制清理所有现有MCP进程
    echo -e "${BLUE}🔍 确保没有现有MCP进程运行...${NC}"
    stop_all_mcp_processes
    sleep 2
    
    # 检查依赖
    check_dependencies
    
    # 构建启动命令
    local cmd="python3 simple_launcher.py"
    
    # 添加base_dir参数
    if [ -n "$base_dir" ]; then
        cmd="$cmd --base-dir \"$base_dir\""
        echo -e "${BLUE}📁 基础工作目录: $base_dir${NC}"
    fi
    
    if [ "$enable_frp" = "true" ]; then
        # 启动FRP模式前，先确保FRP API服务器运行
        echo -e "${BLUE}🌐 启用FRP反向代理模式${NC}"
        
        if ! start_frp_api_server; then
            echo -e "${RED}❌ FRP API服务器启动失败，无法启用FRP模式${NC}"
            return 1
        fi
        
        cmd="$cmd --enable-frp"
        
        # 添加vm_id和session_id参数
        if [ -n "$vm_id" ]; then
            cmd="$cmd --vm-id $vm_id"
        fi
        if [ -n "$session_id" ]; then
            cmd="$cmd --session-id $session_id"
        fi
        
        if [ -n "$vm_id" ]; then
            echo -e "${BLUE}🆔 VM ID: $vm_id${NC}"
        fi
        if [ -n "$session_id" ]; then
            echo -e "${BLUE}📋 Session ID: $session_id${NC}"
        fi
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
    
    # 轮转总控日志（mcp_servers.log），便于追踪本次启动
    if [ -f "$SERVER_LOG" ]; then
        mv -f "$SERVER_LOG" "${SERVER_LOG%.log}_old.log" 2>/dev/null || true
    fi
    
    # 后台启动（simple_launcher内部会将各服务器日志写入 logs/<server>_server.log）
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
            
            # 等待frp配置文件生成并输出路径
            sleep 2
            local frp_json
            if [ -n "$base_dir" ]; then
                frp_json="$base_dir/.useit/mcp_server_frp.json"
            else
                frp_json="$PROJECT_DIR/mcp_workspace/.useit/mcp_server_frp.json"
            fi
            if [ -f "$frp_json" ]; then
                echo -e "${GREEN}📄 FRP服务器配置文件已生成: $frp_json${NC}"
                echo -e "${BLUE}📋 可使用此文件配置注册到MCP客户端${NC}"
            else
                echo -e "${YELLOW}⚠️ FRP配置文件尚未生成，稍等片刻...${NC}"
                # 再等待一下
                sleep 3
                if [ -f "$frp_json" ]; then
                    echo -e "${GREEN}📄 FRP服务器配置文件: $frp_json${NC}"
                    echo -e "${BLUE}📋 可使用此文件配置注册到MCP客户端${NC}"
                fi
            fi
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
    
    # 停止FRP API服务器
    stop_frp_api_server
    
    # 额外清理：删除可能残留的FRP配置文件
    # 检查默认工作空间和其他可能的位置
    local frp_json="$PROJECT_DIR/mcp_workspace/.useit/mcp_server_frp.json"
    if [ -f "$frp_json" ]; then
        echo -e "${BLUE}🧹 清理FRP配置文件...${NC}"
        rm -f "$frp_json"
        echo -e "${GREEN}✅ FRP配置文件已清理${NC}"
    fi
    
    # 也清理旧的位置，防止遗留文件
    local old_frp_json="$PROJECT_DIR/mcp_server_frp.json"
    if [ -f "$old_frp_json" ]; then
        echo -e "${BLUE}🧹 清理旧的FRP配置文件...${NC}"
        rm -f "$old_frp_json"
        echo -e "${GREEN}✅ 旧的FRP配置文件已清理${NC}"
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
            if [ -z "$2" ] || [ -z "$3" ]; then
                echo -e "${RED}❌ start-frp 需要 vm_id 和 session_id 参数${NC}"
                echo "用法: $0 start-frp <vm_id> <session_id> [base_dir]"
                exit 1
            fi
            start_servers "true" "$2" "$3" "$4" "$5"
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
        frp-start)
            start_frp_api_server
            ;;
        frp-stop)
            stop_frp_api_server
            ;;
        frp-status)
            get_frp_status
            ;;
        kill-all)
            stop_all_mcp_processes
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