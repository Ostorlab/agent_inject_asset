"""Sample agent implementation"""
import glob
import logging

from ostorlab.agent import agent
from rich import logging as rich_logging

ASSET_DIR = '/asset/'

RAW_PATTERN = 'asset.binproto_'
SELECTOR_PATTERN = '/asset/selector.txt_'

logging.basicConfig(
    format='%(message)s',
    datefmt='[%X]',
    handlers=[rich_logging.RichHandler(rich_tracebacks=True)],
    force=True
)
logger = logging.getLogger(__name__)


class AgentInjectAsset(agent.Agent):
    """Agent Inject Asset."""

    def start(self) -> None:
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
