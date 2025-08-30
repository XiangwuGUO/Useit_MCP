# AudioSlicer MCP Server

🎵 **音频切片 MCP 服务器** - 基于节拍检测的智能音频分割工具

## 🎯 功能特性

- ✅ **节拍检测** - 使用 librosa 进行精准节拍分析
- ✅ **智能切片** - 在节拍点进行切割，保持音乐完整性
- ✅ **灵活时长** - 支持自定义分段目标时长
- ✅ **Base64 输入** - 支持通过 base64 编码传输音频文件
- ✅ **标准 MCP 协议** - 完全兼容分布式 MCP 框架

## 📦 安装依赖

```bash
# 安装音频处理依赖
pip install librosa pydub soundfile numpy

# 可选：安装 ffmpeg 支持更多音频格式
# Ubuntu/Debian: sudo apt install ffmpeg
# macOS: brew install ffmpeg
# Windows: 下载 ffmpeg 并添加到 PATH
```

## 🚀 启动服务器

### HTTP 模式（推荐用于分布式架构）
```bash
cd AudioSlicer
python server.py
# 服务器将在 http://localhost:8002/mcp 启动
```

### stdio 模式
```bash
python server.py stdio
```

## 🔧 集成到分布式 MCP 系统

### 1. 添加到管理服务器
```bash
curl -X POST http://localhost:8080/clients \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "audio-slicer", 
    "remote_url": "http://localhost:8002",
    "description": "AudioSlicer 音频切片服务器"
  }'
```

### 2. 在 Claude Desktop 中使用
```
# 添加 AudioSlicer 客户机
add_client("audio-slicer", "http://localhost:8002", "音频切片服务器")

# 查看可用工具
list_all_tools()

# 调用音频切片工具
call_remote_tool("slice_audio", {
  "audio_file_content_base64": "UklGRi4AAABXQVZFZm10...",  // 音频文件的 base64 编码
  "filename": "music.mp3",
  "segment_duration_s": 30.0
}, "audio-slicer")
```

## 🛠️ 工具详情

### slice_audio
将音频文件基于节拍检测切割成指定时长的片段。

**参数:**
- `audio_file_content_base64` (string): 音频文件内容的 base64 编码
- `filename` (string): 原始文件名 (如 'track.mp3')
- `segment_duration_s` (float): 目标片段时长（秒）

**返回:**
```json
{
  "message": "Successfully sliced audio into 5 segments.",
  "segment_paths": [
    "output_audio/track_segment_1.wav",
    "output_audio/track_segment_2.wav",
    "output_audio/track_segment_3.wav",
    "output_audio/track_segment_4.wav", 
    "output_audio/track_segment_5.wav"
  ]
}
```

## 🎵 算法说明

### 节拍检测
使用 librosa 的 `beat_track` 函数进行节拍检测：
1. 分析音频频谱特征
2. 识别节拍时间点
3. 计算最优切割位置

### 智能切割
切割算法会寻找最接近目标时长的节拍点：
1. 从当前位置开始累积时长
2. 比较当前节拍点和下一个节拍点与目标时长的差距
3. 选择误差最小的切割点
4. 确保每个片段都在节拍边界上切割

## 📊 使用示例

### Python API 调用
```python
import base64
import httpx

# 读取音频文件
with open('music.mp3', 'rb') as f:
    audio_data = f.read()
audio_base64 = base64.b64encode(audio_data).decode('ascii')

# 调用切片 API
async with httpx.AsyncClient() as client:
    response = await client.post("http://localhost:8080/tools/call", json={
        "tool_name": "slice_audio",
        "arguments": {
            "audio_file_content_base64": audio_base64,
            "filename": "music.mp3", 
            "segment_duration_s": 30.0
        },
        "client_id": "audio-slicer"
    })
    result = response.json()
    print(f"切片结果: {result}")
```

### 命令行测试
```bash
# 测试服务器连接
python test_audio_server.py
```

## 🔍 故障排除

### 常见问题

1. **依赖缺失**
   ```
   ModuleNotFoundError: No module named 'librosa'
   ```
   **解决方案:** 安装音频处理依赖
   ```bash
   pip install librosa pydub soundfile
   ```

2. **ffmpeg 警告**
   ```
   RuntimeWarning: Couldn't find ffmpeg or avconv
   ```
   **解决方案:** 安装 ffmpeg
   ```bash
   # Ubuntu/Debian
   sudo apt install ffmpeg
   
   # macOS
   brew install ffmpeg
   ```

3. **内存不足**
   ```
   MemoryError: Unable to allocate array
   ```
   **解决方案:** 
   - 减少音频文件大小
   - 增加系统内存
   - 使用较低的采样率

4. **切片结果为空**
   **可能原因:**
   - 音频文件太短
   - 节拍检测失败
   - 目标时长设置不合理
   
   **解决方案:**
   - 检查音频文件是否有节拍
   - 调整 `segment_duration_s` 参数
   - 尝试不同类型的音频文件

## 🔒 安全注意事项

1. **文件大小限制** - 建议限制上传音频文件大小（如 50MB）
2. **临时文件清理** - 系统会自动清理处理过程中的临时文件
3. **输出目录** - 输出文件保存在 `output_audio/` 目录下
4. **内存管理** - 大文件处理时注意内存使用量

## 📈 性能优化

1. **批处理** - 支持批量处理多个音频文件
2. **缓存** - 对相同参数的请求可以实现缓存
3. **并发** - 支持多个客户机同时使用
4. **格式优化** - 输出格式可配置（WAV、MP3 等）

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

可以扩展的功能：
- 支持更多音频格式
- 添加音频质量调节
- 实现自定义切片规则
- 添加音频预览功能

## 📄 许可证

MIT License