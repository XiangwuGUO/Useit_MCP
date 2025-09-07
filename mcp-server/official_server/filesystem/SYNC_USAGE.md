# 文件同步功能使用说明

filesystem MCP服务器现在支持将本地文件同步到远程MCP客户端服务器，使用企业级的同步策略。

## 功能特性

- ✅ **支持的文件类型**: txt, md, pdf, doc, docx, ppt, pptx, xls, xlsx, json, yaml, csv, rtf
- ✅ **多种同步策略**: 基于哈希、大小+哈希、ETag等企业级策略
- ✅ **时区无关**: 不依赖时间戳，避免分布式环境时间同步问题
- ✅ **内容级比较**: 基于文件内容哈希，确保完全一致性
- ✅ **文件大小限制**: 单个文件不超过50MB
- ✅ **目录结构保持**: 完整保持原始目录结构
- ✅ **预演模式**: 可以预览将要同步的文件而不实际执行
- ✅ **性能优化**: 分层比较（大小→哈希），减少网络传输
- ✅ **错误处理**: 详细的同步结果和错误报告

## 同步目标

文件将被同步到远程服务器的以下位置：
```
/mnt/efs/data/useit/users_workspace/{vm_id}_{session_id}/
├── mcp_files/           # MCP服务器本地文件同步到这里
│   └── [原始目录结构]
└── uploaded_files/      # 用户上传文件存放这里
    └── [用户上传结构]
```

## 工具调用

### sync_files_to_remote

将本地BASE_DIR中的文件同步到远程MCP客户端。

**请求参数**:
```json
{
  "vm_id": "vm123",                              // 虚拟机ID (必需)
  "session_id": "sess456",                       // 会话ID (必需) 
  "remote_client_url": "http://server:8080",     // 远程MCP客户端URL (必需)
  "force_sync": false,                          // 强制同步所有文件，忽略哈希比较 (可选)
  "dry_run": false,                             // 预演模式，不实际同步 (可选)
  "sync_strategy": "hash",                      // 同步策略 (可选): "hash", "size_hash", "etag", "size_only"
  "chunk_size": 8192                            // 文件读取块大小 (可选)
}
```

**返回结果**:
```json
{
  "success": true,
  "message": "同步完成: 5 个文件已同步，2 个文件跳过",
  "synced_files": [
    "documents/report.pdf",
    "notes/readme.md"
  ],
  "skipped_files": [
    "old_file.txt"
  ],
  "error_files": [
    {
      "file": "large_file.pdf", 
      "error": "文件过大: 60.5MB > 50MB"
    }
  ],
  "total_size": 1048576,
  "sync_summary": {
    "total_files": 10,
    "synced": 5,
    "skipped": 2,
    "errors": 3,
    "dry_run": false
  }
}
```

## 使用示例

### 1. 默认同步策略 (推荐日常使用)

```python
import requests

sync_request = {
    "vm_id": "vm123",
    "session_id": "sess456",
    "remote_client_url": "http://localhost:8080",
    # sync_strategy 默认为 "size_hash" (大小+MD5哈希)
    "force_sync": False,
    "dry_run": False
}

response = requests.post(
    "http://localhost:8003/tools/call",
    json={
        "tool_name": "sync_files_to_remote",
        "arguments": sync_request
    }
)

result = response.json()
print(f"同步完成: {result['message']}")
```

### 2. 高安全性同步 (SHA256哈希)

```python
sync_request = {
    "vm_id": "vm123",
    "session_id": "sess456",
    "remote_client_url": "http://localhost:8080",
    "sync_strategy": "hash",       # 使用SHA256哈希，最安全
    "chunk_size": 16384,          # 使用更大的块大小
    "dry_run": False
}

response = requests.post(
    "http://localhost:8003/tools/call",
    json={
        "tool_name": "sync_files_to_remote",
        "arguments": sync_request
    }
)
```

### 3. 预演模式 - 查看将要同步的文件

```python
sync_request = {
    "vm_id": "vm123",
    "session_id": "sess456",
    "remote_client_url": "http://localhost:8080",
    # 使用默认的 size_hash 策略
    "dry_run": True  # 预演模式
}

response = requests.post(
    "http://localhost:8003/tools/call",
    json={
        "tool_name": "sync_files_to_remote",
        "arguments": sync_request
    }
)

result = response.json()
print(f"将同步 {len(result['synced_files'])} 个文件")
for file in result['synced_files']:
    print(f"  - {file}")
```

### 4. ETag企业级同步

