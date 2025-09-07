# MCP系统完整功能测试

这个测试脚本 (`mcp_quicktest_ext.py`) 提供了MCP系统的完整测试，包括服务器注册、智能工具调用和文件同步功能。

## 🎯 测试功能

### 1️⃣ **MCP服务器注册**
- 从 `mcp_server_frp.json` 读取FRP配置
- 自动注册所有可用的MCP服务器到客户端
- 验证注册是否成功

### 2️⃣ **智能工具调用**
- 测试智能工具调用功能
- 默认测试：创建红烧肉菜谱文件
- 验证工具执行和响应解析

### 3️⃣ **文件同步功能** 
- 测试多种哈希同步策略
- 预演模式和实际同步测试
- 增量同步验证
- 文件完整性检查

## 🚀 使用方法

### 前置条件
1. **启动客户机MCP服务器**（FRP模式）:
```bash
./start_simple_servers.sh start-frp vm123 sess456 /path/to/workspace
```

2. **启动服务器MCP客户端**:
```bash
cd mcp-client && python server.py
```

### 运行测试
```bash
cd mcp-client
python mcp_quicktest_ext.py
```

## 📊 测试结果

测试脚本会显示：
- ✅/❌ 每个步骤的执行状态
- 📄 详细的执行日志和错误信息
- 📊 文件同步统计和结果
- 🎯 最终的测试汇总

## 🔧 配置参数

可以修改脚本中的配置参数：

```python
# 基本配置
mcp_server_url = 'http://localhost:8080'  # MCP客户端地址
vm_id = "vm123"                           # 虚拟机ID
session_id = "sess456"                    # 会话ID

# 测试任务
instruction_text = "创建红烧肉的菜谱，内容写在一个txt文件里面"
mcp_server_name = "filesystem"

# 同步配置
target_base_path = "/mnt/efs/data/useit/users_workspace"
```

## 🏗️ 架构说明

```
客户机端                    服务器端
┌─────────────────┐        ┌─────────────────┐
│ MCP Server      │◄─FRP──►│ MCP Client      │
│ (filesystem)    │        │ (Gateway)       │
│                 │        │                 │
│ BASE_DIR        │        │ Target Path     │
│ ├── file1.txt   │  同步   │ ├── mcp_files/  │
│ ├── docs/       │ ────► │ └── uploaded/   │
│ └── data/       │        │                 │
└─────────────────┘        └─────────────────┘
```

## 🐛 故障排查

### 常见问题

1. **连接失败**
   - 检查MCP客户端是否运行在8080端口
   - 检查FRP配置是否正确生成

2. **注册失败**
   - 确认客户机MCP服务器已启动
   - 检查 `mcp_server_frp.json` 文件是否存在

3. **同步失败**
   - 检查目标目录权限
   - 确认BASE_DIR有可同步的文件
   - 查看文件大小是否超过50MB限制

### 调试技巧

- 查看MCP客户端日志: `tail -f logs/mcp_client.log`
- 查看MCP服务器日志: `tail -f logs/mcp_servers.log`
- 使用预演模式测试: 修改 `dry_run: True`

## 📝 扩展功能

可以基于此测试脚本扩展：

1. **添加新的测试用例**
2. **测试其他MCP服务器**（audio_slicer等）
3. **自定义同步策略**
4. **批量文件操作测试**

## 💡 最佳实践

1. **定期运行测试**确保系统稳定性
2. **监控文件同步结果**避免数据丢失
3. **合理设置同步策略**平衡性能和安全性
4. **备份重要配置**如FRP配置文件