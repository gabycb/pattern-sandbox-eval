"""Azure Web PubSub integration helpers for the autonomous chat feature."""

from __future__ import annotations

import json
import logging
from typing import Dict, Optional

from azure.messaging.webpubsubservice.aio import WebPubSubServiceClient

from ..infra.settings import Settings
from ..models.chat_models import ChatEventPayload

logger = logging.getLogger(__name__)


_GROUP_PREFIX = "task"


class ChatPubSubPublisher:
    """Lightweight wrapper around Azure Web PubSub for chat streaming."""

    def __init__(self, settings: Settings) -> None:
        self._hub = settings.web_pubsub_hub
        connection = settings.web_pubsub_connection_string
        self._client: Optional[WebPubSubServiceClient] = None

        if connection:
            try:
                self._client = WebPubSubServiceClient.from_connection_string(
                    connection,
                    hub=self._hub,
                )
                logger.info("ChatPubSubPublisher initialised", hub=self._hub)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.error("Failed to create Web PubSub client", error=str(exc))
                self._client = None
        else:
            logger.info("ChatPubSubPublisher disabled - no connection string configured")

    @property
    def is_enabled(self) -> bool:
        """Whether Web PubSub streaming is available."""
        return self._client is not None

    async def shutdown(self) -> None:
        """Dispose the underlying client."""
        if self._client is not None:
            await self._client.close()
            self._client = None

    async def get_client_access(
        self,
        *,
        user_id: str,
        task_id: str,
    ) -> Optional[Dict[str, str]]:
        """Generate a client access token and WebSocket URL for the caller."""
        if self._client is None:
            return None

        group_name = self._group_name(task_id)
        try:
            token = await self._client.get_client_access_token(
                user_id=user_id,
                roles=["webpubsub.joinLeaveGroup"],
                groups=[group_name],
            )
            if not token:
                logger.warning("Web PubSub token request returned empty payload", task_id=task_id)
                return None

            return {
                "url": token["url"],
                "group": group_name,
            }
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Failed to issue Web PubSub client token", error=str(exc), task_id=task_id)
            return None

    async def send_event(self, payload: ChatEventPayload) -> None:
        """Publish an event payload to the task group."""
        if self._client is None:
            return

        group_name = self._group_name(payload.task_id)
        message = json.dumps(payload.model_dump(mode="json"))

        try:
            await self._client.send_to_group(
                group_name,
                message,
                content_type="application/json",
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error(
                "Failed to publish Web PubSub event",
                error=str(exc),
                task_id=payload.task_id,
                event_type=payload.type,
            )

    def _group_name(self, task_id: str) -> str:
        return f"{_GROUP_PREFIX}:{task_id}"
