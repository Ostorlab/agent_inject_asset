"""Sample agent implementation"""
import glob
import logging
import pathlib

from ostorlab.agent import agent
from rich import logging as rich_logging

ASSET_DIR = '/asset/'
RAW_PATTERN = 'asset.binproto_'
SELECTOR_PATTERN = '/asset/selector.txt_'

# Before Ostorlab version 0.3.1 (including).
ASSET_RAW_PATH = '/tmp/asset.binproto'
ASSET_SELECTOR_PATH = '/tmp/asset_selector.txt'

logging.basicConfig(
    format='%(message)s',
    datefmt='[%X]',
    level='INFO',
    handlers=[rich_logging.RichHandler(rich_tracebacks=True)],
    force=True
)
logger = logging.getLogger(__name__)


class AgentInjectAsset(agent.Agent):
    """Agent Inject Asset."""

    def start(self) -> None:
        if pathlib.Path(ASSET_RAW_PATH).exists():
            self._legacy_emit_assets()
        else:
            self._emit_assets()

    def _legacy_emit_assets(self):
        """Asset injection as done by Ostorlab version 0.3.1 and before."""
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

    def _emit_assets(self):
        """Asset injection as done in all new versions."""
        try:
            for raw_asset_path in glob.glob(f'{ASSET_DIR}{RAW_PATTERN}*'):
                asset_id = raw_asset_path.split('_', 1)[1]
                asset_selector_path = f'{SELECTOR_PATTERN}{asset_id}'
                with open(raw_asset_path, 'rb') as asset_raw_o, open(
                        asset_selector_path, 'r', encoding='utf-8') as asset_selector_o:
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
