# MCP服务器集合

统一管理多个MCP服务器，支持基础目录管理和FRP隧道部署。

## 🎯 可用服务器

- **filesystem**: 文件系统操作 (端口8003)
- **audio_slicer**: 音频切片处理 (端口8002)  
- **example_server**: 示例Echo服务器 (端口8005)

## 🚀 启动方式

### 使用启动脚本 (推荐)
```bash
# 从项目根目录启动
cd .. && ./start_simple_servers.sh start-frp vm123 sess456 /custom/workspace
```

### 直接启动
```bash
# 安装依赖
pip install -r requirements.txt

# 启动所有服务器（指定基础目录）
python simple_launcher.py --base-dir /path/to/workspace --enable-frp --vm-id vm123 --session-id sess456

# 启动单个服务器
python simple_launcher.py --single filesystem

# 列出可用服务器
python simple_launcher.py --list
```

## 📁 基础目录管理

所有MCP服务器使用统一的基础目录：
- **配置方式**: `--base-dir /path/to/workspace`
- **环境变量**: `MCP_BASE_DIR`
- **默认目录**: `./mcp_workspace/`
- **文件操作**: 所有文件操作限制在基础目录内

## 🔧 配置文件

### servers_config.yaml
自定义服务器配置：
```yaml
custom_servers:
  - name: my_server
    module_path: customized_server/my_server.py
    port: 8006
    description: "我的自定义服务器"
```

## 🛠️ 开发新服务器

参考 `customized_server/example_server.py` 创建新服务器：
```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="MyServer")

@mcp.tool()
def my_tool(param: str) -> str:
    return f"结果: {param}"

if __name__ == "__main__":
    from server_base import start_mcp_server
    start_mcp_server(mcp, 8006, "MyServer")
```

---

🚀 **MCP服务器集合 - 为分布式MCP系统提供强大的功能支持**