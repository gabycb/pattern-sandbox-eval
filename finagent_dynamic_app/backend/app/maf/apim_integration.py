"""
APIM integration for Microsoft Agent Framework (MAF) chat completions.

This module provides hooks to route MAF agent chat completions through
Azure API Management when APIM is enabled.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import structlog

from ..infra.apim_client import APIMClient

logger = structlog.get_logger(__name__)


class APIMChatCompletionHandler:
    """
    Handler that intercepts chat completion calls and routes through APIM.
    
    This is designed to work with MAF's chat completion flow.
    """
    
    def __init__(self, apim_client: APIMClient, default_deployment: str):
        """
        Initialize APIM chat completion handler.
        
        Args:
            apim_client: Initialized APIM client
            default_deployment: Default model deployment name
        """
        self.apim_client = apim_client
        self.default_deployment = default_deployment
        self._enabled = True
        logger.info("APIM chat completion handler initialized")
    
    async def handle_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Handle chat completion request through APIM.
        
        Args:
            messages: List of message dictionaries
            model: Model deployment name (optional)
            **kwargs: Additional model parameters
            
        Returns:
            Chat completion response
        """
        if not self._enabled:
            raise RuntimeError("APIM handler is disabled")
        
        deployment_id = model or self.default_deployment
        
        logger.debug(
            "Handling chat completion via APIM",
            deployment=deployment_id,
            message_count=len(messages),
            has_temperature="temperature" in kwargs,
            has_max_tokens="max_tokens" in kwargs
        )
        
        try:
            response = await self.apim_client.chat_completion(
                deployment_id=deployment_id,
                messages=messages,
                **kwargs
            )
            
            # Log success with token usage if available
            usage = response.get("usage", {})
            logger.info(
                "APIM chat completion successful",
                deployment=deployment_id,
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                total_tokens=usage.get("total_tokens")
            )
            
            return response
        
        except Exception as e:
            logger.error(
                "APIM chat completion failed",
                error=str(e),
                error_type=type(e).__name__,
                deployment=deployment_id
            )
            raise
    
    def disable(self):
        """Disable the APIM handler (for fallback scenarios)."""
        self._enabled = False
        logger.warning("APIM chat completion handler disabled")
    
    def enable(self):
        """Re-enable the APIM handler."""
        self._enabled = True
        logger.info("APIM chat completion handler enabled")
    
    @property
    def enabled(self) -> bool:
        """Check if handler is enabled."""
        return self._enabled