```python
sync_request = {
    "vm_id": "vm123", 
    "session_id": "sess456",
    "remote_client_url": "http://localhost:8080",
    "sync_strategy": "etag",       # 使用ETag策略
    "force_sync": False
}

response = requests.post(
    "http://localhost:8003/tools/call",
    json={
        "tool_name": "sync_files_to_remote",
        "arguments": sync_request
    }
)
```

### 5. 强制同步 - 同步所有文件

```python
sync_request = {
    "vm_id": "vm123",
    "session_id": "sess456",
    "remote_client_url": "http://localhost:8080", 
    # 使用默认的 size_hash 策略
    "force_sync": True  # 强制同步，忽略哈希比较
}

response = requests.post(
    "http://localhost:8003/tools/call",
    json={
        "tool_name": "sync_files_to_remote",
        "arguments": sync_request  
    }
)
```

### 6. 通过MCP客户端智能调用

```python
# 通过MCP客户端的智能工具调用
mcp_request = {
    "vm_id": "vm123",
    "session_id": "sess456",
    "mcp_server_name": "filesystem",
    "task_description": "同步本地文件到远程服务器"
}

response = requests.post(
    "http://localhost:8080/tools/smart-call",
    json=mcp_request
)
```

## 同步策略

### 企业级同步策略

#### 1. **size_hash** (默认推荐)  
- 先比较文件大小，大小相同时再计算MD5哈希
- 平衡性能和准确性，大多数场景的最佳选择
- 适合大量小文件的同步和日常使用

#### 2. **hash** (最高安全性)
- 使用SHA256哈希比较文件内容
- 时区无关，最安全的同步策略
- 适合安全敏感场景和重要数据同步

#### 3. **etag** (企业级)
- 使用ETag算法（类似AWS S3）
- 对大文件使用分块哈希
- 适合云存储和分布式场景

#### 4. **size_only** (快速模式)
- 只比较文件大小
- 最快但准确性最低
- 适合快速预检或测试

### 同步决策逻辑

1. **文件存在性检查**: 检查远程文件是否存在
2. **分层比较策略**:
   - 第一层：文件大小比较（最快）
   - 第二层：内容哈希比较（最准确）
   - 第三层：ETag比较（企业级）
3. **决策规则**:
   - 远程文件不存在 → 同步
   - 文件大小不同 → 同步
   - 大小相同但哈希不同 → 同步
   - 大小和哈希都相同 → 跳过

### 性能优化

- **智能分块**: 大文件自动分块处理
- **缓存机制**: 本地哈希计算结果缓存
- **并发控制**: 避免同时多个同步操作
- **网络优化**: 只传输必要的文件内容

### 文件类型支持

- **文本文件**: txt, md, json, yaml, csv, rtf (使用write_text工具)
- **二进制文件**: pdf, doc, docx, ppt, pptx, xls, xlsx (使用write_binary工具，base64编码)

### 错误处理

- **文件过大**: 超过50MB的文件会被跳过并记录错误
- **网络错误**: 网络请求失败会重试并记录错误
- **权限错误**: 文件读取失败会记录具体错误信息
- **目录创建**: 自动创建必要的远程目录结构

## 企业级特性对比

| 策略 | 准确性 | 性能 | 网络开销 | 适用场景 |
|------|--------|------|----------|----------|
| size_hash (MD5) | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | **默认推荐**、大量小文件 |
| hash (SHA256) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | 安全敏感、重要数据 |
| etag | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 云存储、大文件 |
| size_only | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 快速预检 |

## 最佳实践

1. **日常使用**: 默认 `size_hash` 策略平衡性能和准确性（推荐）
2. **安全敏感**: 使用 `hash` 策略确保最高数据完整性
3. **大文件场景**: 使用 `etag` 策略优化大文件处理
4. **快速预检**: 使用 `size_only` 策略快速检查
5. **块大小优化**: 根据网络条件调整 `chunk_size`
6. **预演先行**: 重要同步前先用 `dry_run` 预览
7. **错误监控**: 检查 `error_files` 处理同步失败

## 注意事项

1. **网络依赖**: 需要确保与远程MCP客户端的网络连接正常
2. **认证**: 确保有足够权限访问远程目录
3. **存储空间**: 确保远程服务器有足够存储空间
4. **并发安全**: 避免同时多个同步操作到相同目标
5. **文件锁定**: 同步期间避免修改正在同步的文件
6. **时区无关**: 新版本不依赖时间戳，避免时区问题
7. **哈希计算**: 大文件哈希计算会占用CPU资源

## 监控和调试

- 查看同步结果中的`sync_summary`了解总体情况
- 检查`error_files`数组了解失败原因  
- 使用`dry_run`模式预览同步计划
- 查看服务器日志获取详细错误信息