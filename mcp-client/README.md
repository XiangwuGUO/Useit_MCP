# MCP网关客户端

FastAPI网关服务器，提供统一API接口管理多个MCP服务器并支持AI智能工具调用。

## 🎯 核心功能

- **统一API入口**: 单一接口访问所有MCP服务器
- **AI智能调用**: 自然语言描述自动选择工具和生成参数  
- **动态服务器管理**: 实时添加/移除MCP服务器连接
- **健康监控**: 系统状态和连接监控

## 🚀 快速启动

```bash
# 安装依赖
pip install -r requirements.txt

# 启动网关服务器
python server.py

# 网关运行在 http://localhost:8080
```

## 📡 主要API接口

### 系统管理
```bash
GET  /health        # 健康检查
GET  /docs          # API文档
```

### 智能工具调用
```bash
POST /tools/smart-call
{
  "mcp_server_name": "filesystem",
  "task_description": "创建一个test.txt文件",
  "vm_id": "vm123", 
  "session_id": "sess456"
}
```

### 服务器注册
```bash
POST /clients
{
  "vm_id": "vm123",
  "session_id": "sess456",
  "name": "filesystem",
  "url": "http://server.com/mcp"
}
```

## 🧠 AI智能调用

智能调用使用Claude API自动：
1. 从可用工具中选择最合适的工具
2. 根据任务描述生成工具参数
3. 执行工具并返回结果
4. 提供token使用统计

## 🔧 测试功能

```bash
# 运行完整功能测试
python mcp_quicktest_ext.py

# 运行基础示例
python examples/demo.py
```

## 🛠️ 配置

### 环境变量
```bash
# AI功能（可选）
export ANTHROPIC_API_KEY="sk-your-key"

# 网关端口（可选）
export MCP_GATEWAY_PORT=8080
```

---

🚀 **MCP网关客户端 - AI驱动的统一MCP管理平台**