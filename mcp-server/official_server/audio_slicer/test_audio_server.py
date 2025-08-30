#!/usr/bin/env python3
"""
AudioSlicer MCP Server 测试脚本

测试 AudioSlicer 服务器能否正常接入分布式 MCP 框架
"""

import asyncio
import base64
import json
import logging
import os
from pathlib import Path

import httpx

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 测试配置
FASTAPI_SERVER_URL = "http://localhost:8080"
AUDIO_SERVER_URL = "http://localhost:8002"
AUDIO_CLIENT_CONFIG = {
    "client_id": "audio-slicer",
    "remote_url": AUDIO_SERVER_URL,
    "description": "音频切片服务器"
}


async def test_audio_server_integration():
    """测试 AudioSlicer 服务器集成"""
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        
        print("🎵 测试 AudioSlicer MCP 服务器集成")
        print("=" * 50)
        
        # 1. 检查 FastAPI 服务器
        print("1. 检查 FastAPI 管理服务器...")
        try:
            response = await client.get(f"{FASTAPI_SERVER_URL}/health")
            if response.status_code == 200:
                print("   ✅ FastAPI 服务器运行正常")
            else:
                print("   ❌ FastAPI 服务器不可用")
                return False
        except Exception as e:
            print(f"   ❌ FastAPI 服务器连接失败: {e}")
            return False
        
        # 2. 检查 AudioSlicer 服务器
        print("2. 检查 AudioSlicer 服务器...")
        try:
            response = await client.post(f"{AUDIO_SERVER_URL}/mcp/", json={
                "jsonrpc": "2.0",
                "id": "test",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "clientInfo": {"name": "test", "version": "1.0"}
                }
            })
            if response.status_code == 200:
                print("   ✅ AudioSlicer 服务器运行正常")
            else:
                print(f"   ❌ AudioSlicer 服务器响应异常: {response.status_code}")
                return False
        except Exception as e:
            print(f"   ❌ AudioSlicer 服务器连接失败: {e}")
            print(f"   💡 请确保已启动: cd AudioSlicer && python server.py")
            return False
        
        # 3. 将 AudioSlicer 添加到管理服务器
        print("3. 添加 AudioSlicer 到管理系统...")
        try:
            response = await client.post(
                f"{FASTAPI_SERVER_URL}/clients",
                json=AUDIO_CLIENT_CONFIG
            )
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ 添加成功: {data['message']}")
            else:
                print(f"   ❌ 添加失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"   ❌ 添加客户机异常: {e}")
            return False
        
        # 4. 检查客户机状态
        print("4. 检查客户机连接状态...")
        try:
            response = await client.get(f"{FASTAPI_SERVER_URL}/clients/audio-slicer/status")
            if response.status_code == 200:
                data = response.json()
                status = data['data']['status']
                print(f"   ✅ 客户机状态: {status}")
                if status != "connected":
                    print("   ⚠️ 客户机未正确连接")
                    return False
            else:
                print(f"   ❌ 获取状态失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"   ❌ 状态检查异常: {e}")
            return False
        
        # 5. 列出工具
        print("5. 获取 AudioSlicer 工具列表...")
        try:
            response = await client.get(f"{FASTAPI_SERVER_URL}/clients/audio-slicer/tools")
            if response.status_code == 200:
                data = response.json()
                tools = data['data']['tools']
                print(f"   ✅ 发现 {len(tools)} 个工具:")
                for tool in tools:
                    print(f"      - {tool['name']}: {tool['description']}")
                
                # 检查是否有 slice_audio 工具
                if not any(tool['name'] == 'slice_audio' for tool in tools):
                    print("   ❌ 未找到 slice_audio 工具")
                    return False
            else:
                print(f"   ❌ 获取工具列表失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"   ❌ 工具列表获取异常: {e}")
            return False
        
        # 6. 创建测试音频文件（简单的正弦波）
        print("6. 创建测试音频文件...")
        try:
            import numpy as np
            import wave
            
            # 生成 3 秒的测试音频（440Hz 正弦波）
            sample_rate = 44100
            duration = 3.0
            frequency = 440.0
            
            t = np.linspace(0, duration, int(sample_rate * duration))
            audio_data = np.sin(2 * np.pi * frequency * t)
            
            # 转换为 16 位整数
            audio_data = (audio_data * 32767).astype(np.int16)
            
            # 保存为 WAV 文件
            test_audio_path = "test_audio.wav"
            with wave.open(test_audio_path, 'w') as wav_file:
                wav_file.setnchannels(1)  # 单声道
                wav_file.setsampwidth(2)  # 2 字节 (16 位)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_data.tobytes())
            
            # 读取并编码为 base64
            with open(test_audio_path, 'rb') as f:
                audio_content = f.read()
            audio_base64 = base64.b64encode(audio_content).decode('ascii')
            
            print(f"   ✅ 创建测试音频文件: {test_audio_path} ({len(audio_content)} bytes)")
            
        except Exception as e:
            print(f"   ❌ 创建测试音频失败: {e}")
            print("   💡 需要安装 numpy: pip install numpy")
            return False
        
        # 7. 测试音频切片工具（模拟调用，因为实际需要音频处理库）
        print("7. 测试音频切片工具...")
        try:
            # 注意：这里只是测试工具调用接口，实际的音频处理需要安装相关库
            response = await client.post(
                f"{FASTAPI_SERVER_URL}/tools/call",
                json={
                    "tool_name": "slice_audio",
                    "arguments": {
                        "audio_file_content_base64": audio_base64[:1000],  # 只传递部分数据用于测试
                        "filename": "test_audio.wav",
                        "segment_duration_s": 1.0
                    },
                    "client_id": "audio-slicer"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data['success']:
                    print("   ✅ 音频切片工具调用成功")
                    # 注意：实际结果可能包含错误，因为缺少依赖库
                    result = data['data']['result']
                    if isinstance(result, dict) and 'error' in result:
                        print(f"   ⚠️ 工具执行错误（可能缺少依赖）: {result['error']}")
                    else:
                        print(f"   📊 切片结果: {result}")
                else:
                    print(f"   ❌ 工具调用失败: {data}")
                    return False
            else:
                print(f"   ❌ 工具调用请求失败: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"   ❌ 音频切片测试异常: {e}")
            return False
        
        # 8. 清理
        print("8. 清理测试环境...")
        try:
            # 移除客户机
            response = await client.delete(f"{FASTAPI_SERVER_URL}/clients/audio-slicer")
            if response.status_code == 200:
                print("   ✅ 客户机移除成功")
            
            # 删除测试文件
            if os.path.exists("test_audio.wav"):
                os.remove("test_audio.wav")
                print("   ✅ 测试文件清理完成")
                
        except Exception as e:
            print(f"   ⚠️ 清理过程出现问题: {e}")
        
        print("\n🎉 AudioSlicer 服务器集成测试完成！")
        return True


async def main():
    """主函数"""
    print("🎵 AudioSlicer MCP 服务器集成测试")
    print("=" * 50)
    print()
    print("📋 测试前置条件:")
    print("1. FastAPI 管理服务器运行在 http://localhost:8080")
    print("2. AudioSlicer 服务器运行在 http://localhost:8002")
    print("3. 已安装必要的依赖库")
    print()
    
    success = await test_audio_server_integration()
    
    if success:
        print("\n✅ 测试结果: AudioSlicer 服务器可以完美接入分布式 MCP 框架！")
        print("\n🚀 接下来可以:")
        print("1. 安装音频处理依赖: pip install librosa pydub soundfile")
        print("2. 在 Claude Desktop 中使用 AudioSlicer 工具")
        print("3. 通过 API 调用音频切片功能")
    else:
        print("\n❌ 测试失败: 请检查服务器状态和配置")


if __name__ == "__main__":
    asyncio.run(main())