"""
Application Settings and Configuration

Loads environment variables and provides typed configuration.
"""

import os
from typing import Optional, List, Union
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """Application configuration settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Azure AI (preferred)
    azure_ai_project_endpoint: Optional[str] = Field(default=None, alias="AZURE_AI_PROJECT_ENDPOINT")
    azure_ai_model_deployment_name: Optional[str] = Field(default=None, alias="AZURE_AI_MODEL_DEPLOYMENT_NAME")

    # Azure OpenAI (legacy fallback)
    azure_openai_endpoint: Optional[str] = Field(default=None, alias="AZURE_OPENAI_ENDPOINT")
    azure_openai_api_key: Optional[str] = Field(default=None, alias="AZURE_OPENAI_API_KEY")
    azure_openai_deployment: Optional[str] = Field(default=None, alias="AZURE_OPENAI_DEPLOYMENT")
    azure_openai_api_version: Optional[str] = Field(default="2024-08-01-preview", alias="AZURE_OPENAI_API_VERSION")
    
    # Azure API Management (APIM) AI Gateway
    apim_enabled: bool = Field(default=False, alias="APIM_ENABLED")
    apim_gateway_url: Optional[str] = Field(default=None, alias="APIM_GATEWAY_URL")
    apim_subscription_key: Optional[str] = Field(default=None, alias="APIM_SUBSCRIPTION_KEY")
    apim_subscription_header: str = Field(default="Ocp-Apim-Subscription-Key", alias="APIM_SUBSCRIPTION_HEADER")
    
    # Entra Agent ID for APIM authentication
    entra_agent_id_enabled: bool = Field(default=False, alias="ENTRA_AGENT_ID_ENABLED")
    entra_agent_tenant_id: Optional[str] = Field(default=None, alias="ENTRA_AGENT_TENANT_ID")
    entra_agent_client_id: Optional[str] = Field(default=None, alias="ENTRA_AGENT_CLIENT_ID")
    entra_agent_client_secret: Optional[str] = Field(default=None, alias="ENTRA_AGENT_CLIENT_SECRET")
    entra_agent_scope: str = Field(
        default="https://cognitiveservices.azure.com/.default",
        alias="ENTRA_AGENT_SCOPE"
    )
    
    # APIM Feature Flags
    apim_enable_load_balancing: bool = Field(default=True, alias="APIM_ENABLE_LOAD_BALANCING")
    apim_enable_rate_limiting: bool = Field(default=True, alias="APIM_ENABLE_RATE_LIMITING")
    apim_enable_content_filtering: bool = Field(default=True, alias="APIM_ENABLE_CONTENT_FILTERING")
    apim_enable_token_tracking: bool = Field(default=True, alias="APIM_ENABLE_TOKEN_TRACKING")
    apim_enable_caching: bool = Field(default=False, alias="APIM_ENABLE_CACHING")
    
    # APIM Monitoring
    apim_log_analytics_workspace_id: Optional[str] = Field(default=None, alias="APIM_LOG_ANALYTICS_WORKSPACE_ID")
    apim_application_insights_key: Optional[str] = Field(default=None, alias="APIM_APPLICATION_INSIGHTS_KEY")
    apim_debug_mode: bool = Field(default=False, alias="APIM_DEBUG_MODE")
    apim_log_request_body: bool = Field(default=False, alias="APIM_LOG_REQUEST_BODY")
    apim_log_response_body: bool = Field(default=False, alias="APIM_LOG_RESPONSE_BODY")
    
    # Financial Data APIs
    fmp_api_key: Optional[str] = Field(default=None, alias="FMP_API_KEY")
    yahoo_finance_enabled: bool = Field(default=True, alias="YAHOO_FINANCE_ENABLED")
    yahoo_finance_mcp_url: str = Field(default="http://localhost:8001/sse", alias="YAHOO_FINANCE_MCP_URL")
    sec_api_key: Optional[str] = Field(default=None, alias="SEC_API_KEY")
    sec_user_agent: str = Field(
        default="FinAgent Research Bot contact@example.com",
        alias="SEC_USER_AGENT"
    )
    
    @property
    def FMP_API_KEY(self) -> Optional[str]:
        """Uppercase alias for fmp_api_key."""
        return self.fmp_api_key
    
    @property
    def YAHOO_FINANCE_MCP_URL(self) -> str:
        """Uppercase alias for yahoo_finance_mcp_url."""
        return self.yahoo_finance_mcp_url
    
    @property
    def AZURE_OPENAI_API_KEY(self) -> Optional[str]:
        """Uppercase alias for azure_openai_api_key."""
        return self.azure_openai_api_key

    @property
    def AZURE_AI_PROJECT_ENDPOINT(self) -> Optional[str]:
        """Uppercase alias for azure_ai_project_endpoint."""
        return self.azure_ai_project_endpoint

    @property
    def AZURE_AI_MODEL_DEPLOYMENT_NAME(self) -> Optional[str]:
        """Uppercase alias for azure_ai_model_deployment_name."""
        return self.azure_ai_model_deployment_name
    
    # Azure Storage
    azure_storage_connection_string: Optional[str] = Field(
        default=None,
        alias="AZURE_STORAGE_CONNECTION_STRING"
    )
    azure_storage_container: str = Field(
        default="financial-reports",
        alias="AZURE_STORAGE_CONTAINER"
    )

    # Chat / Web PubSub
    enable_chat_autorun: bool = Field(default=True, alias="ENABLE_CHAT_AUTORUN")
    web_pubsub_connection_string: Optional[str] = Field(
        default=None,
        alias="WEB_PUBSUB_CONNECTION_STRING"
    )
    web_pubsub_hub: str = Field(default="finagent_chat", alias="WEB_PUBSUB_HUB")
    
    # Azure Cosmos DB
    cosmosdb_endpoint: Optional[str] = Field(default=None, alias="COSMOSDB_ENDPOINT")
    cosmosdb_key: Optional[str] = Field(default=None, alias="COSMOSDB_KEY")
    cosmosdb_database: str = Field(default="finagent", alias="COSMOS_DB_DATABASE")
    cosmosdb_container: str = Field(default="dynamic", alias="COSMOS_DB_CONTAINER")
    
    # Azure Authentication (for managed identity/service principal)
    azure_tenant_id: Optional[str] = Field(default=None, alias="AZURE_TENANT_ID")
    azure_client_id: Optional[str] = Field(default=None, alias="AZURE_CLIENT_ID")
    azure_client_secret: Optional[str] = Field(default=None, alias="AZURE_CLIENT_SECRET")
    
    # Uppercase aliases for compatibility
    @property
    def COSMOSDB_ENDPOINT(self) -> Optional[str]:
        """Uppercase alias for cosmosdb_endpoint."""
        return self.cosmosdb_endpoint
    
    @property
    def COSMOSDB_DATABASE(self) -> str:
        """Uppercase alias for cosmosdb_database."""
        return self.cosmosdb_database
    
    @property
    def COSMOSDB_CONTAINER(self) -> str:
        """Uppercase alias for cosmosdb_container."""
        return self.cosmosdb_container

    @property
    def ENABLE_CHAT_AUTORUN(self) -> bool:
        """Uppercase alias for enable_chat_autorun."""
        return self.enable_chat_autorun

    @property
    def WEB_PUBSUB_CONNECTION_STRING(self) -> Optional[str]:
        """Uppercase alias for web_pubsub_connection_string."""
        return self.web_pubsub_connection_string

    @property
    def WEB_PUBSUB_HUB(self) -> str:
        """Uppercase alias for web_pubsub_hub."""
        return self.web_pubsub_hub
    
    @property
    def AZURE_OPENAI_ENDPOINT(self) -> Optional[str]:
        """Uppercase alias for azure_openai_endpoint."""
        return self.azure_openai_endpoint
    
    @property
    def AZURE_OPENAI_API_VERSION(self) -> Optional[str]:
        """Uppercase alias for azure_openai_api_version."""
        return self.azure_openai_api_version
    
    @property
    def AZURE_OPENAI_DEPLOYMENT(self) -> Optional[str]:
        """Uppercase alias for azure_openai_deployment."""
        return self.azure_openai_deployment

    @property
    def DEFAULT_MODEL_DEPLOYMENT(self) -> Optional[str]:
        """Preferred model deployment alias for agents."""
        return self.azure_ai_model_deployment_name or self.azure_openai_deployment
    
    @property
    def ENABLE_M365_AGENT(self) -> bool:
        """Uppercase alias for enable_m365_agent."""
        return self.enable_m365_agent

    agent_log_format: str = Field(default="color", alias="AGENT_LOG_FORMAT")
    
    @property
    def LOG_LEVEL(self) -> str:
        """Log level for the application."""
        return "INFO"  # Default log level
    
    # Application Insights
    applicationinsights_connection_string: Optional[str] = Field(
        default=None,
        alias="APPLICATIONINSIGHTS_CONNECTION_STRING"
    )
    
    # MCP Configuration
    mcp_enabled: bool = Field(default=True, alias="MCP_ENABLED")
    mcp_server_port: int = Field(default=8100, alias="MCP_SERVER_PORT")
    
    # Backend Configuration
    backend_host: str = Field(default="0.0.0.0", alias="BACKEND_HOST")
    backend_port: int = Field(default=8000, alias="BACKEND_PORT")
    cors_origins: Union[str, List[str]] = Field(
        default="http://localhost:5173,http://localhost:3000",
        alias="CORS_ORIGINS"
    )
    enable_m365_agent: bool = Field(default=False, alias="ENABLE_M365_AGENT")
    m365_host_base_url: Optional[str] = Field(default=None, alias="M365_HOST_BASE_URL")
    m365_client_id: Optional[str] = Field(default=None, alias="M365_CLIENT_ID")
    m365_client_secret: Optional[str] = Field(default=None, alias="M365_CLIENT_SECRET")
    m365_tenant_id: Optional[str] = Field(default=None, alias="M365_TENANT_ID")
    m365_bot_id: Optional[str] = Field(default=None, alias="M365_BOT_ID")
    m365_bot_password: Optional[str] = Field(default=None, alias="M365_BOT_PASSWORD")
    
    @field_validator('cors_origins')
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS_ORIGINS from comma-separated string to list."""
        if isinstance(v, str):
            # Split by comma and strip whitespace
            origins = [origin.strip() for origin in v.split(',') if origin.strip()]
            return origins
        elif isinstance(v, list):
            return v
        return [str(v)]
    
    # Agent Configuration
    max_concurrent_agents: int = Field(default=5, alias="MAX_CONCURRENT_AGENTS")
    default_agent_timeout: int = Field(default=300, alias="DEFAULT_AGENT_TIMEOUT")
    enable_agent_telemetry: bool = Field(default=False, alias="ENABLE_AGENT_TELEMETRY")
    enable_agent_threads: bool = Field(default=False, alias="ENABLE_AGENT_THREADS")
    enable_agent_conversations: bool = Field(default=False, alias="ENABLE_AGENT_CONVERSATIONS")
    enable_application_insights_export: bool = Field(
        default=False,
        alias="ENABLE_APPLICATION_INSIGHTS_EXPORT",
    )
    
    # Execution Configuration
    max_sequential_steps: int = Field(default=10, alias="MAX_SEQUENTIAL_STEPS")
    handoff_max_iterations: int = Field(default=10, alias="HANDOFF_MAX_ITERATIONS")
    group_chat_max_turns: int = Field(default=40, alias="GROUP_CHAT_MAX_TURNS")
    
    # Observability Configuration
    observability_enabled: bool = Field(default=False, alias="OBSERVABILITY_ENABLED")
    observability_otlp_endpoint: Optional[str] = Field(default=None, alias="OBSERVABILITY_OTLP_ENDPOINT")
    observability_enable_sensitive_data: bool = Field(
        default=False,
        alias="OBSERVABILITY_ENABLE_SENSITIVE_DATA",
    )
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Get CORS origins as list."""
        if isinstance(self.cors_origins, str):
            return [origin.strip() for origin in self.cors_origins.split(",")]
        return self.cors_origins

    @property
    def APIM_ENABLED(self) -> bool:
        """Uppercase alias for apim_enabled."""
        return self.apim_enabled
    
    @property
    def APIM_GATEWAY_URL(self) -> Optional[str]:
        """Uppercase alias for apim_gateway_url."""
        return self.apim_gateway_url
    
    @property
    def ENTRA_AGENT_ID_ENABLED(self) -> bool:
        """Uppercase alias for entra_agent_id_enabled."""
        return self.entra_agent_id_enabled
    
    @property
    def agent_log_format_normalized(self) -> str:
        """Normalized log format value for renderer selection."""
        value = (self.agent_log_format or "color").strip().lower()
        if value not in {"json", "color", "console"}:
            return "color"
        return "color" if value in {"color", "console"} else "json"
    
    def model_dump_safe(self) -> dict:
        """Dump settings without sensitive data."""
        data = self.model_dump()
        # Mask sensitive fields
        sensitive_fields = [
            'azure_openai_api_key', 'fmp_api_key', 'sec_api_key',
            'azure_storage_connection_string', 'cosmos_db_key',
            'applicationinsights_connection_string', 'cosmosdb_key',
            'apim_subscription_key', 'entra_agent_client_secret',
            'm365_client_secret', 'm365_bot_password'
        ]
        for field in sensitive_fields:
            if field in data and data[field]:
                data[field] = "***REDACTED***"
        return data


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
