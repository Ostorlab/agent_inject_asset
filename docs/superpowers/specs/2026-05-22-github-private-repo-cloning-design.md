# GitHub Private Repository Cloning — Design Spec

**Date:** 2026-05-22
**Scope:** GitHub only. GitLab and Bitbucket follow the same pattern in future PRs.

---

## Problem

`GitHubCloner.clone()` currently raises `CloneError("GitHub authenticated cloning is not yet implemented")` for any private repository. There is no mechanism to supply a GitHub token to the agent.

---

## Goals

- Allow a GitHub Personal Access Token to be passed to the agent as an arg.
- Use that token to clone private GitHub repositories.
- Leave public-repository cloning untouched (anonymous, no token needed).
- Keep the shared `git.py` helpers credential-free.

---

## Architecture

### 1. `ostorlab.yaml` — new arg

```yaml
args:
  - name: github_token
    type: "string"
    description: "GitHub Personal Access Token for cloning private repositories."
```

No default value. The field is omitted when the user does not supply it.

### 2. Registry — pass credentials to constructor

`registry.cloner_for_url()` gains an optional `credentials` parameter (a plain dict) and forwards it to the provider constructor:

```python
def cloner_for_url(
    repository_url: str,
    credentials: dict | None = None,
) -> base.RepositoryCloner:
    ...
    return provider_class(credentials or {})
```

### 3. Base class — store credentials

`RepositoryCloner` gets a constructor that stores the credentials dict:

```python
class RepositoryCloner(abc.ABC):
    def __init__(self, credentials: dict) -> None:
        self._credentials = credentials
```

### 4. `GitHubCloner` — extract token, validate, clone

```python
class GitHubCloner(base.RepositoryCloner):
    def __init__(self, credentials: dict) -> None:
        super().__init__(credentials)
        self._token: str | None = credentials.get("github_token")

    def ensure_credentials(self) -> None:
        if not self._token:
            raise errors.MissingCredentialsError(
                "github_token agent arg is required to clone private GitHub repositories"
            )

    def clone(self, ref: base.RepositoryCheckoutRequest, destination: str) -> None:
        if git.is_public_repository(ref.repository_url) is True:
            git.clone_repository(ref.repository_url, ref.commit_hash, destination)
            return

        self.ensure_credentials()
        authenticated_url = self._authenticated_url(ref.repository_url)
        git.clone_repository(authenticated_url, ref.commit_hash, destination)

    def _authenticated_url(self, repository_url: str) -> str:
        parsed = urllib.parse.urlparse(repository_url)
        return parsed._replace(
            netloc=f"oauth2:{self._token}@{parsed.hostname}"
        ).geturl()
```

The authenticated URL format (`oauth2:<token>@github.com`) is accepted by GitHub for all PAT types (classic and fine-grained).

### 5. Agent — read arg and pass to registry

```python
cloner = registry.cloner_for_url(
    ref.repository_url,
    credentials={"github_token": self.args.get("github_token")},
)
cloner.clone(ref, SHARED_VOLUME_DIR)
```

---

## Data Flow

```
ostorlab.yaml arg: github_token
       │
       ▼
AgentInjectAsset._checkout_repository()
       │  self.args.get("github_token") → credentials dict
       ▼
registry.cloner_for_url(url, credentials)
       │  matches github.com → GitHubCloner(credentials)
       ▼
GitHubCloner.clone(ref, destination)
       │  is_public? → anonymous clone
       │  is_private?
       │    ensure_credentials() → raises MissingCredentialsError if no token
       │    _authenticated_url()  → https://oauth2:<token>@github.com/...
       ▼
git.clone_repository(authenticated_url, commit_hash, destination)
       │  git clone + git checkout
       ▼
/code  (shared volume)
```

---

## Error Handling

| Situation | Exception raised | Agent behaviour |
|---|---|---|
| Private repo, no token configured | `MissingCredentialsError` (subclass of `CloneError`) | Logs error, skips asset |
| Private repo, bad token | `CloneError` (git exits non-zero) | Logs error, skips asset |
| Unsupported forge host | `UnsupportedProviderError` (subclass of `CloneError`) | Logs error, skips asset |
| Public repo | — | Cloned anonymously, no change |

All three error types are already caught by the `except provider_errors.CloneError` in `agent.py:84`.

---

## Security

- The token is never written to disk or logged.
- It lives only in the transient authenticated URL string passed to `subprocess.run()`.
- The existing `GIT_TERMINAL_PROMPT=0` / `GIT_ASKPASS=true` env vars in `git.py` are unchanged.

---

## Testing

- Unit test: `GitHubCloner` with a valid token clones via authenticated URL (mock `git.clone_repository`).
- Unit test: `GitHubCloner` with no token raises `MissingCredentialsError`.
- Unit test: `GitHubCloner` with a public repo clones anonymously regardless of token presence.
- Unit test: `registry.cloner_for_url` passes credentials to constructor.
- Existing tests must continue to pass unchanged.

---

## Out of scope

- GitLab and Bitbucket authenticated cloning (same pattern, separate PRs).
- GitHub App tokens (supported by the same URL format, no extra work needed).
- Token rotation or refresh.
