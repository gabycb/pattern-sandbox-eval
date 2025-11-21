"""
Azure API Management (APIM) Client for AI Gateway Integration

Provides a client for routing AI requests through Azure API Management,
supporting authentication, load balancing, rate limiting, and monitoring.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from enum import Enum

import httpx
import structlog
from azure.identity.aio import DefaultAzureCredential, ClientSecretCredential

from .settings import Settings

logger = structlog.get_logger(__name__)


class APIMAuthType(str, Enum):
    """Authentication types for APIM."""
    SUBSCRIPTION_KEY = "subscription_key"
    ENTRA_AGENT_ID = "entra_agent_id"
    MANAGED_IDENTITY = "managed_identity"


class APIMTokenCache:
    """Simple token cache for Entra Agent ID authentication."""
    
    def __init__(self):
        self._token: Optional[str] = None
        self._expiry: Optional[datetime] = None
        self._lock = asyncio.Lock()
    
    async def get_token(
        self,
        credential: Union[DefaultAzureCredential, ClientSecretCredential],
        scope: str
    ) -> str:
        """Get cached token or fetch new one."""
        async with self._lock:
            now = datetime.utcnow()
            
            # Return cached token if valid
            if self._token and self._expiry and now < self._expiry:
                logger.debug("Using cached Entra token")
                return self._token
            
            # Fetch new token
            logger.debug("Fetching new Entra token", scope=scope)
            token_result = await credential.get_token(scope)
            self._token = token_result.token
            
            # Set expiry with 5-minute buffer
            self._expiry = now + timedelta(seconds=token_result.expires_on - time.time() - 300)
            
            logger.info("Entra token acquired", expiry=self._expiry.isoformat())
            return self._token


class APIMClient:
    """
    Client for Azure API Management AI Gateway.
    
    Handles authentication, request routing, retry logic, and telemetry
    for AI model calls through APIM.
    """
    
    def __init__(self, settings: Settings):
        """
        Initialize APIM client.
        
        Args:
            settings: Application settings with APIM configuration
        """
        self.settings = settings
        self._http_client: Optional[httpx.AsyncClient] = None
        self._credential: Optional[Union[DefaultAzureCredential, ClientSecretCredential]] = None
        self._token_cache = APIMTokenCache()
        
        # Validate configuration
        if settings.apim_enabled:
            if not settings.apim_gateway_url:
                raise ValueError("APIM_GATEWAY_URL is required when APIM_ENABLED=true")
            
            # Determine auth type
            if settings.entra_agent_id_enabled:
                self._auth_type = APIMAuthType.ENTRA_AGENT_ID
                if not all([
                    settings.entra_agent_tenant_id,
                    settings.entra_agent_client_id,
                    settings.entra_agent_client_secret
                ]):
                    raise ValueError(
                        "Entra Agent ID requires ENTRA_AGENT_TENANT_ID, "
                        "ENTRA_AGENT_CLIENT_ID, and ENTRA_AGENT_CLIENT_SECRET"
                    )
            elif settings.apim_subscription_key:
                self._auth_type = APIMAuthType.SUBSCRIPTION_KEY
            else:
                self._auth_type = APIMAuthType.MANAGED_IDENTITY
            
            logger.info(
                "APIM client initialized",
                gateway_url=settings.apim_gateway_url,
                auth_type=self._auth_type.value
            )
    
    async def initialize(self):
        """Initialize async resources."""
        if not self.settings.apim_enabled:
            return
        
        # Create HTTP client with timeout and retry configuration
        timeout = httpx.Timeout(120.0, connect=10.0)
        limits = httpx.Limits(max_keepalive_connections=20, max_connections=100)
        
        self._http_client = httpx.AsyncClient(
            timeout=timeout,
            limits=limits,
            http2=True,
            follow_redirects=False
        )
        
        # Initialize credential for Entra authentication
        if self._auth_type == APIMAuthType.ENTRA_AGENT_ID:
            self._credential = ClientSecretCredential(
                tenant_id=self.settings.entra_agent_tenant_id,
                client_id=self.settings.entra_agent_client_id,
                client_secret=self.settings.entra_agent_client_secret
            )
            logger.info("Entra Agent ID credential initialized")
        elif self._auth_type == APIMAuthType.MANAGED_IDENTITY:
            self._credential = DefaultAzureCredential(
                exclude_interactive_browser_credential=True
            )
            logger.info("Managed Identity credential initialized")
        
        logger.info("APIM client initialized successfully")
    
    async def shutdown(self):
        """Cleanup async resources."""
        if self._http_client:
            await self._http_client.aclose()
            logger.debug("APIM HTTP client closed")
        
        if self._credential:
            await self._credential.close()
            logger.debug("APIM credential closed")
    
    async def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for APIM request."""
        headers = {}
        
        if self._auth_type == APIMAuthType.SUBSCRIPTION_KEY:
            headers[self.settings.apim_subscription_header] = self.settings.apim_subscription_key
        
        elif self._auth_type in (APIMAuthType.ENTRA_AGENT_ID, APIMAuthType.MANAGED_IDENTITY):
            token = await self._token_cache.get_token(
                self._credential,
                self.settings.entra_agent_scope
            )
            headers["Authorization"] = f"Bearer {token}"
        
        return headers
    
    async def _make_request(
        self,
        method: str,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
        query_params: Optional[Dict[str, str]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        retry_count: int = 3
    ) -> Dict[str, Any]:
        """
        Make HTTP request to APIM with retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (relative to gateway URL)
            json_data: JSON request body
            query_params: Query parameters
            extra_headers: Additional headers
            retry_count: Number of retries on failure
            
        Returns:
            JSON response from APIM
            
        Raises:
            httpx.HTTPError: On request failure after retries
        """
        if not self._http_client:
            raise RuntimeError("APIM client not initialized. Call initialize() first.")
        
        url = f"{self.settings.apim_gateway_url.rstrip('/')}/{path.lstrip('/')}"
        
        # Build headers
        headers = await self._get_auth_headers()
        headers["Content-Type"] = "application/json"
        headers["User-Agent"] = "FinAgent-Dynamic/2.0"
        
        # Add custom headers for APIM features
        if self.settings.apim_enable_token_tracking:
            headers["X-APIM-Track-Tokens"] = "true"
        
        if self.settings.apim_debug_mode:
            headers["X-APIM-Debug"] = "true"
        
        if extra_headers:
            headers.update(extra_headers)
        
        # Retry loop with exponential backoff
        last_error = None
        for attempt in range(retry_count):
            try:
                start_time = time.time()
                
                # Log request (excluding sensitive data unless debug mode)
                log_data = {
                    "method": method,
                    "url": url,
                    "attempt": attempt + 1
                }
                
                if self.settings.apim_log_request_body and json_data:
                    log_data["request_body"] = json_data
                
                logger.debug("APIM request", **log_data)
                
                # Make request
                response = await self._http_client.request(
                    method=method,
                    url=url,
                    json=json_data,
                    params=query_params,
                    headers=headers
                )
                
                elapsed = time.time() - start_time
                
                # Check for rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 5))
                    logger.warning(
                        "APIM rate limit exceeded",
                        retry_after=retry_after,
                        attempt=attempt + 1
                    )
                    
                    if attempt < retry_count - 1:
                        await asyncio.sleep(retry_after)
                        continue
                
                # Raise for 4xx/5xx errors
                response.raise_for_status()
                
                # Parse response
                result = response.json()
                
                # Log response
                log_data = {
                    "status_code": response.status_code,
                    "elapsed_ms": int(elapsed * 1000),
                    "attempt": attempt + 1
                }
                
                # Extract token usage from APIM headers
                if "X-APIM-Token-Usage" in response.headers:
                    log_data["token_usage"] = response.headers["X-APIM-Token-Usage"]
                
                if self.settings.apim_log_response_body:
                    log_data["response_body"] = result
                
                logger.info("APIM request successful", **log_data)
                
                return result
            
            except httpx.HTTPStatusError as e:
                last_error = e
                logger.error(
                    "APIM HTTP error",
                    status_code=e.response.status_code,
                    error=str(e),
                    attempt=attempt + 1
                )
                
                # Don't retry on 4xx errors (except 429)
                if 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                    raise
                
                # Exponential backoff for retries
                if attempt < retry_count - 1:
                    backoff = 2 ** attempt
                    await asyncio.sleep(backoff)
            
            except Exception as e:
                last_error = e
                logger.error(
                    "APIM request error",
                    error=str(e),
                    error_type=type(e).__name__,
                    attempt=attempt + 1
                )
                
                if attempt < retry_count - 1:
                    backoff = 2 ** attempt
                    await asyncio.sleep(backoff)
        
        # All retries exhausted
        logger.error("APIM request failed after all retries", error=str(last_error))
        raise last_error
    
    async def chat_completion(
        self,
        deployment_id: str,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        stop: Optional[Union[str, List[str]]] = None,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create chat completion through APIM.
        
        Args:
            deployment_id: Model deployment name
            messages: List of message objects
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter
            frequency_penalty: Frequency penalty
            presence_penalty: Presence penalty
            stop: Stop sequences
            stream: Whether to stream response
            **kwargs: Additional parameters
            
        Returns:
            Chat completion response
        """
        # Path must include /openai/ for APIM policy routing to OpenAI backend pool
        path = f"openai/deployments/{deployment_id}/chat/completions"
        
        # Build request body
        request_body = {
            "messages": messages
        }
        
        if temperature is not None:
            request_body["temperature"] = temperature
        if max_tokens is not None:
            request_body["max_tokens"] = max_tokens
        if top_p is not None:
            request_body["top_p"] = top_p
        if frequency_penalty is not None:
            request_body["frequency_penalty"] = frequency_penalty
        if presence_penalty is not None:
            request_body["presence_penalty"] = presence_penalty
        if stop is not None:
            request_body["stop"] = stop
        if stream:
            request_body["stream"] = stream
        
        # Add any additional kwargs
        request_body.update(kwargs)
        
        query_params = {
            "api-version": self.settings.azure_openai_api_version or "2024-08-01-preview"
        }
        
        return await self._make_request(
            method="POST",
            path=path,
            json_data=request_body,
            query_params=query_params
        )
    
    async def embeddings(
        self,
        deployment_id: str,
        input_text: Union[str, List[str]],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create embeddings through APIM.
        
        Args:
            deployment_id: Model deployment name
            input_text: Text or list of texts to embed
            **kwargs: Additional parameters
            
        Returns:
            Embeddings response
        """
        path = f"deployments/{deployment_id}/embeddings"
        
        request_body = {
            "input": input_text
        }
        request_body.update(kwargs)
        
        query_params = {
            "api-version": self.settings.azure_openai_api_version or "2024-08-01-preview"
        }
        
        return await self._make_request(
            method="POST",
            path=path,
            json_data=request_body,
            query_params=query_params
        )
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check APIM gateway health.
        
        Returns:
            Health status information
        """
        try:
            # Simple GET request to check connectivity
            path = "health"
            return await self._make_request(
                method="GET",
                path=path,
                retry_count=1
            )
        except Exception as e:
            logger.error("APIM health check failed", error=str(e))
            return {
                "status": "unhealthy",
                "error": str(e)
            }


def create_apim_client(settings: Settings) -> Optional[APIMClient]:
    """
    Factory function to create APIM client if enabled.
    
    Args:
        settings: Application settings
        
    Returns:
        APIMClient instance if enabled, None otherwise
    """
    if not settings.apim_enabled:
        logger.info("APIM disabled, skipping client creation")
        return None
    
    try:
        client = APIMClient(settings)
        logger.info("APIM client created successfully")
        return client
    except Exception as e:
        logger.error("Failed to create APIM client", error=str(e))
        raise
