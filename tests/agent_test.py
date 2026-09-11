"""Unittests for inject asset agent."""

import pathlib
import unittest.mock

import pyfakefs.fake_filesystem
import pytest
from ostorlab.agent import definitions as agent_definitions
from ostorlab.agent.message import message, serializer
from ostorlab.runtimes import definitions as runtime_definitions

from agent import agent_inject_asset as agent_module
from agent import repository_archive
from agent.providers import errors as provider_errors
from agent.providers import git, token

_REAL_MESSAGE_CODE_PATH = pathlib.Path(serializer.__file__).resolve().parent / "proto"
_FAKE_MESSAGE_CODE_PATH = "/tmp/ostorlab/agent/message/proto"

APK_MESSAGE_RAW = message.Message.from_data(
    selector="v3.asset.file.android.apk", data={"content": b"FAKE"}
).raw
REPOSITORY_MESSAGE_RAW = message.Message.from_data(
    selector="v3.asset.repository",
    data={
        "repository_url": "https://github.com/owner/repo",
        "commit_hash": "abc123",
    },
).raw
ARCHIVE_CONTENT_MESSAGE_RAW = message.Message.from_data(
    selector="v3.asset.file.repository_archive",
    data={"content": b"FAKE_ARCHIVE_BYTES"},
).raw
ARCHIVE_URL_MESSAGE_RAW = message.Message.from_data(
    selector="v3.asset.file.repository_archive",
    data={"content_url": "https://example.com/repo.zip"},
).raw
ARCHIVE_EMPTY_MESSAGE_RAW = message.Message.from_data(
    selector="v3.asset.file.repository_archive",
    data={"path": "/some/local/path.zip"},
).raw


