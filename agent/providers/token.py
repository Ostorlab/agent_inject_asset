"""Token generation for Git platforms."""

import logging
from typing import Optional

import requests
from agent.providers import errors

logger = logging.getLogger(__name__)

_GENERATE_GIT_PLATFORM_TOKEN_QUERY = """
    query GenerateGitPlatformToken($gitProvider: String!) {
        generateGitPlatformToken(gitProvider: $gitProvider) {
            token
        }
    }
"""

def fetch_platform_token(
    api_url: str,
    api_key: str,
    git_provider: str
) -> Optional[str]:
    """Fetches a cloning token for a given Git platform using the Reporting Engine API."""
    if not api_url or not api_key:
        return None
    
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }
    
    payload = {
        "query": _GENERATE_GIT_PLATFORM_TOKEN_QUERY,
        "variables": {
            "gitProvider": git_provider
        }
    }
    
    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        if "errors" in data:
            logger.warning("GraphQL errors when fetching token for %s: %s", git_provider, data["errors"])
            return None
            
        return data.get("data", {}).get("generateGitPlatformToken", {}).get("token")
        
    except requests.RequestException as e:
        logger.warning("Failed to fetch platform token for %s: %s", git_provider, e)
        return None
