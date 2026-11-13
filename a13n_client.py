import asyncio
from urllib.parse import quote, urlsplit

import aiohttp


class AgentError(Exception):
    """An error safe to return to AstrBot."""


class A13nClient:
    def __init__(self, service_url: str, api_key: str, agent_id: str):
        url = urlsplit(service_url)
        if (
            url.scheme not in {"http", "https"}
            or not url.hostname
            or url.username is not None
            or url.query
            or url.fragment
            or url.path.rstrip("/").endswith("/api/v1")
        ):
            raise ValueError(
                "Enter the a13n Service URL without /api/v1 or credentials."
            )
        self.base_url = f"{service_url}/api/v1"
        self.agent_id = agent_id
        self.connection = (self.base_url, agent_id)
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self.session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        self.session = aiohttp.ClientSession(
            headers=self._headers, timeout=aiohttp.ClientTimeout(total=15)
        )

    async def close(self) -> None:
        if self.session is not None:
            await self.session.close()
            self.session = None

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        assert self.session is not None
        async with self.session.request(
            method, self.base_url + path, allow_redirects=False, **kwargs
        ) as response:
            if response.status in {401, 403}:
                raise AgentError(
                    "a13n denied access. Check the workspace key and permissions."
                )
            if response.status >= 500 or response.status in {408, 429}:
                raise aiohttp.ClientError()
            if response.status not in {200, 201}:
                raise AgentError(f"a13n rejected the request (HTTP {response.status}).")
            data = await response.json()
            if not isinstance(data, dict):
                raise AgentError("a13n returned an unexpected response.")
            return data

    async def submit(self, thread_id: str | None, query: str, key: str) -> dict:
        path = (
            f"/threads/{quote(thread_id, safe='')}/inbox" if thread_id else "/threads"
        )
        body = {
            "agent_id": self.agent_id,
            "delivery": "next_run",
            "payload": {"content": [{"type": "text", "text": query}]},
        }
        headers = {"Idempotency-Key": key}
        try:
            return await self._request("POST", path, json=body, headers=headers)
        except (aiohttp.ClientError, TimeoutError):
            await asyncio.sleep(0.25)
            return await self._request("POST", path, json=body, headers=headers)

    async def result(self, receipt: dict) -> str:
        run = receipt["run"]
        entry = receipt["entry"]
        if run is None:
            thread_id = quote(receipt["thread"]["id"], safe="")
            entry_id = quote(entry["id"], safe="")
            path = f"/threads/{thread_id}/inbox/{entry_id}"
            while not entry["assigned_run_id"]:
                if entry["status"] != "pending":
                    raise AgentError(
                        "The a13n message was closed before a Run started."
                    )
                await asyncio.sleep(0.5)
                entry = await self._request("GET", path)
            run_id = entry["assigned_run_id"]
            run = await self._request("GET", f"/runs/{quote(run_id, safe='')}")
        path = f"/runs/{quote(run['id'], safe='')}"
        while run["status"] in {"accepted", "running"}:
            await asyncio.sleep(0.5)
            run = await self._request("GET", path)

        status = run["status"]
        if status == "waiting":
            raise AgentError(
                "The a13n Agent is waiting for input. Continue it in a13n."
            )
        if status == "failed":
            raise AgentError("The a13n Agent failed. Check the Run in a13n.")
        if status == "cancelled":
            raise AgentError("The a13n Run was cancelled.")
        if (
            status != "completed"
            or not isinstance(run["output"], str)
            or not run["output"]
        ):
            raise AgentError("The a13n Agent did not return a text reply.")
        return run["output"]
