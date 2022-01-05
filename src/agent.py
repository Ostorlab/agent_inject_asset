"""Sample agent implementation"""
from ostorlab.agent import agent

ASSET_RAW_PATH = '/tmp/asset.binproto'
ASSET_SELECTOR_PATH = '/tmp/asset_selector.txt'


class AgentInjectAsset(agent.Agent):
    """Agent Inject asset."""

    def start(self) -> None:
        with open(ASSET_RAW_PATH, 'r', encoding='utf-8') as asset_selector_o, open(ASSET_RAW_PATH, 'rb') as asset_raw_o:
            asset = asset_raw_o.read()
            selector = asset_selector_o.read()
            self.emit_raw(selector=selector, raw=asset)




