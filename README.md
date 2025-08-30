# Useit MCP - 统一的MCP服务器系统

🚀 **现代化的分布式MCP服务器系统** - 提供统一的MCP服务器管理，支持本地和远程部署

## 🎯 项目特点

- **🔌 统一网关**: 通过单一API管理多个MCP服务器
- **🧠 智能任务**: 支持自然语言描述的任务自动执行  
- **📁 模块化**: 清晰的代码结构，易于扩展
- **🌐 灵活部署**: 支持本地测试和远程FRP代理模式
- **⚡ 即插即用**: 简单的配置和启动

## 📦 项目结构

```
useit-mcp/
├── mcp-client/                 # 🎯 MCP网关服务器 (统一入口)
│   ├── server.py              # 主服务器入口
│   ├── core/                  # 核心功能模块
│   │   ├── client_manager.py  # 客户机管理
│   │   ├── task_executor.py   # 智能任务执行
│   │   └── api_models.py      # API数据模型
│   ├── config/                # 配置管理
│   ├── examples/              # 使用示例
│   └── utils/                 # 工具函数
├── mcp-server/                # 🔧 MCP服务器集合
│   ├── launcher.py            # 传统启动器 (本地)
│   ├── simple_launcher.py     # 简化启动器 (支持FRP)
│   ├── simple_frp_registry.py # FRP注册器
│   └── official_server/       # 官方服务器实现
│       ├── filesystem/        # 文件系统服务器
│       ├── audio_slicer/      # 音频处理服务器
│       └── web_search/        # 网页搜索服务器
├── start_simple_servers.sh    # 统一启动脚本
└── SIMPLE_USAGE.md           # 详细使用文档
```

## 🚀 快速开始

### 方式一：本地测试模式

```bash
# 1. 启动MCP服务器 (本地模式)
./start_simple_servers.sh start

# 2. 启动MCP网关 (另开终端)
cd mcp-client
python server.py

# 3. 访问API文档
# http://localhost:8080/docs
```

### 方式二：FRP远程代理模式

```bash
# 1. 设置远程MCP客户端地址
export MCP_CLIENT_URL="http://your-server:8080"

# 2. 启动MCP服务器 (FRP模式)
./start_simple_servers.sh start-frp

# 3. 服务器会自动创建FRP隧道并注册到远程客户端
```

## 🧠 核心功能

### 1. 统一MCP网关
- **单一入口**: 所有功能通过一个API提供
- **客户机管理**: 动态添加/移除MCP服务器
- **智能路由**: 自动查找合适的服务器执行任务
- **状态监控**: 实时监控所有服务器状态

### 2. 智能任务执行
```bash
# 用自然语言描述任务，系统自动执行
curl -X POST "http://localhost:8080/tasks/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "vm_id": "filesystem",
    "session_id": "auto", 
    "mcp_server_name": "FileSystem",
    "task_description": "创建一个Python项目结构，包含src、tests、docs目录"
  }'
```

### 3. 多MCP服务器支持
- **FileSystem**: 文件操作、目录管理、文档处理
- **AudioSlicer**: 音频切片、节拍分析
- **WebSearch**: 网页搜索功能
- **可扩展**: 轻松添加新的MCP服务器

## 📡 核心API接口

### 系统管理
```
GET  /health              # 健康检查  
GET  /stats               # 系统统计
GET  /docs                # API文档
```

### 客户机管理
```
POST /clients             # 添加MCP服务器
GET  /clients             # 列出所有服务器
POST /servers/register    # 服务器注册 (FRP用)
```

### 工具调用
```
GET  /tools               # 列出所有工具
POST /tools/call          # 调用指定工具
POST /tools/find          # 查找并调用工具
```

### 智能任务
```  
POST /tasks/execute       # 执行智能任务
```

完整API文档请访问 `/docs` 端点查看

## 🔧 使用模式

### 本地开发模式
适用于开发测试，所有服务运行在本地：

