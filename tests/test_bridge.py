import importlib
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from aiohttp import ClientSession, web

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
A13nClient = importlib.import_module(f"{ROOT.name}.a13n_client").A13nClient
Conversations = importlib.import_module(f"{ROOT.name}.conversations").Conversations
DifyBridge = importlib.import_module(f"{ROOT.name}.dify").DifyBridge


class BridgeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.directory = Path(directory)
        self.submissions = []
        self.assigned = []
        self.retry = False
        self.output = "第一轮"
        service = web.Application()
        service.router.add_post("/api/v1/threads", self.submit)
        service.router.add_post("/api/v1/threads/{thread}/inbox", self.submit)
        service.router.add_get("/api/v1/threads/{thread}/inbox/{entry}", self.entry)
        service.router.add_get("/api/v1/runs/{run}", self.run_view)
        runner = web.AppRunner(service)
        self.addAsyncCleanup(runner.cleanup)
        await runner.setup()
        await web.TCPSite(runner, "127.0.0.1", 0).start()
        self.service_url = f"http://127.0.0.1:{runner.addresses[0][1]}"
        self.http = await self.enterAsyncContext(ClientSession())
        await self.start_bridge()

    async def start_bridge(self):
        client = A13nClient(self.service_url, "workspace-token", "agent_1")
        bridge = DifyBridge(client, Conversations(self.directory), "local-key", 4)
        self.addAsyncCleanup(bridge.close)
        await bridge.start(0)
        self.url = f"http://127.0.0.1:{bridge.runner.addresses[0][1]}/v1/chat-messages"
        return bridge

    async def submit(self, request):
        body = await request.json()
        self.assertEqual(request.headers["Authorization"], "Bearer workspace-token")
        self.assertEqual(body["delivery"], "next_run")
        self.assertEqual(body["agent_id"], "agent_1")
        self.submissions.append(
            (request.path, request.headers["Idempotency-Key"], body)
        )
        if self.retry:
            self.retry = False
            raise web.HTTPServiceUnavailable()
        run = None if "thread" in request.match_info else await self.run_data()
        return web.json_response(
            {
                "thread": {"id": "thr_1"},
                "entry": {"id": "ent_1", "status": "pending", "assigned_run_id": None},
                "run": run,
            },
            status=201,
        )

    async def entry(self, request):
        self.assigned.append(request.path)
        return web.json_response({"assigned_run_id": "run_1", "status": "assigned"})

    async def run_data(self):
        return {"id": "run_1", "status": "completed", "output": self.output}

    async def run_view(self, request):
        return web.json_response(await self.run_data())

    async def chat(self, user="session-1", conversation="", token="local-key", **extra):
        async with self.http.post(
            self.url,
            headers={"Authorization": f"Bearer {token}"},
            json={
                "user": user,
                "query": "你好",
                "response_mode": "streaming",
                "conversation_id": conversation,
                **extra,
            },
        ) as response:
            text = await response.text()
            if response.status != 200:
                return response.status
            return [
                json.loads(line.removeprefix("data: "))
                for line in text.splitlines()
                if line.startswith("data: ")
            ]

    async def test_first_turn_retries_and_waits_for_its_inbox_entry_after_reload(self):
        self.retry = True
        first = await self.chat()
        conversation = first[0]["conversation_id"]
        self.assertEqual(first[-2]["answer"], "第一轮")
        self.assertEqual(first[-1]["event"], "message_end")
        self.assertEqual(self.submissions[0], self.submissions[1])
        await self.start_bridge()
        self.output = "第二轮"
        followup = await self.chat(conversation=conversation)
        self.assertEqual(followup[0]["answer"], "第二轮")
        self.assertEqual(followup[-1]["conversation_id"], conversation)
        self.assertEqual(self.submissions[-1][0], "/api/v1/threads/thr_1/inbox")
        self.assertEqual(self.assigned, ["/api/v1/threads/thr_1/inbox/ent_1"])

    async def test_rejects_cross_session_use_invalid_key_and_files(self):
        first = await self.chat()
        conversation = first[0]["conversation_id"]
        wrong_session = await self.chat(user="session-2", conversation=conversation)
        self.assertEqual(wrong_session[0]["event"], "error")
        self.assertEqual(await self.chat(token="wrong"), 401)
        self.assertEqual(await self.chat(files=[{"type": "image"}]), 415)
        self.assertEqual(len(self.submissions), 1)

    async def test_records_the_conversation_before_waiting_for_a_text_result(self):
        self.output = {"unexpected": "structured output"}
        events = await self.chat()
        self.assertEqual(events[0]["answer"], "")
        self.assertEqual(events[-1]["event"], "error")
        self.assertEqual(events[-1]["status"], 400)
        self.output = "Text reply"
        followup = await self.chat(conversation=events[0]["conversation_id"])
        self.assertEqual(followup[0]["answer"], "Text reply")
