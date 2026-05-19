"""Git operations shared by the repository providers.

These wrappers run `git` non-interactively: a private repository fails fast
instead of blocking on a credentials prompt.
"""

import logging
import os
import subprocess

from agent.providers import errors

logger = logging.getLogger(__name__)

_LS_REMOTE_TIMEOUT_SECONDS = 60
_CLONE_TIMEOUT_SECONDS = 600


def _non_interactive_env() -> dict[str, str]:
    """Return an environment that makes git fail instead of prompting."""
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = "true"
    return env


def is_public_repository(repository_url: str) -> bool:
    """Return whether `repository_url` is reachable without authentication.

    Probes with `git ls-remote` — a cheap network call that lists refs without
    a checkout.
    """
    try:
        result = subprocess.run(
            ["git", "ls-remote", repository_url, "HEAD"],
            capture_output=True,
            timeout=_LS_REMOTE_TIMEOUT_SECONDS,
            env=_non_interactive_env(),
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as e:
        logger.warning("git ls-remote failed for %s: %s", repository_url, e)
        return False

    return result.returncode == 0


def clone_repository(repository_url: str, commit_hash: str, destination: str) -> None:
    """Clone `repository_url` into `destination` and check out `commit_hash`.

    Raises `CloneError` when the clone or the checkout fails.
    """
    _run_git(
        ["clone", repository_url, destination],
        error=f"failed to clone {repository_url}",
    )
    _run_git(
        ["-C", destination, "checkout", commit_hash],
        error=f"failed to check out {commit_hash}",
    )


def _run_git(args: list[str], error: str) -> None:
    """Run a git command, raising `CloneError` on a non-zero exit."""
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            timeout=_CLONE_TIMEOUT_SECONDS,
            env=_non_interactive_env(),
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as e:
        raise errors.CloneError(f"{error}: {e}") from e

    if result.returncode != 0:
        raise errors.CloneError(
            f"{error}: {result.stderr.decode(errors='replace').strip()}"
        )
