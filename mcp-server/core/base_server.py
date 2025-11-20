#!/usr/bin/env python3
"""
企业级MCP服务器基类
符合公司开发标准，提供统一的服务器名称管理和配置
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from mcp.server.fastmcp import FastMCP


class MCPServerConfig:
    """MCP服务器配置类"""
    
    def __init__(
        self,
        server_name: str,
        title: str,
        description: str,
        port: int,
        version: str = "1.0.0"
    ):
        self.server_name = server_name
        self.title = title
        self.description = description
        self.port = port
        self.version = version
        
        # 验证服务器名称符合规范
        self._validate_server_name()
    
    def _validate_server_name(self):
        """验证服务器名称符合企业规范"""
        if not self.server_name:
            raise ValueError("服务器名称不能为空")
        
        if not self.server_name.islower():
            raise ValueError(f"服务器名称必须为小写: {self.server_name}")
        
        if " " in self.server_name:
            raise ValueError(f"服务器名称不能包含空格: {self.server_name}")
        
        # 只允许字母、数字和下划线
        if not self.server_name.replace("_", "").isalnum():
            raise ValueError(f"服务器名称只能包含字母、数字和下划线: {self.server_name}")


class StandardMCPServer(ABC):
    """标准化MCP服务器基类"""
    
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._mcp_instance = None
        self._initialize_server()
    
    def _initialize_server(self):
        """初始化MCP服务器实例"""
        self._mcp_instance = FastMCP(
            name=self.config.server_name,  # 确保服务器名称正确传递
            title=self.config.title,
            description=self.config.description,
            port=self.config.port
        )
        
        # 注册工具
        self._register_tools()
    
    @property
    def mcp(self) -> FastMCP:
        """获取MCP服务器实例"""
        return self._mcp_instance
    
    @property
    def server_name(self) -> str:
        """获取服务器名称"""
        return self.config.server_name
    
    @abstractmethod
    def _register_tools(self):
        """注册工具 - 子类必须实现"""
        pass
    
    def get_server_info(self) -> Dict[str, Any]:
        """获取服务器信息"""
        return {
            "server_name": self.config.server_name,
            "title": self.config.title,
            "description": self.config.description,
            "port": self.config.port,
            "version": self.config.version
        }
    
    def run(self, host: str = "0.0.0.0"):
        """启动服务器"""
        print(f"🚀 启动 {self.config.title} ({self.config.server_name})")
        print(f"   📍 地址: http://{host}:{self.config.port}")
        print(f"   📝 描述: {self.config.description}")
        
        # 运行服务器 - FastMCP.run()不接受host参数
        if self._mcp_instance:
            self._mcp_instance.run()
        else:
            raise RuntimeError("MCP服务器实例未初始化")


# 企业标准服务器配置
class ServerConfigs:
    """预定义的服务器配置"""
    
    FILESYSTEM = MCPServerConfig(
        server_name="filesystem",
        title="文件系统服务",
        description="提供文件系统操作功能，包括文件读写、目录管理等",
        port=8003
    )
    
    AUDIO_SLICER = MCPServerConfig(
        server_name="audio_slicer",
        title="音频切片服务",
        description="提供音频文件切片和处理功能",
        port=8002
    )

    EXCEL = MCPServerConfig(
        server_name="excel",
        title="Excel控制服务",
        description="基于COM的Excel自动化操作服务，支持工作簿、工作表、单元格的创建、修改、删除和公式操作",
        port=8004
    )

    @classmethod
    def get_config(cls, server_name: str) -> Optional[MCPServerConfig]:
        """根据服务器名称获取配置"""
        configs = {
            "filesystem": cls.FILESYSTEM,
            "audio_slicer": cls.AUDIO_SLICER,
            "excel": cls.EXCEL
        }
        return configs.get(server_name)

    @classmethod
    def list_configs(cls) -> Dict[str, MCPServerConfig]:
        """列出所有配置"""
        return {
            "filesystem": cls.FILESYSTEM,
            "audio_slicer": cls.AUDIO_SLICER,
            "excel": cls.EXCEL
        }


def create_standard_server(server_name: str) -> MCPServerConfig:
    """创建标准服务器配置的工厂方法"""
    config = ServerConfigs.get_config(server_name)
    if not config:
        raise ValueError(f"未知的服务器类型: {server_name}")
    return config