def _add_real_ostorlab_message_protos(
    fs: pyfakefs.fake_filesystem.FakeFilesystem,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Expose the real ostorlab message proto tree to pyfakefs."""
    monkeypatch.setattr(serializer, "MESSAGE_CODE_PATH", _FAKE_MESSAGE_CODE_PATH)
    fs.add_real_directory(
        str(_REAL_MESSAGE_CODE_PATH), target_path=_FAKE_MESSAGE_CODE_PATH
    )


def testInjectAssetAgent_whenExpectFilesArePresent_rawAssetIsInjected(
    agent_mock: list[message.Message],
    fs: pyfakefs.fake_filesystem.FakeFilesystem,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensures file is injected using the provided selector."""
    # The pymockfs overrides the whole filesystem, which causes the message serialization to fail as it is looking for
    # proto files. This adds a passthrough to the real filesystem.
    fs.add_real_directory("/home/")
    fs.add_real_directory("/opt/")
    _add_real_ostorlab_message_protos(fs, monkeypatch)

    fs.create_file(file_path="/asset/asset.binproto_1", contents=APK_MESSAGE_RAW)
    fs.create_file(
        file_path="/asset/selector.txt_1", contents="v3.asset.file.android.apk"
    )

    definition = agent_definitions.AgentDefinition(
        name="start_test_agent", out_selectors=["v3.asset.file.android.apk"]
    )
    settings = runtime_definitions.AgentSettings(
        key="agent/ostorlab/agent_inject_asset"
    )

    test_agent = agent_module.AgentInjectAsset(definition, settings)
    test_agent.start()
    assert len(agent_mock) == 1
    assert agent_mock[0].selector == "v3.asset.file.android.apk"
    assert agent_mock[0].raw == APK_MESSAGE_RAW


def testInjectAssetAgent_withMultipleAsset_rawAssetAreInjected(
    agent_mock: list[message.Message],
    fs: pyfakefs.fake_filesystem.FakeFilesystem,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensures file is injected using the provided selector."""
    # The pymockfs overrides the whole filesystem, which causes the message serialization to fail as it is looking for
    # proto files. This adds a passthrough to the real filesystem.
    fs.add_real_directory("/home/")
    fs.add_real_directory("/opt/")
    _add_real_ostorlab_message_protos(fs, monkeypatch)

    fs.create_file(file_path="/asset/asset.binproto_1", contents=APK_MESSAGE_RAW)
    fs.create_file(
        file_path="/asset/selector.txt_1", contents="v3.asset.file.android.apk"
    )
    fs.create_file(file_path="/asset/asset.binproto_2", contents=APK_MESSAGE_RAW)
    fs.create_file(
        file_path="/asset/selector.txt_2", contents="v3.asset.file.android.apk"
    )

    definition = agent_definitions.AgentDefinition(
        name="start_test_agent", out_selectors=["v3.asset.file.android.apk"]
    )
    settings = runtime_definitions.AgentSettings(
        key="agent/ostorlab/agent_inject_asset"
    )

    test_agent = agent_module.AgentInjectAsset(definition, settings)
    test_agent.start()
    assert len(agent_mock) == 2
    assert agent_mock[0].selector == "v3.asset.file.android.apk"
    assert agent_mock[0].raw == APK_MESSAGE_RAW
    assert agent_mock[1].selector == "v3.asset.file.android.apk"
    assert agent_mock[1].raw == APK_MESSAGE_RAW


def testInjectAssetAgent_whenLegacyAssetInjection_rawAssetIsInjected(
    agent_mock: list[message.Message],
    fs: pyfakefs.fake_filesystem.FakeFilesystem,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensures file is injected using the provided selector."""
    # The pymockfs overrides the whole filesystem, which causes the message serialization to fail as it is lookgin for
    # proto files. This add a passthrough to the real filesystem.
    fs.add_real_directory("/home/")
    fs.add_real_directory("/opt/")
    _add_real_ostorlab_message_protos(fs, monkeypatch)

    fs.create_file(file_path=agent_module.ASSET_RAW_PATH, contents=APK_MESSAGE_RAW)
    fs.create_file(
        file_path=agent_module.ASSET_SELECTOR_PATH,
        contents="v3.asset.file.android.apk",
    )

    definition = agent_definitions.AgentDefinition(
        name="start_test_agent", out_selectors=["v3.asset.file.android.apk"]
    )
    settings = runtime_definitions.AgentSettings(
        key="agent/ostorlab/agent_inject_asset"
    )

    test_agent = agent_module.AgentInjectAsset(definition, settings)
    test_agent.run()
    assert len(agent_mock) == 1
    assert agent_mock[0].selector == "v3.asset.file.android.apk"
    assert agent_mock[0].raw == APK_MESSAGE_RAW


def testInjectAssetAgent_whenRepositoryAssetIsPrivateAndCannotBeCloned_repositoryAssetIsSkipped(
    agent_mock: list[message.Message],
    fs: pyfakefs.fake_filesystem.FakeFilesystem,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensures a private repository asset is not emitted when the checkout fails."""
    fs.add_real_directory("/home/")
    fs.add_real_directory("/opt/")
    _add_real_ostorlab_message_protos(fs, monkeypatch)
    monkeypatch.setattr(git, "is_public_repository", lambda repository_url: False)

    original_from_raw = message.Message.from_raw

    def mock_from_raw(selector, raw):
        if selector == "v3.asset.repository":

            class MockMessage:
                def __init__(self):
                    self.data = {
                        "repository_url": "https://github.com/owner/repo",
                        "commit_hash": "abc123",
                        "provider": "GITHUB",
                    }
                    self.selector = selector
                    self.raw = raw

            return MockMessage()
        return original_from_raw(selector, raw)

    monkeypatch.setattr(message.Message, "from_raw", mock_from_raw)

    fs.create_file(file_path="/asset/asset.binproto_1", contents=REPOSITORY_MESSAGE_RAW)
    fs.create_file(file_path="/asset/selector.txt_1", contents="v3.asset.repository")
    definition = agent_definitions.AgentDefinition(
        name="start_test_agent", out_selectors=["v3.asset.repository"]
    )
    settings = runtime_definitions.AgentSettings(
        key="agent/ostorlab/agent_inject_asset"
    )
    test_agent = agent_module.AgentInjectAsset(definition, settings)

    test_agent.start()

    assert len(agent_mock) == 0


def testInjectAssetAgent_whenRepositoryAssetIsPublic_repositoryAssetIsInjected(
    agent_mock: list[message.Message],
    fs: pyfakefs.fake_filesystem.FakeFilesystem,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensures a public repository asset is cloned and then emitted."""
    fs.add_real_directory("/home/")
    fs.add_real_directory("/opt/")
    _add_real_ostorlab_message_protos(fs, monkeypatch)
    clone_calls: list[tuple[str, str, str]] = []
    monkeypatch.setattr(git, "is_public_repository", lambda repository_url: True)
    monkeypatch.setattr(
        git,
        "clone_repository",
        lambda repository_url, commit_hash, destination: clone_calls.append(
            (repository_url, commit_hash, destination)
        ),
    )

    original_from_raw = message.Message.from_raw

    def mock_from_raw(selector, raw):
        if selector == "v3.asset.repository":

            class MockMessage:
                def __init__(self):
                    self.data = {
                        "repository_url": "https://github.com/owner/repo",
                        "commit_hash": "abc123",
                        "provider": "GITHUB",
                    }
                    self.selector = selector
                    self.raw = raw

            return MockMessage()
        return original_from_raw(selector, raw)

    monkeypatch.setattr(message.Message, "from_raw", mock_from_raw)

    fs.create_file(file_path="/asset/asset.binproto_1", contents=REPOSITORY_MESSAGE_RAW)
    fs.create_file(file_path="/asset/selector.txt_1", contents="v3.asset.repository")
    definition = agent_definitions.AgentDefinition(
        name="start_test_agent", out_selectors=["v3.asset.repository"]
    )
    settings = runtime_definitions.AgentSettings(
        key="agent/ostorlab/agent_inject_asset"
    )
    test_agent = agent_module.AgentInjectAsset(definition, settings)

    test_agent.start()

    assert len(agent_mock) == 1
    assert agent_mock[0].selector == "v3.asset.repository"
    assert agent_mock[0].raw == REPOSITORY_MESSAGE_RAW
    assert clone_calls == [("https://github.com/owner/repo", "abc123", "/code")]


def testInjectAssetAgent_whenRepositoryAssetIsPrivate_fetchesTokenAndClones(
    agent_mock: list[message.Message],
    fs: pyfakefs.fake_filesystem.FakeFilesystem,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensures a private repository asset fetches token and clones."""
    fs.add_real_directory("/home/")
    fs.add_real_directory("/opt/")
    _add_real_ostorlab_message_protos(fs, monkeypatch)
    clone_calls: list[tuple[str, str, str]] = []
    monkeypatch.setattr(git, "is_public_repository", lambda repository_url: False)
    monkeypatch.setattr(
        git,
        "clone_repository",
        lambda repository_url, commit_hash, destination: clone_calls.append(
            (repository_url, commit_hash, destination)
        ),
    )

    # Mock token fetch
    monkeypatch.setattr(
        token, "fetch_platform_token", lambda *args, **kwargs: "ghp_mock_token"
    )

    original_from_raw = message.Message.from_raw

    def mock_from_raw(selector, raw):
        if selector == "v3.asset.repository":

            class MockMessage:
                def __init__(self):
                    self.data = {
                        "repository_url": "https://github.com/owner/repo",
                        "commit_hash": "abc123",
                        "provider": "GITHUB",
                    }
                    self.selector = selector
                    self.raw = raw

            return MockMessage()
        return original_from_raw(selector, raw)

    monkeypatch.setattr(message.Message, "from_raw", mock_from_raw)

    fs.create_file(file_path="/asset/asset.binproto_1", contents=REPOSITORY_MESSAGE_RAW)
    fs.create_file(file_path="/asset/selector.txt_1", contents="v3.asset.repository")
    definition = agent_definitions.AgentDefinition(
        name="start_test_agent", out_selectors=["v3.asset.repository"]
    )
    settings = runtime_definitions.AgentSettings(
        key="agent/ostorlab/agent_inject_asset",
        args=[
            {
                "name": "api_reporting_engine_base_url",
                "value": b"https://api.ostorlab.co",
                "type": "string",
            },
            {
                "name": "reporting_engine_api_key",
                "value": b"mock_key",
                "type": "string",
            },
        ],
    )
    test_agent = agent_module.AgentInjectAsset(definition, settings)

    with unittest.mock.patch(
        "agent.agent_inject_asset.AgentInjectAsset.args",
        new_callable=unittest.mock.PropertyMock,
    ) as mock_args:
        mock_args.return_value = {
            "api_reporting_engine_base_url": "https://api.ostorlab.co",
            "reporting_engine_api_key": "mock_key",
        }
        test_agent.start()

    assert len(agent_mock) == 1
    assert clone_calls == [
        (
            "https://x-access-token:ghp_mock_token@github.com/owner/repo",
            "abc123",
            "/code",
        )
    ]


def testInjectAssetAgent_whenRepositoryAssetIsPrivateWithEmbeddedCreds_skipsTokenFetchAndClones(
    agent_mock: list[message.Message],
    fs: pyfakefs.fake_filesystem.FakeFilesystem,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensures a private repository with embedded credentials skips token fetching."""
    fs.add_real_directory("/home/")
    fs.add_real_directory("/opt/")
    _add_real_ostorlab_message_protos(fs, monkeypatch)
    clone_calls: list[tuple[str, str, str]] = []

    # is_public_repository will return True if the embedded credentials work!
    monkeypatch.setattr(git, "is_public_repository", lambda repository_url: True)
    monkeypatch.setattr(
        git,
        "clone_repository",
        lambda repository_url, commit_hash, destination: clone_calls.append(
            (repository_url, commit_hash, destination)
        ),
    )

    # Mock token fetch to fail the test if it's called
    def fail_if_called(*args, **kwargs):
        raise AssertionError("fetch_platform_token should not be called")

    monkeypatch.setattr(token, "fetch_platform_token", fail_if_called)

    original_from_raw = message.Message.from_raw

    def mock_from_raw(selector, raw):
        if selector == "v3.asset.repository":

            class MockMessage:
                def __init__(self):
                    self.data = {
                        "repository_url": "https://user:pass@github.com/owner/repo",
                        "commit_hash": "abc123",
                        "provider": "GITHUB",
                    }
                    self.selector = selector
                    self.raw = raw

            return MockMessage()
        return original_from_raw(selector, raw)

    monkeypatch.setattr(message.Message, "from_raw", mock_from_raw)

    fs.create_file(file_path="/asset/asset.binproto_1", contents=REPOSITORY_MESSAGE_RAW)
    fs.create_file(file_path="/asset/selector.txt_1", contents="v3.asset.repository")
    definition = agent_definitions.AgentDefinition(
        name="start_test_agent", out_selectors=["v3.asset.repository"]
    )
    settings = runtime_definitions.AgentSettings(
        key="agent/ostorlab/agent_inject_asset",
        args=[
            {
                "name": "api_reporting_engine_base_url",
                "value": b"https://api.ostorlab.co",
                "type": "string",
            },
            {
                "name": "reporting_engine_api_key",
                "value": b"mock_key",
                "type": "string",
            },
        ],
    )
    test_agent = agent_module.AgentInjectAsset(definition, settings)

    with unittest.mock.patch(
        "agent.agent_inject_asset.AgentInjectAsset.args",
        new_callable=unittest.mock.PropertyMock,
    ) as mock_args:
        mock_args.return_value = {
            "api_reporting_engine_base_url": "https://api.ostorlab.co",
            "reporting_engine_api_key": "mock_key",
        }
        test_agent.start()

    assert len(agent_mock) == 1
    assert clone_calls == [
        ("https://user:pass@github.com/owner/repo", "abc123", "/code")
    ]


def testInjectAssetAgent_whenRepositoryArchiveHasContent_archiveIsExtractedAndInjected(
    agent_mock: list[message.Message],
    fs: pyfakefs.fake_filesystem.FakeFilesystem,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensures an embedded repository archive is extracted and then emitted."""
    fs.add_real_directory("/home/")
    fs.add_real_directory("/opt/")
    _add_real_ostorlab_message_protos(fs, monkeypatch)
    extract_calls: list[tuple[bytes, str]] = []
    monkeypatch.setattr(
        repository_archive,
        "extract_content",
        lambda content, destination: extract_calls.append((content, destination)),
    )
    fs.create_file(
        file_path="/asset/asset.binproto_1", contents=ARCHIVE_CONTENT_MESSAGE_RAW
    )
    fs.create_file(
        file_path="/asset/selector.txt_1",
        contents="v3.asset.file.repository_archive",
    )
    definition = agent_definitions.AgentDefinition(
        name="start_test_agent", out_selectors=["v3.asset.file.repository_archive"]
    )
    settings = runtime_definitions.AgentSettings(
        key="agent/ostorlab/agent_inject_asset"
    )
    test_agent = agent_module.AgentInjectAsset(definition, settings)

    test_agent.start()

    assert extract_calls == [(b"FAKE_ARCHIVE_BYTES", agent_module.SHARED_VOLUME_DIR)]
    assert len(agent_mock) == 1
    assert agent_mock[0].selector == "v3.asset.file.repository_archive"
    assert agent_mock[0].raw == ARCHIVE_CONTENT_MESSAGE_RAW


def testInjectAssetAgent_whenRepositoryArchiveHasContentUrl_archiveIsDownloadedAndInjected(
    agent_mock: list[message.Message],
    fs: pyfakefs.fake_filesystem.FakeFilesystem,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensures a remote repository archive is downloaded and then emitted."""
    fs.add_real_directory("/home/")
    fs.add_real_directory("/opt/")
    _add_real_ostorlab_message_protos(fs, monkeypatch)
    download_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        repository_archive,
        "download_archive",
        lambda content_url, destination: download_calls.append(
            (content_url, destination)
        ),
    )
    fs.create_file(
        file_path="/asset/asset.binproto_1", contents=ARCHIVE_URL_MESSAGE_RAW
    )
    fs.create_file(
        file_path="/asset/selector.txt_1",
        contents="v3.asset.file.repository_archive",
    )
    definition = agent_definitions.AgentDefinition(
        name="start_test_agent", out_selectors=["v3.asset.file.repository_archive"]
    )
    settings = runtime_definitions.AgentSettings(
        key="agent/ostorlab/agent_inject_asset"
    )
    test_agent = agent_module.AgentInjectAsset(definition, settings)

    test_agent.start()

    assert download_calls == [
        ("https://example.com/repo.zip", agent_module.SHARED_VOLUME_DIR)
    ]
    assert len(agent_mock) == 1
    assert agent_mock[0].selector == "v3.asset.file.repository_archive"
    assert agent_mock[0].raw == ARCHIVE_URL_MESSAGE_RAW


def testInjectAssetAgent_whenRepositoryArchiveCannotBeExtracted_archiveAssetIsSkipped(
    agent_mock: list[message.Message],
    fs: pyfakefs.fake_filesystem.FakeFilesystem,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensures a repository archive asset is not emitted when extraction fails."""
    fs.add_real_directory("/home/")
    fs.add_real_directory("/opt/")
    _add_real_ostorlab_message_protos(fs, monkeypatch)

    def _raise(content: bytes, destination: str) -> None:
        raise provider_errors.ArchiveDownloadError("corrupted archive")

    monkeypatch.setattr(repository_archive, "extract_content", _raise)
    fs.create_file(
        file_path="/asset/asset.binproto_1", contents=ARCHIVE_CONTENT_MESSAGE_RAW
    )
    fs.create_file(
        file_path="/asset/selector.txt_1",
        contents="v3.asset.file.repository_archive",
    )
    definition = agent_definitions.AgentDefinition(
        name="start_test_agent", out_selectors=["v3.asset.file.repository_archive"]
    )
    settings = runtime_definitions.AgentSettings(
        key="agent/ostorlab/agent_inject_asset"
    )
    test_agent = agent_module.AgentInjectAsset(definition, settings)

    test_agent.start()

    assert len(agent_mock) == 0


def testInjectAssetAgent_whenRepositoryArchiveHasNeitherContentNorUrl_archiveAssetIsSkipped(
    agent_mock: list[message.Message],
    fs: pyfakefs.fake_filesystem.FakeFilesystem,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensures an archive asset carrying no payload is not emitted."""
    fs.add_real_directory("/home/")
    fs.add_real_directory("/opt/")
    _add_real_ostorlab_message_protos(fs, monkeypatch)
    fs.create_file(
        file_path="/asset/asset.binproto_1", contents=ARCHIVE_EMPTY_MESSAGE_RAW
    )
    fs.create_file(
        file_path="/asset/selector.txt_1",
        contents="v3.asset.file.repository_archive",
    )
    definition = agent_definitions.AgentDefinition(
        name="start_test_agent", out_selectors=["v3.asset.file.repository_archive"]
    )
    settings = runtime_definitions.AgentSettings(
        key="agent/ostorlab/agent_inject_asset"
    )
    test_agent = agent_module.AgentInjectAsset(definition, settings)

    test_agent.start()

    assert len(agent_mock) == 0