```bash
# 启动服务器
./start_simple_servers.sh start

# 查看状态
./start_simple_servers.sh status

# 停止服务
./start_simple_servers.sh stop
```

### FRP远程模式
适用于分布式部署，客户机上的MCP服务器通过FRP隧道注册到服务器端：

```bash
# 设置服务器端MCP客户端地址
export MCP_CLIENT_URL="http://server-ip:8080"

# 启动并自动注册
./start_simple_servers.sh start-frp

# 单个服务器测试
./start_simple_servers.sh single-frp filesystem
```

## 🎯 部署架构

### 架构图
```
[客户机]                    [服务器]
MCP服务器 ←→ FRP隧道 ←→ 公网 ←→ MCP客户端/网关
```

### 两种部署方式

1. **本地模式**: 
   - 所有组件在同一机器运行
   - 适用于开发测试
   - 启动命令: `./start_simple_servers.sh start`

2. **分布式模式**:
   - 客户机运行MCP服务器 + FRP隧道
   - 服务器运行MCP网关客户端
   - 通过FRP隧道连接
   - 启动命令: `./start_simple_servers.sh start-frp`

## 🛠️ 配置选项

### 环境变量配置
```bash
# 基础配置
export MCP_GATEWAY_PORT=8080
export LOG_LEVEL=INFO

# 智能任务配置  
export ANTHROPIC_API_KEY="sk-your-key"
export CLAUDE_MODEL="claude-3-sonnet-20240229"

# FRP配置
export MCP_CLIENT_URL="http://localhost:8080"  # 服务器端地址
```

## 📚 服务器管理

### 可用服务器
- `audio_slicer`: 音频切片服务 (端口8002)
- `filesystem`: 文件系统操作 (端口8003)  
- `web_search`: 网页搜索服务 (端口8004)

### 管理命令
```bash
# 列出可用服务器
./start_simple_servers.sh list

# 启动单个服务器
./start_simple_servers.sh single filesystem

# 查看运行状态
./start_simple_servers.sh status

# 查看日志
./start_simple_servers.sh logs
```

## 🔍 故障排除

### 常见问题

1. **端口冲突**
   ```bash
   # 检查端口占用
   lsof -i :8080
   
   # 修改端口
   export MCP_GATEWAY_PORT=8081
   ```

2. **FRP连接失败**
   ```bash
   # 检查FRP服务器连通性
   ping useit.run
   
   # 查看详细日志
   ./start_simple_servers.sh logs
   ```

3. **服务器注册失败**
   ```bash
   # 检查MCP客户端地址
   echo $MCP_CLIENT_URL
   
   # 测试连通性
   curl $MCP_CLIENT_URL/health
   ```

### 获取帮助
- 查看详细日志: `./start_simple_servers.sh logs`
- 运行健康检查: `curl http://localhost:8080/health`
- 查看系统状态: `curl http://localhost:8080/stats`
- 完整使用说明: 查看 `SIMPLE_USAGE.md`

## 🎊 项目优势

### ✅ 架构优势
- **统一入口**: 单一服务器管理所有功能
- **模块化设计**: 清晰的代码结构，易于维护
- **可扩展性**: 轻松添加新的MCP服务器
- **灵活部署**: 支持本地和分布式部署

### ✅ 功能优势  
- **智能化**: 自然语言任务描述，自动执行
- **分布式**: 支持跨网络的服务器连接
- **实时性**: 实时状态监控和故障检测

### ✅ 开发优势
- **即插即用**: 简单的配置和启动
- **标准协议**: 完全兼容MCP标准
- **丰富文档**: 详细的文档和示例代码

## 🤝 文件说明

- **README.md**: 本文档，项目概览
- **SIMPLE_USAGE.md**: 详细使用说明和示例
- **start_simple_servers.sh**: 统一的服务器管理脚本
- **mcp-client/**: MCP网关客户端，提供统一API
- **mcp-server/**: MCP服务器实现，包含各种功能服务器

## 📄 许可证

MIT License

---

🚀 **开始使用Useit MCP，体验统一的分布式MCP服务器系统！**