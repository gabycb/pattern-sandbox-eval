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

        print(f"\n=== ChatPubSubPublisher.__init__ ===")
        print(f"Hub: {self._hub}")
        print(f"Connection exists: {bool(connection)}")
        print(f"Connection length: {len(connection) if connection else 0}")
        
        logger.info(
            f"ChatPubSubPublisher.__init__: hub={self._hub}, connection_exists={bool(connection)}, connection_length={len(connection) if connection else 0}"
        )

        if connection:
            try:
                self._client = WebPubSubServiceClient.from_connection_string(
                    connection,
                    hub=self._hub,
                )
                print(f"✓ ChatPubSubPublisher initialized: hub={self._hub}, client={type(self._client).__name__}")
                logger.info(f"ChatPubSubPublisher initialised successfully: hub={self._hub}, client={type(self._client).__name__}")
            except Exception as exc:  # pragma: no cover - defensive logging
                print(f"✗ Failed to create Web PubSub client: {exc}")
                logger.error(f"Failed to create Web PubSub client: {exc}", exc_info=True)
                self._client = None
        else:
            print("✗ ChatPubSubPublisher disabled - no connection string")
            logger.warning("ChatPubSubPublisher disabled - no connection string configured")

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
        print(f"\n=== send_event called ===")
        print(f"Client is None: {self._client is None}")
        print(f"Event type: {payload.type}")
        print(f"Task ID: {payload.task_id}")
        
        if self._client is None:
            print("✗ send_event: client is None, cannot send")
            logger.warning("ChatPubSubPublisher: send_event called but client is None")
            return

        group_name = self._group_name(payload.task_id)
        message = json.dumps(payload.model_dump(mode="json"))

        print(f"Group name: {group_name}")
        print(f"Message preview: {message[:200]}")

        logger.info(
            "ChatPubSubPublisher: Sending event to Web PubSub",
            group_name=group_name,
            event_type=payload.type,
            task_id=payload.task_id,
            message_preview=message[:200],
        )

        try:
            print(f"→ Calling send_to_group...")
            await self._client.send_to_group(
                group_name,
                message,
                content_type="text/plain",  # Changed from application/json
            )
            print(f"✓ Event sent successfully to {group_name}")
            logger.info(
                "ChatPubSubPublisher: Event sent successfully",
                group_name=group_name,
                event_type=payload.type,
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            print(f"✗ Failed to send event: {exc}")
            logger.error(
                "ChatPubSubPublisher: Failed to publish Web PubSub event",
                error=str(exc),
                task_id=payload.task_id,
                event_type=payload.type,
                group_name=group_name,
            )

    def _group_name(self, task_id: str) -> str:
        return f"{_GROUP_PREFIX}:{task_id}"
