"""Token generation for Git platforms."""

import logging

import requests
import tenacity

logger = logging.getLogger(__name__)

_GENERATE_GIT_PLATFORM_TOKEN_QUERY = """
    query GenerateGitPlatformToken($gitProvider: String!) {
        generateGitPlatformToken(gitProvider: $gitProvider) {
            token
        }
    }
"""


@tenacity.retry(
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_exponential(multiplier=2, min=1, max=10),
    retry=tenacity.retry_if_exception_type((requests.RequestException, ValueError)),
    before_sleep=lambda retry_state: logger.warning(
        "Retrying platform token fetch, attempt %s", retry_state.attempt_number
    ),
    reraise=True,
)
def _do_fetch_platform_token(
    api_url: str, api_key: str, git_provider: str
) -> str | None:
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }

    payload = {
        "query": _GENERATE_GIT_PLATFORM_TOKEN_QUERY,
        "variables": {"gitProvider": git_provider},
    }

    response = requests.post(api_url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()

    data = response.json()
    if "errors" in data:
        logger.warning(
            "GraphQL errors when fetching token for %s: %s",
            git_provider,
            data["errors"],
        )
        return None

    response_data = data.get("data")
    if response_data is None:
        logger.warning("GraphQL response for %s has null data", git_provider)
        return None

    token_value = response_data.get("generateGitPlatformToken", {}).get("token")
    if token_value == "":
        logger.warning("GraphQL response for %s returned empty token", git_provider)
        return None
    return token_value


def fetch_platform_token(api_url: str, api_key: str, git_provider: str) -> str | None:
    """Fetches a cloning token for a given Git platform using the Reporting Engine API."""
    if api_url is None or api_key is None or api_url == "" or api_key == "":
        return None

    try:
        return _do_fetch_platform_token(api_url, api_key, git_provider)
    except (requests.RequestException, ValueError) as e:
        logger.warning(
            "Failed to fetch platform token for %s after retries: %s", git_provider, e
        )
        return None
