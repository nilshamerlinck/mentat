from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Literal
from uuid import UUID, uuid4

from ipdb import set_trace

from .broadcast import Broadcast

_SESSION_STREAM: ContextVar[SessionStream] = ContextVar("mentat:session_stream")


class StreamMessageSource(Enum):
    SERVER = "server"
    CLIENT = "client"


@dataclass
class StreamMessage:
    id: UUID
    channel: str
    source: StreamMessageSource
    data: Any
    extra: Dict[str, Any] | None
    created_at: datetime


def get_session_stream():
    session_stream = _SESSION_STREAM.get()
    if not isinstance(session_stream, SessionStream):
        raise Exception("SessionStream is not set for the current context")
    return session_stream


class SessionStream:
    """Replaces `cprint` and `print`

    Stores message history for a Session and holds an in-memory message bus.

    Terminal and extension clients can read these messages and render them accordingly.
    For the terminal, they would be rendered with `cprint`.
    """

    def __init__(self):
        self.messages: List[StreamMessage] = []
        self._broadcast = Broadcast()

    async def start(self):
        await self._broadcast.connect()

    async def stop(self):
        await self._broadcast.disconnect()

    def send(
        self,
        data: Any,
        source: StreamMessageSource = StreamMessageSource.SERVER,
        channel: str = "default",
        **kwargs,
    ):
        message = StreamMessage(
            id=uuid4(),
            source=source,
            channel=channel,
            data=data,
            created_at=datetime.utcnow(),
            extra=kwargs,
        )
        self.messages.append(message)
        self._broadcast.publish_nowait(channel=channel, message=message)

        return message

    # TODO: this should aways return a SessionMessage
    async def recv(self, channel: str = "default"):
        """Listen for a single reponse on a channel"""
        async with self._broadcast.subscribe(channel) as subscriber:
            async for event in subscriber:
                return event.message

    async def listen(
        self, channel: str = "default"
    ) -> AsyncGenerator[StreamMessage, None]:
        """Listen to all messages on a channel indefinitely"""
        async with self._broadcast.subscribe(channel) as subscriber:
            async for event in subscriber:
                yield event.message