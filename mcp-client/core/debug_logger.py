#!/usr/bin/env python3
"""
AI调试日志记录器
用于记录AI输入输出到时间戳文件夹中
"""

import os
import json
import random
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

class DebugLogger:
    """AI调试日志记录器"""
    
    def __init__(self, base_dir: str = "/home/ubuntu/workspace/gxw/useit_mcp_new/useit-mcp/mcp-client/mcp_ai_input"):
        self.base_dir = Path(base_dir)
        self.debug_enabled = False
        self.current_session_dir = None
        self.call_counter = 0
        
        # 确保基础目录存在
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def enable_debug(self):
        """启用调试模式"""
        self.debug_enabled = True
        self._create_session_dir()
    
    def disable_debug(self):
        """禁用调试模式"""
        self.debug_enabled = False
        self.current_session_dir = None
        self.call_counter = 0
    
    def _create_session_dir(self):
        """创建会话目录（北京时间+6位随机数）"""
        # 获取北京时间
        beijing_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 生成6位随机数
        random_suffix = f"{random.randint(100000, 999999):06d}"
        
        # 创建目录名
        session_name = f"{beijing_time}_{random_suffix}"
        self.current_session_dir = self.base_dir / session_name
        
        # 创建目录
        self.current_session_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"📁 [DEBUG] 创建调试会话目录: {self.current_session_dir}")
    
    async def log_ai_input(self, messages: List[Any], tools: List[Any] = None, metadata: Dict[str, Any] = None):
        """记录AI输入"""
        if not self.debug_enabled or not self.current_session_dir:
            return
        
        try:
            self.call_counter += 1
            
            # 构建输入数据
            input_data = {
                "timestamp": datetime.now().isoformat(),
                "type": "ai_input",
                "call_number": self.call_counter,
                "messages": self._serialize_messages(messages),
                "tools": self._serialize_tools(tools) if tools else [],
                "metadata": metadata or {}
            }
            
            # 写入文件
            filename = f"{self.call_counter:03d}_ai_input.json"
            file_path = self.current_session_dir / filename
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(input_data, f, ensure_ascii=False, indent=2)
            
            print(f"📝 [DEBUG] 记录AI输入: {filename}")
            
        except Exception as e:
            print(f"❌ [DEBUG] 记录AI输入失败: {e}")
    
    async def log_ai_output(self, response: Any, tool_calls: List[Dict[str, Any]] = None, metadata: Dict[str, Any] = None):
        """记录AI输出"""
        if not self.debug_enabled or not self.current_session_dir:
            return
        
        try:
            # 构建输出数据
            output_data = {
                "timestamp": datetime.now().isoformat(),
                "type": "ai_output",
                "call_number": self.call_counter,
                "response": self._serialize_response(response),
                "tool_calls": tool_calls or [],
                "metadata": metadata or {}
            }
            
            # 写入文件
            filename = f"{self.call_counter:03d}_ai_output.json"
            file_path = self.current_session_dir / filename
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            
            print(f"📝 [DEBUG] 记录AI输出: {filename}")
            
        except Exception as e:
            print(f"❌ [DEBUG] 记录AI输出失败: {e}")
    
    async def log_tool_execution(self, tool_name: str, tool_input: Dict[str, Any], tool_output: Any, success: bool = True, error: str = None):
        """记录工具执行"""
        if not self.debug_enabled or not self.current_session_dir:
            return
        
        try:
            # 构建工具执行数据
            tool_data = {
                "timestamp": datetime.now().isoformat(),
                "type": "tool_execution",
                "call_number": self.call_counter,
                "tool_name": tool_name,
                "tool_input": tool_input,
                "tool_output": self._serialize_tool_output(tool_output),
                "success": success,
                "error": error
            }
            
            # 写入文件
            tool_counter = len([f for f in self.current_session_dir.glob(f"{self.call_counter:03d}_tool_*.json")]) + 1
            filename = f"{self.call_counter:03d}_tool_{tool_counter:02d}_{tool_name}.json"
            file_path = self.current_session_dir / filename
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(tool_data, f, ensure_ascii=False, indent=2)
            
            print(f"🔧 [DEBUG] 记录工具执行: {filename}")
            
        except Exception as e:
            print(f"❌ [DEBUG] 记录工具执行失败: {e}")
    
    async def log_conversation_state(self, conversation: List[Any], step_number: int, metadata: Dict[str, Any] = None):
        """记录每一步完成后的conversation状态"""
        if not self.debug_enabled or not self.current_session_dir:
            return
        
        try:
            # 构建conversation状态数据
            conversation_data = {
                "timestamp": datetime.now().isoformat(),
                "type": "conversation_state",
                "call_number": self.call_counter,
                "step_number": step_number,
                "conversation": self._serialize_messages(conversation),
                "conversation_length": len(conversation),
                "metadata": metadata or {}
            }
            
            # 写入文件
            filename = f"{self.call_counter:03d}_conversation_step_{step_number:02d}.json"
            file_path = self.current_session_dir / filename
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(conversation_data, f, ensure_ascii=False, indent=2)
            
            print(f"💬 [DEBUG] 记录conversation状态: {filename} (消息数: {len(conversation)})")
            
        except Exception as e:
            print(f"❌ [DEBUG] 记录conversation状态失败: {e}")
    
    def _serialize_messages(self, messages: List[Any]) -> List[Dict[str, Any]]:
        """序列化消息列表"""
        serialized = []
        
        for msg in messages:
            try:
                if hasattr(msg, 'type') and hasattr(msg, 'content'):
                    # LangChain消息对象
                    msg_dict = {
                        "type": msg.type,
                        "content": str(msg.content)
                    }
                    
                    # 处理其他可能的属性
                    if hasattr(msg, 'tool_call_id'):
                        msg_dict["tool_call_id"] = msg.tool_call_id
                    if hasattr(msg, 'additional_kwargs'):
                        # 安全地序列化additional_kwargs
                        try:
                            json.dumps(msg.additional_kwargs)
                            msg_dict["additional_kwargs"] = msg.additional_kwargs
                        except (TypeError, ValueError):
                            msg_dict["additional_kwargs"] = str(msg.additional_kwargs)
                    if hasattr(msg, 'name'):
                        msg_dict["name"] = msg.name
                        
                    serialized.append(msg_dict)
                elif isinstance(msg, dict):
                    serialized.append(msg)
                else:
                    serialized.append({"content": str(msg)})
            except Exception as e:
                serialized.append({"error": f"序列化失败: {e}", "raw": str(msg)})
        
        return serialized
    
    def _serialize_tools(self, tools: List[Any]) -> List[Dict[str, Any]]:
        """序列化工具列表"""
        serialized = []
        
        print(f"🔍 [DEBUG] 序列化工具列表，工具数量: {len(tools)}")
        
        for i, tool in enumerate(tools):
            try:
                print(f"🔍 [DEBUG] 工具 {i}: 类型={type(tool).__name__}, 属性={[attr for attr in dir(tool) if not attr.startswith('_')][:10]}")
                
                tool_info = {
                    "name": getattr(tool, 'name', f'unknown_tool_{i}'),
                    "description": getattr(tool, 'description', ''),
                }
                
                print(f"🔍 [DEBUG] 工具 {i}: name={tool_info['name']}, description={tool_info['description'][:50]}...")
                
                # 尝试获取参数schema
                if hasattr(tool, 'args_schema') and tool.args_schema:
                    try:
                        schema = None
                        schema_type = type(tool.args_schema).__name__
                        print(f"🔍 [DEBUG] 工具 {i} args_schema类型: {schema_type}")
                        
                        # 检查是否是字典类型 (MCP inputSchema)
                        if isinstance(tool.args_schema, dict):
                            schema = tool.args_schema.copy()  # 复制避免修改原始数据
                            properties = schema.get('properties', {})
                            required = schema.get('required', [])
                            print(f"✅ [DEBUG] 工具 {i} 使用MCP字典schema")
                            print(f"   参数: {list(properties.keys())}")
                            print(f"   必需参数: {required}")
                            # 为每个属性添加更详细的信息
                            if properties:
                                for prop_name, prop_info in properties.items():
                                    prop_type = prop_info.get('type', 'unknown')
                                    prop_desc = prop_info.get('description', prop_info.get('title', ''))
                                    print(f"     - {prop_name}: {prop_type} - {prop_desc[:50]}{'...' if len(prop_desc) > 50 else ''}")
                        # Pydantic v2 model
                        elif hasattr(tool.args_schema, 'model_json_schema'):
                            schema = tool.args_schema.model_json_schema()
                            print(f"✅ [DEBUG] 工具 {i} 使用model_json_schema")
                        # Pydantic v1 model 
                        elif hasattr(tool.args_schema, 'schema'):
                            schema = tool.args_schema.schema()
                            print(f"✅ [DEBUG] 工具 {i} 使用schema方法")
                        # 从model_fields构建
                        elif hasattr(tool.args_schema, 'model_fields'):
                            print(f"🔧 [DEBUG] 工具 {i} 从model_fields构建schema")
                            fields = {}
                            for field_name, field_info in tool.args_schema.model_fields.items():
                                field_type = str(getattr(field_info, 'annotation', 'Unknown'))
                                field_desc = getattr(field_info, 'description', '')
                                required = getattr(field_info, 'is_required', lambda: False)()
                                fields[field_name] = {
                                    "type": field_type,
                                    "description": field_desc,
                                    "required": required
                                }
                            schema = {"properties": fields, "type": "object"}
                        # 检查是否有__dict__属性
                        elif hasattr(tool.args_schema, '__dict__'):
                            schema_dict = tool.args_schema.__dict__
                            schema = {
                                "type": "object",
                                "description": f"Schema for {tool_info['name']}",
                                "raw_attributes": list(schema_dict.keys()),
                                "args_schema_type": schema_type
                            }
                            print(f"🔧 [DEBUG] 工具 {i} 使用__dict__: {list(schema_dict.keys())}")
                        else:
                            # 最后的备选方案
                            schema = {
                                "type": "object", 
                                "description": f"Schema for {tool_info['name']}",
                                "args_schema_type": schema_type,
                                "available_methods": [attr for attr in dir(tool.args_schema) if not attr.startswith('_')]
                            }
                            print(f"⚠️ [DEBUG] 工具 {i} 使用备选方案，可用方法: {schema['available_methods']}")
                        
                        tool_info["args_schema"] = schema
                        print(f"✅ [DEBUG] 工具 {i} schema获取成功")
                        
                    except Exception as schema_e:
                        tool_info["args_schema"] = f"schema序列化失败: {schema_e}"
                        print(f"❌ [DEBUG] 工具 {i} schema序列化失败: {schema_e}")
                        import traceback
                        print(f"❌ [DEBUG] 详细错误: {traceback.format_exc()}")
                
                # 添加更多调试信息
                tool_info["tool_type"] = type(tool).__name__
                
                serialized.append(tool_info)
                print(f"✅ [DEBUG] 工具 {i} 序列化成功")
                
            except Exception as e:
                error_info = {
                    "error": f"序列化失败: {e}",
                    "name": f"error_tool_{i}",
                    "tool_type": type(tool).__name__ if tool else "None",
                    "raw": str(tool)[:100]
                }
                serialized.append(error_info)
                print(f"❌ [DEBUG] 工具 {i} 序列化失败: {e}")
        
        print(f"🔍 [DEBUG] 工具序列化完成，成功序列化 {len(serialized)} 个工具")
        return serialized
    
    def _serialize_response(self, response: Any) -> Dict[str, Any]:
        """序列化AI响应"""
        try:
            if hasattr(response, 'content'):
                return {
                    "content": str(response.content),
                    "type": getattr(response, 'type', 'unknown'),
                    "additional_kwargs": getattr(response, 'additional_kwargs', {})
                }
            elif isinstance(response, dict):
                # 处理包含messages的字典响应
                serialized_response = {}
                for key, value in response.items():
                    if key == 'messages':
                        # 序列化messages列表
                        serialized_response[key] = self._serialize_messages(value)
                    else:
                        # 其他字段直接复制或转换为字符串
                        try:
                            # 尝试JSON序列化测试
                            json.dumps(value)
                            serialized_response[key] = value
                        except (TypeError, ValueError):
                            # 如果不能序列化，转换为字符串
                            serialized_response[key] = str(value)
                return serialized_response
            else:
                return {"content": str(response)}
        except Exception as e:
            return {"error": f"序列化失败: {e}", "raw": str(response)}
    
    def _serialize_tool_output(self, output: Any) -> Any:
        """序列化工具输出"""
        try:
            if isinstance(output, (str, int, float, bool, list, dict)):
                return output
            elif hasattr(output, 'dict'):
                return output.model_dump()
            elif hasattr(output, '__dict__'):
                return output.__dict__
            else:
                return str(output)
        except Exception as e:
            return f"序列化失败: {e}"
    
    def get_session_info(self) -> Optional[Dict[str, Any]]:
        """获取当前会话信息"""
        if not self.debug_enabled or not self.current_session_dir:
            return None
        
        return {
            "enabled": self.debug_enabled,
            "session_dir": str(self.current_session_dir),
            "call_counter": self.call_counter,
            "files_count": len(list(self.current_session_dir.glob("*.json")))
        }

# 全局调试记录器实例
debug_logger = DebugLogger()