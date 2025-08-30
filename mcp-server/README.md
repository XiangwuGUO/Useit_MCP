# MCP服务器集合

这个目录包含了多个MCP服务器实现，提供文件系统、音频处理、网页搜索等功能。支持本地运行和FRP远程注册两种模式。

## 🎯 功能特性

- **多服务器支持**: 集成多个功能专一的MCP服务器
- **统一管理**: 通过启动器统一管理所有服务器
- **灵活部署**: 支持本地测试和FRP远程注册模式
- **自动端口管理**: 智能分配和管理端口，避免冲突
- **可扩展架构**: 易于添加新的MCP服务器

## 📦 目录结构

```
mcp-server/
├── launcher.py                # 传统启动器 (纯本地)
├── simple_launcher.py         # 简化启动器 (支持FRP)
├── simple_frp_registry.py     # FRP注册器
├── official_server/           # 官方服务器实现
│   ├── filesystem/            # 文件系统服务器
│   │   └── server.py
│   ├── audio_slicer/          # 音频处理服务器
│   │   ├── server.py
│   │   ├── slicer.py
│   │   └── requirements.txt
│   └── web_search/            # 网页搜索服务器
│       ├── server.py
│       └── websearch_tool.py
├── customized_server/         # 自定义服务器示例
│   └── example_server.py
├── servers_config.yaml        # 自定义服务器配置
└── requirements.txt           # Python依赖
```

## 🚀 快速启动

### 方式一：使用统一启动脚本 (推荐)

```bash
# 回到项目根目录
cd ..

# 本地模式 - 启动所有服务器
./start_simple_servers.sh start

# FRP模式 - 启动并自动注册到远程
export MCP_CLIENT_URL="http://your-server:8080"
./start_simple_servers.sh start-frp

# 启动单个服务器测试
./start_simple_servers.sh single filesystem

# 查看状态
./start_simple_servers.sh status
```

### 方式二：直接使用启动器

```bash
# 安装依赖
pip install -r requirements.txt

# 本地模式启动所有服务器
python simple_launcher.py

# FRP模式启动
python simple_launcher.py --enable-frp

# 启动单个服务器
python simple_launcher.py --single filesystem

# 列出可用服务器
python simple_launcher.py --list
```

## 🔧 可用服务器

### 1. 文件系统服务器 (filesystem)
- **端口**: 8003
- **功能**: 文件和目录操作
- **工具**: 创建/读取/写入/删除文件，列出目录等

### 2. 音频切片服务器 (audio_slicer) 
- **端口**: 8002
- **功能**: 音频文件切片和节拍分析
- **工具**: 音频切片、节拍检测、格式转换

### 3. 网页搜索服务器 (web_search)
- **端口**: 8004
- **功能**: 网页搜索和内容获取
- **工具**: 搜索查询、网页抓取、内容提取
- **配置**: 需要设置 `OPENAI_API_KEY` 环境变量

## 📡 两种使用模式

### 本地开发模式
适用于开发测试，所有服务器运行在本地：

```bash
# 启动所有服务器
python simple_launcher.py

# 或使用传统启动器（无FRP功能）
python launcher.py
```

**特点**:
- 所有服务器运行在本地
- 直接通过localhost访问
- 适用于开发和测试

### FRP远程注册模式
适用于分布式部署，服务器通过FRP隧道注册到远程客户端：

```bash
# 设置远程MCP客户端地址
export MCP_CLIENT_URL="http://server-ip:8080"

# 启动并自动注册
python simple_launcher.py --enable-frp
```

**特点**:
- 自动创建FRP隧道
- 将公网地址注册到远程MCP客户端
- 支持跨网络访问

## 🔧 配置说明

### 环境变量

```bash
# 基础配置
export MCP_SERVER_PORT=8003        # 单个服务器端口
export MCP_CLIENT_URL="http://localhost:8080"  # MCP客户端地址

# 服务特定配置
export OPENAI_API_KEY="your-key"   # 网页搜索服务器需要
```

### 自定义服务器配置

在 `servers_config.yaml` 中可以配置自定义服务器：

```yaml
custom_servers:
  - name: my_custom_server
    module_path: customized_server/my_server.py
    port: 8005
    transport: streamable-http
    description: My custom MCP server
    env_vars:
      MY_API_KEY: required
```

## 🛠️ 添加新服务器

### 1. 创建服务器实现

```python
# customized_server/my_server.py
from mcp.server.fastmcp import FastMCP
import os

# 获取端口配置
port = int(os.environ.get("MCP_SERVER_PORT", 8005))
mcp = FastMCP("MyServer", port=port)

@mcp.tool()
def my_tool(param: str) -> str:
    """我的工具功能"""
    return f"处理结果: {param}"

if __name__ == "__main__":
    mcp.run()
```

### 2. 添加到配置文件

编辑 `servers_config.yaml` 添加新服务器配置。

### 3. 测试服务器

```bash
# 列出包含新服务器的所有服务器
python simple_launcher.py --list

# 单独测试新服务器
python simple_launcher.py --single my_custom_server
```

## 📊 服务器管理

### 查看服务器状态

```bash
# 使用启动脚本
../start_simple_servers.sh status

# 或直接查询MCP客户端
curl http://localhost:8080/clients
```

### 日志查看

```bash
# 查看启动脚本日志
../start_simple_servers.sh logs

# 查看单个服务器日志
python simple_launcher.py --single filesystem
```

## 🔍 故障排除

### 常见问题

1. **端口冲突**
   ```bash
   # 检查端口占用
   lsof -i :8003
   
   # 端口会自动分配，通常不会冲突
   ```

2. **服务器启动失败**
   ```bash
   # 检查依赖是否安装
   pip install -r requirements.txt
   
   # 检查环境变量
   python simple_launcher.py --list
   ```

3. **FRP注册失败**
   ```bash
   # 检查MCP客户端地址
   echo $MCP_CLIENT_URL
   curl $MCP_CLIENT_URL/health
   
   # 检查FRP连接
   ping useit.run
   ```

### 调试模式

```bash
# 启动单个服务器进行调试
python simple_launcher.py --single filesystem

# 查看详细日志
python simple_launcher.py --single filesystem 2>&1 | tee debug.log
```

## 🧪 开发和测试

### 开发新服务器

1. 参考 `customized_server/example_server.py`
2. 实现所需的工具和功能
3. 添加到配置文件
4. 进行本地测试

### 测试流程

```bash
# 1. 本地测试
python simple_launcher.py --single my_server

# 2. 集成测试
python simple_launcher.py --no-custom  # 测试官方服务器
python simple_launcher.py              # 测试所有服务器

# 3. FRP测试
export MCP_CLIENT_URL="http://test-server:8080"
python simple_launcher.py --single my_server --enable-frp
```

## ✨ 最佳实践

### 服务器开发

1. **端口管理**: 使用 `MCP_SERVER_PORT` 环境变量
2. **错误处理**: 实现适当的错误处理和日志记录
3. **配置管理**: 通过环境变量进行配置
4. **文档**: 为工具和资源提供清晰的描述

### 部署建议

1. **本地开发**: 使用本地模式快速迭代
2. **远程测试**: 使用FRP模式测试分布式场景
3. **监控**: 定期检查服务器状态和连接
4. **日志**: 保留足够的日志用于故障排除

---

这个MCP服务器集合为useit-mcp系统提供了丰富的功能支持，通过统一的启动器和配置系统，使得管理多个MCP服务器变得简单而高效。