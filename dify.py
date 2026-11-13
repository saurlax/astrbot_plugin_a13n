import asyncio
import hmac
import json
import sqlite3
import uuid
from weakref import WeakValueDictionary

from aiohttp import ClientError, web

from .a13n_client import A13nClient, AgentError
from .conversations import Conversations


class DifyBridge:
    def __init__(
        self, service: A13nClient, conversations: Conversations, key: str, timeout: int
    ):
        self.service = service
        self.conversations = conversations
        self.key = f"Bearer {key}".encode()
        self.timeout = timeout
        self.locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()
        app = web.Application(client_max_size=512 * 1024)
        app.router.add_post("/v1/chat-messages", self.chat)
        app.router.add_post("/v1/files/upload", self.reject_upload)
        self.runner = web.AppRunner(
            app, access_log=None, handler_cancellation=True, shutdown_timeout=1
        )

    async def start(self, port: int) -> None:
        try:
            await self.service.start()
            await self.runner.setup()
            await web.TCPSite(self.runner, "127.0.0.1", port).start()
        except (Exception, asyncio.CancelledError):
            await self.close()
            raise

    async def close(self) -> None:
        try:
            await self.runner.cleanup()
        finally:
            await self.service.close()

    def authenticate(self, request: web.Request) -> None:
        supplied = request.headers.get("Authorization", "").encode()
        if not hmac.compare_digest(supplied, self.key):
            raise web.HTTPUnauthorized(text="Invalid local bridge key.")

    async def reject_upload(self, request: web.Request) -> web.Response:
        self.authenticate(request)
        raise web.HTTPUnsupportedMediaType(text="The a13n bridge supports text only.")

    async def chat(self, request: web.Request) -> web.StreamResponse:
        self.authenticate(request)
        try:
            body = await request.json()
        except (ValueError, UnicodeError):
            raise web.HTTPBadRequest(text="Expected a JSON chat request.") from None
        if not isinstance(body, dict):
            raise web.HTTPBadRequest(text="Expected a JSON object.")
        user = body.get("user")
        query = body.get("query")
        previous = body.get("conversation_id", "")
        if not isinstance(user, str) or not user.strip() or len(user) > 1024:
            raise web.HTTPBadRequest(text="Expected a non-empty user identifier.")
        if not isinstance(query, str) or not query.strip() or len(query) > 65536:
            raise web.HTTPBadRequest(
                text="Expected non-empty text of up to 65536 characters."
            )
        if not isinstance(previous, str) or len(previous) > 128:
            raise web.HTTPBadRequest(text="Invalid conversation ID.")
        if body.get("response_mode") != "streaming":
            raise web.HTTPBadRequest(text="Use Dify Chat in streaming response mode.")
        if body.get("files"):
            raise web.HTTPUnsupportedMediaType(
                text="The a13n bridge supports text only."
            )

        response = web.StreamResponse(
            headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache"}
        )
        await response.prepare(request)
        conversation_id = previous or str(uuid.uuid4())
        message_id = str(uuid.uuid4())
        ids = {"conversation_id": conversation_id, "message_id": message_id}
        scope = (*self.service.connection, user)
        lock = self.locks.setdefault(user, asyncio.Lock())
        try:
            async with asyncio.timeout(self.timeout), lock:
                thread = (
                    self.conversations.thread(previous, scope) if previous else None
                )
                receipt = await self.service.submit(thread, query, message_id)
                if not previous:
                    self.conversations.save(
                        conversation_id, scope, receipt["thread"]["id"]
                    )
                    await self.send(response, "message", answer="", **ids)
                answer = await self.service.result(receipt)
        except AgentError as error:
            await self.send(response, "error", status=400, message=str(error))
        except TimeoutError:
            await self.send(
                response, "error", status=504, message="Timed out waiting for a13n."
            )
        except (ClientError, KeyError, TypeError, ValueError, sqlite3.Error):
            await self.send(
                response,
                "error",
                status=502,
                message="Could not read the a13n conversation.",
            )
        else:
            await self.send(response, "message", answer=answer, **ids)
            await self.send(response, "message_end", **ids)
        return response

    @staticmethod
    async def send(response: web.StreamResponse, event: str, **fields) -> None:
        data = json.dumps({"event": event, **fields}, ensure_ascii=False)
        await response.write(f"data: {data}\n\n".encode())
