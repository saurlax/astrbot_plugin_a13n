from astrbot.api import AstrBotConfig, logger
from astrbot.api.star import Context, Star, StarTools

from .a13n_client import A13nClient
from .conversations import Conversations
from .dify import DifyBridge


class A13nPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.bridge: DifyBridge | None = None

    async def initialize(self) -> None:
        service_url = self.config["service_url"].strip().rstrip("/")
        api_key = self.config["service_api_key"].strip()
        agent_id = self.config["agent_id"].strip()
        bridge_key = self.config["bridge_key"].strip()
        if not all((service_url, api_key, agent_id, bridge_key)):
            logger.info(
                "Configure a13n for AstrBot, then reload the plugin to start it."
            )
            return
        if len(bridge_key) < 24 or not bridge_key.isascii() or not bridge_key.isalnum():
            raise ValueError(
                "The bridge key must contain at least 24 ASCII letters or digits."
            )
        if bridge_key == api_key:
            raise ValueError("Use a separate key for the local bridge.")
        port = self.config["port"]
        timeout = self.config["timeout_seconds"]
        if not 1 <= port <= 65535 or timeout <= 0:
            raise ValueError("Configure a valid TCP port and a positive timeout.")
        service = A13nClient(service_url, api_key, agent_id)
        store = Conversations(StarTools.get_data_dir("astrbot_plugin_a13n"))
        self.bridge = DifyBridge(service, store, bridge_key, timeout)
        await self.bridge.start(port)
        logger.info(f"a13n for AstrBot is listening on http://127.0.0.1:{port}/v1")

    async def terminate(self) -> None:
        if self.bridge is not None:
            await self.bridge.close()
            self.bridge = None
