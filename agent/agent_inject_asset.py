"""Inject asset agent."""

import glob
import logging
import pathlib
import urllib.parse

from ostorlab.agent import agent
from ostorlab.agent.message import message as agent_message
from rich import logging as rich_logging

from agent.providers import base
from agent.providers import git
from agent.providers import errors as provider_errors
from agent.providers import registry
from agent.providers import token

ASSET_DIR = "/asset/"
RAW_PATTERN = "asset.binproto_"
SELECTOR_PATTERN = "/asset/selector.txt_"
REPOSITORY_SELECTOR = "v3.asset.repository"
SHARED_VOLUME_DIR = "/code"

# Before Ostorlab version 0.3.1 (including).
ASSET_RAW_PATH = "/tmp/asset.binproto"
ASSET_SELECTOR_PATH = "/tmp/asset_selector.txt"

logging.basicConfig(
    format="%(message)s",
    datefmt="[%X]",
    level="INFO",
    handlers=[rich_logging.RichHandler(rich_tracebacks=True)],
    force=True,
)
logger = logging.getLogger(__name__)


class AgentInjectAsset(agent.Agent):
    """Agent Inject Asset."""

    def start(self) -> None:
        if pathlib.Path(ASSET_RAW_PATH).exists():
            self._legacy_emit_assets()
        else:
            self._emit_assets()

    def _legacy_emit_assets(self) -> None:
        """Asset injection as done by Ostorlab version 0.3.1 and before."""
        try:
            with (
                open(ASSET_RAW_PATH, "rb") as asset_raw_o,
                open(ASSET_SELECTOR_PATH, "r", encoding="utf-8") as asset_selector_o,
            ):
                asset = asset_raw_o.read()
                selector = asset_selector_o.read()
                self._emit_asset(selector=selector, asset=asset)
        except FileNotFoundError as e:
            logger.error("expected asset files are not found: %s", e)
            raise

    def _emit_assets(self) -> None:
        """Asset injection as done in all new versions."""
        try:
            for raw_asset_path in glob.glob(f"{ASSET_DIR}{RAW_PATTERN}*"):
                asset_id = raw_asset_path.split("_", 1)[1]
                asset_selector_path = f"{SELECTOR_PATTERN}{asset_id}"
                with (
                    open(raw_asset_path, "rb") as asset_raw_o,
                    open(
                        asset_selector_path, "r", encoding="utf-8"
                    ) as asset_selector_o,
                ):
                    asset = asset_raw_o.read()
                    selector = asset_selector_o.read()
                    self._emit_asset(selector=selector, asset=asset)
        except FileNotFoundError as e:
            logger.error("expected asset files are not found: %s", e)
            raise

    def _emit_asset(self, selector: str, asset: bytes) -> None:
        """Emit a single asset, checking out repository assets beforehand."""
        selector = selector.strip()
        if selector == REPOSITORY_SELECTOR:
            try:
                self._checkout_repository(asset)
            except provider_errors.CloneError as e:
                logger.error("skipping repository asset: %s", e)
                return

        logger.info("injecting asset of size %d to selector %s", len(asset), selector)
        self.emit_raw(selector=selector, raw=asset)

    def _authenticate_if_needed(
        self, ref: base.RepositoryCheckoutRequest, cloner: base.RepositoryCloner
    ) -> None:
        """Injects authentication token into ref if the repository is private."""
        if git.is_public_repository(ref.repository_url) is False:
            # Attempt to fetch a platform token if not embedded and API keys are available
            if (
                cloner.PROVIDER_NAME is not None
                and urllib.parse.urlparse(ref.repository_url).username is None
            ):
                api_url = self.args.get("api_reporting_engine_base_url")
                api_key = self.args.get("reporting_engine_api_key")

                if api_url is not None and api_key is not None:
                    fetched_token = token.fetch_platform_token(
                        api_url, api_key, cloner.PROVIDER_NAME
                    )
                    if fetched_token is not None:
                        ref.token = fetched_token

            if (
                ref.token is None
                and urllib.parse.urlparse(ref.repository_url).username is None
            ):
                raise provider_errors.MissingCredentialsError(
                    f"Credentials are required for private repository {git.redact_url(ref.repository_url)}"
                )

    def _checkout_repository(self, asset: bytes) -> None:
        """Clone the repository asset onto the shared scan volume.

        Raises `CloneError` (or a subclass) when the repository cannot be
        checked out.
        """
        repository_message = agent_message.Message.from_raw(REPOSITORY_SELECTOR, asset)

        # Enums are usually parsed as strings or integers.
        provider = repository_message.data.get("provider")

        ref = base.RepositoryCheckoutRequest(
            repository_url=repository_message.data.get("repository_url", ""),
            commit_hash=repository_message.data.get("commit_hash", ""),
            provider=provider,
        )
        if ref.repository_url == "" or ref.commit_hash == "":
            raise provider_errors.CloneError(
                "repository asset is missing repository_url or commit_hash"
            )

        cloner = registry.cloner_for_url(ref.repository_url, ref.provider)

        # If the repository is public (or URL already contains working credentials), we do not need to fetch a token.
        self._authenticate_if_needed(ref, cloner)

        cloner.clone(ref, SHARED_VOLUME_DIR)
        logger.info(
            "checked out %s into %s",
            git.redact_url(ref.repository_url),
            SHARED_VOLUME_DIR,
        )


if __name__ == "__main__":
    logger.info("starting agent ...")
    AgentInjectAsset.main()
