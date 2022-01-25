"""Sample agent implementation"""
import logging

from ostorlab.agent import agent

ASSET_RAW_PATH = '/tmp/asset.binproto'
ASSET_SELECTOR_PATH = '/tmp/asset_selector.txt'

logger = logging.getLogger(__name__)

class AgentInjectAsset(agent.Agent):
    """Agent Inject Asset."""

    def start(self) -> None:
        try:
            with open(ASSET_RAW_PATH, 'rb') as asset_raw_o, open(ASSET_SELECTOR_PATH, 'r',
                                                                 encoding='utf-8') as asset_selector_o:
                asset = asset_raw_o.read()
                selector = asset_selector_o.read()
                logger.info('injecting asset of size %d to selector %s', len(asset), selector)
                self.emit_raw(selector=selector, raw=asset)
        except FileNotFoundError as e:
            logger.error('expected asset files are not found: %s', e)
            raise


if __name__ == '__main__':
    logger.info('starting agent ...')
    AgentInjectAsset.main()
