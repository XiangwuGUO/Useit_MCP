"""
配置管理

统一管理所有配置项，支持环境变量和配置文件
"""

import os
from typing import Optional
from pathlib import Path

try:
    from dotenv import load_dotenv
    # 加载.env文件
    env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(env_path)
except ImportError:
    print("⚠️ python-dotenv not found, .env files will not be loaded")


class Settings:
    """应用配置"""
    
    def __init__(self):
        # === 服务器配置 ===
        self.host = os.getenv("MCP_GATEWAY_HOST", "0.0.0.0")
        self.port = int(os.getenv("MCP_GATEWAY_PORT", "8080"))
        
        # === API配置 ===
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.claude_model = os.getenv("CLAUDE_MODEL", "claude-3-sonnet-20240229")
        self.claude_api_timeout = int(os.getenv("CLAUDE_API_TIMEOUT", "300"))
        
        # === 客户机连接配置 ===
        self.client_timeout = int(os.getenv("CLIENT_TIMEOUT", "30"))
        self.max_clients = int(os.getenv("MAX_CLIENTS", "100"))
        
        # === 任务执行配置 ===
        self.default_max_steps = int(os.getenv("DEFAULT_MAX_STEPS", "10"))
        self.task_timeout = int(os.getenv("TASK_TIMEOUT", "600"))
        
        # === 日志配置 ===
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.log_file = os.getenv("LOG_FILE")
        
        # === 其他配置 ===
        cors_origins_str = os.getenv("CORS_ORIGINS", "*")
        self.cors_origins = [cors_origins_str] if cors_origins_str != "*" else ["*"]
        self.enable_docs = os.getenv("ENABLE_DOCS", "true").lower() == "true"


# 全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取配置实例"""
    return settings


def validate_required_settings() -> bool:
    """验证必需的配置"""
    errors = []
    
    if not settings.anthropic_api_key:
        errors.append("ANTHROPIC_API_KEY 环境变量未设置，智能任务功能将不可用")
    
    if errors:
        for error in errors:
            print(f"⚠️ 配置警告: {error}")
    
    return len(errors) == 0