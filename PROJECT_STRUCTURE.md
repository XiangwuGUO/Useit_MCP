# 项目结构说明

## 🏗️ 整体架构

```
useit-mcp/
├── README.md                   # 主文档 - 项目概览和快速入门
├── SIMPLE_USAGE.md            # 详细使用说明 - FRP集成指南
├── PROJECT_STRUCTURE.md       # 本文档 - 项目结构说明
├── start_simple_servers.sh    # 🚀 统一启动脚本 (主要入口)
│
├── mcp-client/                # 🎯 MCP网关客户端 (核心组件)
│   ├── server.py             # 主服务器 - 统一API网关
│   ├── core/                 # 核心功能模块
│   ├── config/               # 配置管理
│   ├── utils/                # 工具函数
│   ├── examples/             # 使用示例
│   └── README.md            # 详细API文档
│
├── mcp-server/               # 🔧 MCP服务器集合
│   ├── simple_launcher.py    # 简化启动器 (支持FRP)
│   ├── simple_frp_registry.py # FRP注册器
│   ├── launcher.py          # 传统启动器 (纯本地)
│   ├── official_server/     # 官方服务器实现
│   ├── customized_server/   # 自定义服务器示例
│   ├── servers_config.yaml  # 服务器配置文件
│   └── README.md           # 服务器详细文档
│
└── logs/                    # 日志目录
```

## 🎯 核心组件

### 1. 统一启动脚本
**文件**: `start_simple_servers.sh`  
**作用**: 系统主入口，提供统一的服务器管理

```bash
# 主要命令
./start_simple_servers.sh start          # 本地模式
./start_simple_servers.sh start-frp      # FRP远程注册模式
./start_simple_servers.sh status         # 查看状态
./start_simple_servers.sh list           # 列出可用服务器
```

### 2. MCP网关客户端 
**目录**: `mcp-client/`  
**作用**: 统一API网关，管理所有MCP服务器连接

**核心文件**:
- `server.py` - FastAPI网关服务器
- `core/client_manager.py` - 简化的客户机管理器
- `core/task_executor.py` - 智能任务执行器
- `core/api_models.py` - API数据模型

**API端点**:
- `/health`, `/stats` - 系统监控
- `/clients`, `/servers/register` - 服务器管理
- `/tools/call`, `/tools/find` - 工具调用
- `/tasks/execute` - 智能任务执行

### 3. MCP服务器集合
**目录**: `mcp-server/`  
**作用**: 提供各种功能的MCP服务器实现

**启动器**:
- `simple_launcher.py` - 支持FRP的启动器 (推荐)
- `launcher.py` - 纯本地启动器
- `simple_frp_registry.py` - FRP注册工具

**可用服务器**:
- `filesystem` (端口8003) - 文件系统操作
- `audio_slicer` (端口8002) - 音频处理
- `web_search` (端口8004) - 网页搜索

## 🔄 两种运行模式

### 本地开发模式
```
[MCP网关客户端:8080] ←→ [本地MCP服务器:8002,8003,8004]
```

**特点**:
- 所有组件在同一机器运行
- 通过localhost通信
- 适用于开发测试

**启动方式**:
```bash
./start_simple_servers.sh start
cd mcp-client && python server.py
```

### FRP分布式模式
```
[客户机] MCP服务器 ←→ FRP隧道 ←→ [公网] ←→ [服务器] MCP网关客户端
```

**特点**:
- 客户机运行MCP服务器
- 服务器运行MCP网关客户端  
- 通过FRP隧道连接
- 支持跨网络部署

**启动方式**:
```bash
# 客户机端
export MCP_CLIENT_URL="http://server-ip:8080"
./start_simple_servers.sh start-frp

# 服务器端
cd mcp-client && python server.py
```

## 📁 文件组织说明

### 主要文件

| 文件 | 作用 | 重要性 |
|------|------|--------|
| `start_simple_servers.sh` | 统一启动脚本 | ⭐⭐⭐ |
| `mcp-client/server.py` | API网关服务器 | ⭐⭐⭐ |
| `mcp-server/simple_launcher.py` | MCP服务器启动器 | ⭐⭐⭐ |
| `mcp-server/simple_frp_registry.py` | FRP注册器 | ⭐⭐ |
| `README.md` | 主文档 | ⭐⭐ |
| `SIMPLE_USAGE.md` | 使用指南 | ⭐⭐ |

### 备份文件 (可删除)

| 文件 | 说明 |
|------|------|
| `mcp-client/server_complex.py` | 复杂版本的服务器 (包含已移除的FRP发现功能) |
| `mcp-client/core/client_manager_complex.py` | 复杂版本的客户机管理器 |
| `mcp-server/launcher_complex.py` | 复杂版本的启动器 |

## 🔧 配置文件

### 环境变量
```bash
# 基础配置
export MCP_GATEWAY_PORT=8080
export LOG_LEVEL=INFO

# FRP配置
export MCP_CLIENT_URL="http://localhost:8080"

# 智能任务 (可选)
export ANTHROPIC_API_KEY="your-api-key"
```

### 配置文件
- `mcp-client/config/settings.py` - 网关服务器配置
- `mcp-server/servers_config.yaml` - 自定义服务器配置

## 📊 端口分配

| 组件 | 默认端口 | 说明 |
|------|----------|------|
| MCP网关客户端 | 8080 | API网关入口 |
| 音频切片服务器 | 8002 | audio_slicer |
| 文件系统服务器 | 8003 | filesystem |
| 网页搜索服务器 | 8004 | web_search |
| 自定义服务器 | 8005+ | 根据配置分配 |

## 🛠️ 开发工作流

### 1. 本地开发
```bash
# 启动MCP服务器
./start_simple_servers.sh start

# 启动网关 (另开终端)
cd mcp-client && python server.py

# 测试API
curl http://localhost:8080/docs
```

### 2. 添加新服务器
```bash
# 1. 创建服务器文件
# mcp-server/customized_server/my_server.py

# 2. 添加配置
# 编辑 mcp-server/servers_config.yaml

# 3. 测试
./start_simple_servers.sh single my_server
```

### 3. 分布式测试
```bash
# 客户机端
export MCP_CLIENT_URL="http://test-server:8080"
./start_simple_servers.sh start-frp

# 服务器端
cd mcp-client && python server.py
```

## 📚 文档体系

1. **README.md** - 项目总览，快速开始
2. **SIMPLE_USAGE.md** - 详细使用说明，FRP集成指南
3. **mcp-client/README.md** - 网关服务器API文档
4. **mcp-server/README.md** - MCP服务器开发指南
5. **PROJECT_STRUCTURE.md** - 本文档，架构说明

## 🔍 故障排除

### 常见目录
- `logs/` - 系统日志
- `mcp-client/gateway.log` - 网关日志
- `mcp-server/output_audio/` - 音频处理输出

### 调试命令
```bash
# 查看系统状态
./start_simple_servers.sh status

# 查看日志
./start_simple_servers.sh logs

# 健康检查
curl http://localhost:8080/health

# 列出所有工具
curl http://localhost:8080/tools
```

---

这个项目结构经过优化，移除了冗余代码，整合了文档，提供了清晰的开发和部署路径。通过统一的启动脚本和模块化的设计，既保持了系统的简洁性，又提供了强大的扩展能力。