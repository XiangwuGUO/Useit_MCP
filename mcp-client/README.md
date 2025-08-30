# MCP客户端网关服务器

MCP客户端网关服务器是整个useit-mcp系统的核心组件，提供统一的API接口来管理和调用多个MCP服务器。

## 🎯 功能特性

- **统一API网关**: 提供单一入口访问所有MCP服务器
- **客户机管理**: 动态添加、移除和监控MCP服务器连接
- **工具调用**: 统一的工具调用接口，支持智能路由
- **智能任务**: 基于自然语言的任务自动化执行
- **健康监控**: 实时监控系统状态和服务器连接
- **服务器注册**: 支持MCP服务器自动注册(用于FRP集成)

## 📦 目录结构

```
mcp-client/
├── server.py              # 主服务器入口
├── core/                  # 核心功能模块
│   ├── client_manager.py  # MCP客户机连接管理
│   ├── task_executor.py   # 智能任务执行器
│   └── api_models.py      # API数据模型定义
├── config/                # 配置管理
│   └── settings.py        # 应用配置
├── utils/                 # 工具函数
│   └── helpers.py         # 辅助函数
├── examples/              # 使用示例
│   └── demo.py            # API调用示例
└── requirements.txt       # Python依赖
```

## 🚀 快速启动

### 1. 安装依赖

```bash
cd mcp-client
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 基础配置
export MCP_GATEWAY_PORT=8080
export LOG_LEVEL=INFO

# 智能任务配置(可选)
export ANTHROPIC_API_KEY="sk-your-api-key"
export CLAUDE_MODEL="claude-3-sonnet-20240229"
```

### 3. 启动服务器

```bash
python server.py
```

服务器启动后可访问:
- **API文档**: http://localhost:8080/docs
- **健康检查**: http://localhost:8080/health
- **系统状态**: http://localhost:8080/stats

## 📡 API接口说明

### 系统管理

#### GET /health
健康检查接口
```json
{
  "success": true,
  "message": "服务器运行正常",
  "data": {
    "status": "healthy",
    "connected_clients": 2,
    "total_tools": 15,
    "uptime": "2h30m"
  }
}
```

#### GET /stats
系统统计信息
```json
{
  "success": true,
  "data": {
    "total_clients": 3,
    "connected_clients": 2,
    "total_tools": 15,
    "total_resources": 5,
    "uptime": "2h30m",
    "server_start_time": "2024-01-01T10:00:00"
  }
}
```

### 客户机管理

#### POST /clients
添加MCP服务器
```json
{
  "vm_id": "server-01",
  "session_id": "session-001",
  "remote_url": "http://localhost:8003/mcp"
}
```

#### GET /clients
列出所有已连接的MCP服务器
```json
{
  "success": true,
  "data": [
    {
      "vm_id": "server-01",
      "session_id": "session-001", 
      "remote_url": "http://localhost:8003/mcp",
      "connected": true,
      "tools_count": 8,
      "resources_count": 3
    }
  ]
}
```

#### DELETE /clients/{vm_id}/{session_id}
移除指定的MCP服务器连接

#### POST /servers/register
MCP服务器注册接口(用于FRP自动注册)
```json
{
  "name": "filesystem",
  "url": "http://localhost:8003/mcp",
  "description": "文件系统操作服务器"
}
```

### 工具管理

#### GET /tools
获取所有可用工具列表
```json
{
  "success": true,
  "data": [
    {
      "client_id": "server-01/session-001",
      "name": "create_file",
      "description": "创建文件",
      "input_schema": {...}
    }
  ]
}
```

#### POST /tools/call
调用指定客户机的工具
```json
{
  "vm_id": "server-01",
  "session_id": "session-001",
  "tool_name": "create_file",
  "arguments": {
    "path": "/tmp/test.txt",
    "content": "Hello World"
  }
}
```

#### POST /tools/find
智能查找并调用工具
```json
{
  "tool_name": "create_file",
  "arguments": {
    "path": "/tmp/test.txt",
    "content": "Hello World"
  },
  "preferred_vm_id": "server-01"
}
```

### 智能任务

