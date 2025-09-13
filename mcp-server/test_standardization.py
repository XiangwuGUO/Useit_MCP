#!/usr/bin/env python3
"""
MCP服务器标准化验证测试

验证core目录下的标准化组件是否正常工作，以及official_server下的服务器
是否正确使用了标准化响应格式。
"""

import sys
import os
from pathlib import Path

# 添加核心路径
current_dir = Path(__file__).parent
core_path = current_dir / "core"
sys.path.insert(0, str(core_path))

def test_core_imports():
    """测试核心组件导入"""
    print("🧪 测试核心组件导入...")
    
    try:
        from standard_response import (
            StandardMCPResponse, MCPResponseBuilder, OperationType, ResponseStatus,
            create_file_info, quick_success, quick_error
        )
        print("   ✅ standard_response 模块导入成功")
        
        from standard_tools import (
            FileSystemTool, ProcessingTool, QueryTool, standard_mcp_tool
        )
        print("   ✅ standard_tools 模块导入成功")
        
        from base_server import StandardMCPServer
        print("   ✅ base_server 模块导入成功")
        
        # 测试核心包导入
        import core
        print("   ✅ core 包导入成功")
        
        return True
        
    except Exception as e:
        print(f"   ❌ 导入失败: {e}")
        return False

def test_response_builder():
    """测试响应构建器"""
    print("\n🧪 测试响应构建器...")
    
    try:
        from core import MCPResponseBuilder, OperationType
        
        builder = MCPResponseBuilder("test_tool")
        
        # 测试成功响应
        success_response = builder.success(
            operation=OperationType.CREATE,
            message="测试成功",
            data={"created_files": 2}
        )
        
        response_dict = success_response.to_dict()
        
        # 验证必需字段
        required_fields = ["status", "operation", "message", "timestamp", "version"]
        for field in required_fields:
            assert field in response_dict, f"缺少必需字段: {field}"
        
        assert response_dict["status"] == "success"
        assert response_dict["operation"] == "create"
        
        print("   ✅ 成功响应构建正常")
        
        # 测试错误响应
        error_response = builder.error(
            operation=OperationType.READ,
            message="测试错误",
            error_details="这是一个测试错误"
        )
        
        error_dict = error_response.to_dict()
        assert error_dict["status"] == "error"
        
        print("   ✅ 错误响应构建正常")
        
        return True
        
    except Exception as e:
        print(f"   ❌ 响应构建器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_file_info():
    """测试文件信息创建"""
    print("\n🧪 测试文件信息创建...")
    
    try:
        from core import create_file_info
        
        file_info = create_file_info(
            path="test.txt",
            description="测试文件",
            size=1024,
            mime_type="text/plain"
        )
        
        # 验证字段
        assert file_info.path == "test.txt"
        assert file_info.description == "测试文件"
        assert file_info.size == 1024
        
        print("   ✅ 文件信息创建正常")
        
        return True
        
    except Exception as e:
        print(f"   ❌ 文件信息测试失败: {e}")
        return False

def test_tool_base_classes():
    """测试工具基类"""
    print("\n🧪 测试工具基类...")
    
    try:
        from core import FileSystemTool, ProcessingTool, QueryTool
        import tempfile
        
        # 测试FileSystemTool
        with tempfile.TemporaryDirectory() as temp_dir:
            fs_tool = FileSystemTool("test_fs", Path(temp_dir))
            
            # 测试路径解析
            test_path = fs_tool.resolve_path("test.txt")
            assert Path(temp_dir) in test_path.parents or test_path == Path(temp_dir) / "test.txt"
            
            print("   ✅ FileSystemTool 工作正常")
        
        # 测试ProcessingTool
        proc_tool = ProcessingTool("test_proc", Path("/tmp"))
        assert proc_tool.get_operation_type().value == "process"
        
        print("   ✅ ProcessingTool 工作正常")
        
        # 测试QueryTool
        query_tool = QueryTool("test_query", Path("/tmp"))
        assert query_tool.get_operation_type().value == "query"
        
        print("   ✅ QueryTool 工作正常")
        
        return True
        
    except Exception as e:
        print(f"   ❌ 工具基类测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_filesystem_server_structure():
    """测试filesystem服务器结构"""
    print("\n🧪 测试filesystem服务器结构...")
    
    try:
        # 检查文件是否存在
        fs_server_path = current_dir / "official_server" / "filesystem" / "server.py"
        if not fs_server_path.exists():
            print("   ❌ filesystem服务器文件不存在")
            return False
        
        # 读取文件内容，检查是否导入了标准组件
        with open(fs_server_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查关键导入
        if "from core import" not in content:
            print("   ❌ filesystem服务器未导入标准化组件")
            return False
        
        if "MCPResponseBuilder" not in content:
            print("   ❌ filesystem服务器未使用MCPResponseBuilder")
            return False
        
        print("   ✅ filesystem服务器结构正确")
        
        return True
        
    except Exception as e:
        print(f"   ❌ filesystem服务器结构测试失败: {e}")
        return False

def test_audio_slicer_server_structure():
    """测试audio_slicer服务器结构"""
    print("\n🧪 测试audio_slicer服务器结构...")
    
    try:
        # 检查文件是否存在
        audio_server_path = current_dir / "official_server" / "audio_slicer" / "server.py"
        if not audio_server_path.exists():
            print("   ❌ audio_slicer服务器文件不存在")
            return False
        
        # 读取文件内容，检查是否导入了标准组件
        with open(audio_server_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查关键导入
        if "from core import" not in content:
            print("   ❌ audio_slicer服务器未导入标准化组件")
            return False
        
        if "MCPResponseBuilder" not in content:
            print("   ❌ audio_slicer服务器未使用MCPResponseBuilder")
            return False
        
        print("   ✅ audio_slicer服务器结构正确")
        
        return True
        
    except Exception as e:
        print(f"   ❌ audio_slicer服务器结构测试失败: {e}")
        return False

def main():
    """运行所有测试"""
    print("🚀 开始MCP服务器标准化验证测试")
    print("=" * 60)
    
    tests = [
        ("核心组件导入", test_core_imports),
        ("响应构建器", test_response_builder),
        ("文件信息创建", test_file_info),
        ("工具基类", test_tool_base_classes),
        ("filesystem服务器结构", test_filesystem_server_structure),
        ("audio_slicer服务器结构", test_audio_slicer_server_structure),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                print(f"   ⚠️  {test_name} 测试失败")
        except Exception as e:
            print(f"   ❌ {test_name} 测试异常: {e}")
    
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    
    success_rate = (passed / total) * 100
    print(f"总测试数: {total}")
    print(f"通过: {passed} ✅")
    print(f"失败: {total - passed} ❌")
    print(f"通过率: {success_rate:.1f}%")
    
    if passed == total:
        print("\n🎉 所有测试通过! MCP服务器标准化实现正确。")
        print("\n✨ 标准化特性:")
        print("   - 统一的响应格式 (StandardMCPResponse)")
        print("   - 强大的响应构建器 (MCPResponseBuilder)")
        print("   - 完整的工具基类库 (FileSystemTool, ProcessingTool, QueryTool)")
        print("   - 标准化的文件信息格式 (FileInfo)")
        print("   - 核心组件模块化 (core/)")
        print("   - 服务器特异化实现 (official_server/)")
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败，需要修复。")

if __name__ == "__main__":
    main()