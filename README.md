# Useit MCP - 分布式MCP服务器系统

🚀 **统一的MCP服务器管理平台** - 支持智能工具调用和分布式部署

## 🎯 核心功能

- **🔌 统一API网关**: 单一入口管理多个MCP服务器
- **🧠 AI智能调用**: 自然语言描述自动选择工具和生成参数
- **📁 基础目录管理**: 统一的文件操作沙箱目录
- **🌐 FRP隧道部署**: 支持跨网络的安全连接
- **⚡ 自动重启**: 智能检测并重启服务器

## 📦 项目结构

```
useit-mcp/
├── mcp-client/                 # MCP API网关
│   ├── server.py              # FastAPI网关服务器
│   ├── core/                  # 核心功能模块
│   │   ├── client_manager.py  # MCP客户端管理
│   │   ├── task_executor.py   # AI任务执行引擎
│   │   └── api_models.py      # API数据模型
│   └── mcp_quicktest_ext.py   # 功能测试脚本
├── mcp-server/                # MCP服务器集合
│   ├── simple_launcher.py     # 统一启动器
│   ├── base_dir_decorator.py  # 基础目录管理
│   └── official_server/       # 服务器实现
│       ├── filesystem/        # 文件系统操作
│       └── audio_slicer/      # 音频处理
└── start_simple_servers.sh    # 管理脚本
```

## 🚀 快速开始

### 1. 启动MCP网关
```bash
cd mcp-client && python server.py
# 网关运行在 http://localhost:8080
```

### 2. 启动MCP服务器

**本地模式**：
```bash
./start_simple_servers.sh start
```

**FRP模式（带基础目录）**：
```bash
# 指定工作目录
./start_simple_servers.sh start-frp vm123 sess456 /path/to/workspace

# 使用默认目录
./start_simple_servers.sh start-frp vm123 sess456
```

### 3. 测试功能
```bash
cd mcp-client && python mcp_quicktest_ext.py
```

## 🧠 核心功能

### AI智能工具调用
```bash
# 智能工具调用：指定MCP服务器+任务描述，AI自动选择工具和生成参数
curl -X POST "http://localhost:8080/tools/smart-call" \
  -H "Content-Type: application/json" \
  -d '{
    "mcp_server_name": "filesystem",
    "task_description": "创建一个test.txt文件，内容是Hello World",
    "vm_id": "vm123",
    "session_id": "sess456"
  }'
```

### 可用MCP服务器
- **filesystem**: 文件系统操作（读写文件、目录管理）
- **audio_slicer**: 音频切片处理
- **example_server**: 示例服务器（echo功能）

## 📡 主要API接口

```
GET  /health                    # 系统健康检查
POST /tools/smart-call          # AI智能工具调用
POST /clients                   # 注册MCP服务器
GET  /docs                      # API文档
```

## 🔧 管理命令

```bash
# 启动服务器
./start_simple_servers.sh start                              # 本地模式
./start_simple_servers.sh start-frp vm123 sess456           # FRP模式（默认目录）
./start_simple_servers.sh start-frp vm123 sess456 /custom/dir  # FRP模式（指定目录）
./start_simple_servers.sh start-frp vm123 sess456 /home/ubuntu/workspace/gxw/useit_mcp_new/useit_mcp_test_dir
# 管理操作
./start_simple_servers.sh stop                              # 停止服务器
./start_simple_servers.sh status                            # 查看状态
./start_simple_servers.sh logs                              # 查看日志
./start_simple_servers.sh list                              # 列出可用服务器
```

## 🛠️ 配置选项

### 环境变量
```bash
# AI功能（可选）
export ANTHROPIC_API_KEY="sk-your-key"

# FRP模式
export MCP_CLIENT_URL="http://server-ip:8080"
```

### 基础目录
所有MCP服务器使用统一的基础目录进行文件操作：
- 默认目录：`./mcp_workspace/`
- 可通过启动参数指定：`start-frp vm123 sess456 /custom/path`
- 环境变量：`MCP_BASE_DIR`

## 🔍 故障排除

```bash
# 查看服务器状态
./start_simple_servers.sh status

# 查看详细日志
./start_simple_servers.sh logs

# 检查网关健康状态
curl http://localhost:8080/health
```

---

🚀 **开始使用Useit MCP - 智能化的MCP服务器管理平台！**