#### POST /tasks/execute
执行自然语言描述的智能任务
```json
{
  "vm_id": "server-01",
  "session_id": "session-001",
  "mcp_server_name": "FileSystem",
  "task_description": "创建一个Python项目结构，包含src、tests、docs目录和相应的文件",
  "context": "项目名称是my-project"
}
```

## 🔧 配置说明

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| MCP_GATEWAY_PORT | 8080 | 网关服务器端口 |
| LOG_LEVEL | INFO | 日志级别 |
| CLIENT_TIMEOUT | 30 | MCP客户端连接超时(秒) |
| TASK_TIMEOUT | 300 | 任务执行超时(秒) |
| ANTHROPIC_API_KEY | - | Claude API密钥(智能任务用) |
| CLAUDE_MODEL | claude-3-sonnet-20240229 | Claude模型 |

### 配置文件

配置文件位于 `config/settings.py`，支持从环境变量和 `.env` 文件加载配置。

## 🧠 智能任务执行

智能任务执行器使用Claude API来理解自然语言描述的任务，并自动调用相应的MCP工具来完成任务。

### 工作流程
1. 接收自然语言任务描述
2. 分析可用的MCP工具和资源
3. 生成执行计划
4. 依次调用相关工具
5. 返回执行结果

### 示例任务
- "创建一个Python项目结构"
- "备份/home目录下的所有Python文件"
- "搜索关于机器学习的文章并保存摘要"

## 🔍 使用示例

### Python客户端示例

```python
import httpx

# 添加MCP服务器
async with httpx.AsyncClient() as client:
    response = await client.post("http://localhost:8080/clients", json={
        "vm_id": "filesystem",
        "session_id": "auto",
        "remote_url": "http://localhost:8003/mcp"
    })
    print(response.json())

# 调用工具
response = await client.post("http://localhost:8080/tools/call", json={
    "vm_id": "filesystem",
    "session_id": "auto", 
    "tool_name": "create_file",
    "arguments": {
        "path": "/tmp/hello.txt",
        "content": "Hello MCP!"
    }
})
print(response.json())

# 智能任务执行
response = await client.post("http://localhost:8080/tasks/execute", json={
    "vm_id": "filesystem",
    "session_id": "auto",
    "task_description": "创建一个名为my-project的Python项目结构"
})
print(response.json())
```

### curl示例

```bash
# 健康检查
curl http://localhost:8080/health

# 添加MCP服务器
curl -X POST http://localhost:8080/clients \
  -H "Content-Type: application/json" \
  -d '{
    "vm_id": "filesystem",
    "session_id": "auto",
    "remote_url": "http://localhost:8003/mcp"
  }'

# 获取工具列表
curl http://localhost:8080/tools

# 执行智能任务
curl -X POST http://localhost:8080/tasks/execute \
  -H "Content-Type: application/json" \
  -d '{
    "vm_id": "filesystem",
    "session_id": "auto",
    "task_description": "创建一个Python项目结构"
  }'
```

## 🔧 故障排除

### 常见问题

1. **服务器启动失败**
   - 检查端口是否被占用: `lsof -i :8080`
   - 检查Python依赖是否安装完整

2. **MCP服务器连接失败**
   - 确认MCP服务器正在运行
   - 检查URL和端口配置
   - 查看服务器日志

3. **智能任务执行失败**
   - 检查ANTHROPIC_API_KEY是否设置
   - 确认API密钥有效且有足够配额
   - 查看任务执行日志

### 日志查看

服务器日志默认输出到 `gateway.log` 文件。可以通过以下方式查看:

```bash
# 查看最新日志
tail -f gateway.log

# 查看错误日志
grep ERROR gateway.log
```

## 🛠️ 开发说明

### 添加新的API端点

1. 在 `server.py` 中添加新的路由函数
2. 在 `core/api_models.py` 中定义相关的数据模型
3. 更新API文档和示例

### 扩展智能任务功能

1. 修改 `core/task_executor.py`
2. 添加新的任务模板或处理逻辑
3. 测试任务执行流程

### 测试

```bash
# 运行示例
cd examples
python demo.py

# 手动测试API
curl http://localhost:8080/docs
```

---

这个MCP客户端网关服务器为整个useit-mcp系统提供了统一、简洁的API接口，是连接各种MCP服务器和智能任务执行的核心枢纽。