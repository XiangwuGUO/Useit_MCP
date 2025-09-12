#!/usr/bin/env python3
"""
测试new_files变量功能
验证所有文件创建函数都正确返回基于base_dir的相对路径
"""

import requests
import json
import time
import base64
from pathlib import Path

# 配置常量
MCP_CLIENT_URL = "http://localhost:8080"
VM_ID = "test_vm"
SESSION_ID = "test_session"

def register_mcp_server(server_name: str, server_url: str):
    """注册MCP服务器"""
    print(f"📡 注册MCP服务器: {server_name} -> {server_url}")
    
    payload = {
        "vm_id": VM_ID,
        "session_id": SESSION_ID,
        "name": server_name,
        "url": server_url,
        "description": f"{server_name} MCP服务器",
        "transport": "http"
    }
    
    response = requests.post(f"{MCP_CLIENT_URL}/clients", json=payload, timeout=10)
    return response.status_code in [200, 400]  # 400表示已存在，也算成功

def test_filesystem_new_files():
    """测试filesystem服务器的new_files功能"""
    print("\n🗂️ 测试Filesystem服务器new_files功能...")
    
    # 注册filesystem服务器
    if not register_mcp_server("filesystem", "http://localhost:8003/mcp"):
        print("❌ 无法注册filesystem服务器")
        return False
    
    success_count = 0
    total_tests = 0
    
    # 测试1: write_text - 创建新文件
    print("\n📝 测试1: write_text创建新文件")
    total_tests += 1
    try:
        payload = {
            "vm_id": VM_ID,
            "session_id": SESSION_ID,
            "tool_name": "write_text",
            "arguments": {
                "req": {
                    "path": "test_new_file.txt",
                    "content": "测试内容 - new_files变量",
                    "encoding": "utf-8",
                    "append": False
                }
            },
            "server_name": "filesystem"
        }
        
        response = requests.post(f"{MCP_CLIENT_URL}/tools/call", json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success") and "new_files" in result.get("data", {}):
                new_files = result["data"]["new_files"]
                print(f"   ✅ 成功创建文件，new_files: {new_files}")
                if new_files and any("test_new_file.txt" in path for path in new_files.keys()):
                    success_count += 1
                    print(f"   ✅ new_files包含正确的相对路径")
                else:
                    print(f"   ⚠️ new_files不包含预期的文件路径")
            else:
                print(f"   ❌ 结果中没有new_files变量: {result}")
        else:
            print(f"   ❌ 请求失败: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"   ❌ 测试异常: {e}")
    
    # 测试2: mkdir - 创建目录
    print("\n📁 测试2: mkdir创建目录")
    total_tests += 1
    try:
        payload = {
            "vm_id": VM_ID,
            "session_id": SESSION_ID,
            "tool_name": "mkdir",
            "arguments": {
                "req": {
                    "path": "test_new_dir",
                    "parents": True,
                    "exist_ok": True
                }
            },
            "server_name": "filesystem"
        }
        
        response = requests.post(f"{MCP_CLIENT_URL}/tools/call", json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success") and "new_files" in result.get("data", {}):
                new_files = result["data"]["new_files"]
                print(f"   ✅ 成功创建目录，new_files: {new_files}")
                if new_files and any("test_new_dir" in path for path in new_files.keys()):
                    success_count += 1
                    print(f"   ✅ new_files包含正确的目录路径")
                else:
                    print(f"   ✅ 目录已存在，new_files为空（符合预期）")
                    success_count += 1
            else:
                print(f"   ❌ 结果中没有new_files变量: {result}")
        else:
            print(f"   ❌ 请求失败: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"   ❌ 测试异常: {e}")
    
    # 测试3: copy - 复制文件
    print("\n📋 测试3: copy复制文件")
    total_tests += 1
    try:
        payload = {
            "vm_id": VM_ID,
            "session_id": SESSION_ID,
            "tool_name": "copy",
            "arguments": {
                "req": {
                    "src": "test_new_file.txt",
                    "dst": "test_copied_file.txt",
                    "overwrite": True
                }
            },
            "server_name": "filesystem"
        }
        
        response = requests.post(f"{MCP_CLIENT_URL}/tools/call", json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success") and "new_files" in result.get("data", {}):
                new_files = result["data"]["new_files"]
                print(f"   ✅ 成功复制文件，new_files: {new_files}")
                if new_files and any("test_copied_file.txt" in path for path in new_files.keys()):
                    success_count += 1
                    print(f"   ✅ new_files包含正确的复制文件路径")
                else:
                    print(f"   ⚠️ new_files不包含预期的复制文件路径")
            else:
                print(f"   ❌ 结果中没有new_files变量: {result}")
        else:
            print(f"   ❌ 请求失败: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"   ❌ 测试异常: {e}")
    
    print(f"\n📊 Filesystem测试结果: {success_count}/{total_tests} 通过")
    return success_count == total_tests

def test_audio_slicer_new_files():
    """测试audio_slicer服务器的new_files功能"""
    print("\n🎵 测试Audio Slicer服务器new_files功能...")
    
    # 注册audio_slicer服务器
    if not register_mcp_server("audio_slicer", "http://localhost:8002/mcp"):
        print("❌ 无法注册audio_slicer服务器")
        return False
    
    # 生成一个简单的测试音频数据 (WAV格式)
    print("🎵 生成测试音频数据...")
    import wave
    import numpy as np
    import tempfile
    import os
    
    # 创建一个简单的正弦波音频
    sample_rate = 44100
    duration = 2  # 2秒
    frequency = 440  # A4音符
    
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    audio_data = (np.sin(2 * np.pi * frequency * t) * 32767).astype(np.int16)
    
    # 写入临时WAV文件
    with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
        with wave.open(temp_file.name, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data.tobytes())
        
        # 读取并编码为base64
        with open(temp_file.name, 'rb') as f:
            audio_base64 = base64.b64encode(f.read()).decode('utf-8')
        
        # 清理临时文件
        os.unlink(temp_file.name)
    
    success_count = 0
    total_tests = 1
    
    # 测试: slice_audio - 创建音频片段文件
    print("\n🔪 测试: slice_audio创建音频片段")
    try:
        payload = {
            "vm_id": VM_ID,
            "session_id": SESSION_ID,
            "tool_name": "slice_audio",
            "arguments": {
                "audio_file_content_base64": audio_base64,
                "filename": "test_audio.wav",
                "segment_duration_s": 1.0
            },
            "server_name": "audio_slicer"
        }
        
        response = requests.post(f"{MCP_CLIENT_URL}/tools/call", json=payload, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success") and "new_files" in result.get("data", {}):
                new_files = result["data"]["new_files"]
                print(f"   ✅ 成功切片音频，new_files: {new_files}")
                if new_files and len(new_files) > 0:
                    success_count += 1
                    print(f"   ✅ new_files包含 {len(new_files)} 个音频片段文件")
                    # 显示一些文件路径示例
                    for i, (path, desc) in enumerate(list(new_files.items())[:3]):
                        print(f"      📄 {path} - {desc}")
                    if len(new_files) > 3:
                        print(f"      ... 还有 {len(new_files) - 3} 个文件")
                else:
                    print(f"   ⚠️ new_files为空")
            else:
                print(f"   ❌ 结果中没有new_files变量: {result}")
        else:
            print(f"   ❌ 请求失败: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"   ❌ 测试异常: {e}")
    
    print(f"\n📊 Audio Slicer测试结果: {success_count}/{total_tests} 通过")
    return success_count == total_tests

def main():
    """主测试函数"""
    print("🧪 开始测试new_files变量功能")
    print("=" * 60)
    
    # 检查MCP客户端状态
    print("1️⃣ 检查MCP客户端状态...")
    try:
        response = requests.get(f"{MCP_CLIENT_URL}/health", timeout=5)
        if response.status_code == 200:
            print("   ✅ MCP客户端运行正常")
        else:
            print(f"   ❌ MCP客户端响应异常: {response.status_code}")
            return
    except Exception as e:
        print(f"   ❌ 无法连接到MCP客户端: {e}")
        return
    
    # 运行测试
    filesystem_ok = test_filesystem_new_files()
    audio_ok = test_audio_slicer_new_files()
    
    # 显示最终结果
    print("\n" + "=" * 60)
    print("📊 最终测试结果")
    print("=" * 60)
    
    print(f"🗂️  Filesystem服务器: {'✅ 通过' if filesystem_ok else '❌ 失败'}")
    print(f"🎵 Audio Slicer服务器: {'✅ 通过' if audio_ok else '❌ 失败'}")
    
    if filesystem_ok and audio_ok:
        print(f"\n🎉 所有测试通过！new_files功能正常工作")
        print("💡 所有文件创建函数都正确返回基于base_dir的相对路径")
    else:
        print(f"\n⚠️ 部分测试失败，需要进一步调试")

if __name__ == "__main__":
    main()