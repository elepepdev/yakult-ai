# config_manager/system.py
from typing import Dict, Optional, ClassVar, Literal
from pydantic import Field, model_validator
from pydantic.dataclasses import dataclass
from .i18n import I18nMixin, Description
from ..conversations.idle_life_manager import IdleLifeConfig


class DesktopConfig(I18nMixin):
    """Desktop engine configuration."""

    engine: str = Field("electron", alias="engine")

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "engine": Description(
            en="Desktop engine to use: 'electron' (default) or 'web'",
            zh="要使用的桌面引擎：'electron'（默认）或 'web'",
        ),
    }


class FileAttachmentConfig(I18nMixin):
    """File attachment limits."""

    max_files: int = Field(5, alias="max_files")
    max_file_size_mb: int = Field(15, alias="max_file_size_mb")
    token_budget: int = Field(2000, alias="token_budget")
    enable_ocr: bool = Field(True, alias="enable_ocr")

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "max_files": Description(en="Maximum number of files per message", zh="每条消息最大文件数"),
        "max_file_size_mb": Description(en="Maximum file size in MB", zh="最大文件大小（MB）"),
        "token_budget": Description(en="Max tokens of extracted text per file", zh="每个文件提取文本的最大 token 数"),
        "enable_ocr": Description(en="OCR scanned PDFs/images as text fallback", zh="对扫描 PDF/图片启用 OCR"),
    }


class SystemConfig(I18nMixin):
    """System configuration settings."""

    conf_version: str = Field(..., alias="conf_version")
    host: str = Field(..., alias="host")
    port: int = Field(..., alias="port")
    config_alts_dir: str = Field(..., alias="config_alts_dir")
    tool_prompts: Dict[str, str] = Field(..., alias="tool_prompts")
    enable_proxy: bool = Field(False, alias="enable_proxy")
    sudo_password: Optional[str] = Field(None, alias="sudo_password")
    desktop: Optional[DesktopConfig] = Field(None, alias="desktop")
    idle_life: Optional[IdleLifeConfig] = Field(None, alias="idle_life")
    file_attachment: Optional[FileAttachmentConfig] = Field(
        None, alias="file_attachment"
    )
    ai_mode: Literal["lite", "minimal", "full_agent"] = Field(
        "full_agent", alias="ai_mode"
    )

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "conf_version": Description(en="Configuration version", zh="配置文件版本"),
        "host": Description(en="Server host address", zh="服务器主机地址"),
        "port": Description(en="Server port number", zh="服务器端口号"),
        "config_alts_dir": Description(
            en="Directory for alternative configurations", zh="备用配置目录"
        ),
        "tool_prompts": Description(
            en="Tool prompts to be inserted into persona prompt",
            zh="要插入到角色提示词中的工具提示词",
        ),
        "enable_proxy": Description(
            en="Enable proxy mode for multiple clients",
            zh="启用代理模式以支持多个客户端使用一个 ws 连接",
        ),
        "sudo_password": Description(
            en="Password for sudo commands (by AI agent)",
            zh="sudo 命令的密码（AI 代理使用）",
        ),
        "ai_mode": Description(
            en="AI capability mode: 'lite' (chat only), 'minimal' (light tools), 'full_agent' (all tools)",
            zh="AI 能力模式：'lite'（仅聊天）、'minimal'（轻量工具）、'full_agent'（全部工具）",
        ),
        "desktop": Description(
            en="Desktop engine configuration", zh="桌面引擎配置"
        ),
        "idle_life": Description(
            en="Autonomous idle life system (random talk, subconscious thoughts, dreams, moods)",
            zh="自主空闲生活系统（随机对话、潜意识想法、梦境、情绪）",
        ),
        "file_attachment": Description(
            en="File attachment limits for messages", zh="消息文件附件限制"
        ),
    }

    @model_validator(mode="after")
    def check_port(cls, values):
        port = values.port
        if port < 0 or port > 65535:
            raise ValueError("Port must be between 0 and 65535")
        return values
