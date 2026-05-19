"""Unittests for inject asset agent."""

from pathlib import Path

import pytest
import pyfakefs.fake_filesystem
from ostorlab.agent import definitions as agent_definitions
from ostorlab.agent.message import message
from ostorlab.agent.message import serializer
from ostorlab.runtimes import definitions as runtime_definitions

import agent
from providers import git

_REAL_MESSAGE_CODE_PATH = Path(serializer.__file__).resolve().parent / "proto"
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

    test_agent = agent.AgentInjectAsset(definition, settings)
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

    test_agent = agent.AgentInjectAsset(definition, settings)
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

    fs.create_file(file_path=agent.ASSET_RAW_PATH, contents=APK_MESSAGE_RAW)
    fs.create_file(
        file_path=agent.ASSET_SELECTOR_PATH, contents="v3.asset.file.android.apk"
    )

    definition = agent_definitions.AgentDefinition(
        name="start_test_agent", out_selectors=["v3.asset.file.android.apk"]
    )
    settings = runtime_definitions.AgentSettings(
        key="agent/ostorlab/agent_inject_asset"
    )

    test_agent = agent.AgentInjectAsset(definition, settings)
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
    fs.create_file(file_path="/asset/asset.binproto_1", contents=REPOSITORY_MESSAGE_RAW)
    fs.create_file(file_path="/asset/selector.txt_1", contents="v3.asset.repository")
    definition = agent_definitions.AgentDefinition(
        name="start_test_agent", out_selectors=["v3.asset.repository"]
    )
    settings = runtime_definitions.AgentSettings(
        key="agent/ostorlab/agent_inject_asset"
    )
    test_agent = agent.AgentInjectAsset(definition, settings)

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
    fs.create_file(file_path="/asset/asset.binproto_1", contents=REPOSITORY_MESSAGE_RAW)
    fs.create_file(file_path="/asset/selector.txt_1", contents="v3.asset.repository")
    definition = agent_definitions.AgentDefinition(
        name="start_test_agent", out_selectors=["v3.asset.repository"]
    )
    settings = runtime_definitions.AgentSettings(
        key="agent/ostorlab/agent_inject_asset"
    )
    test_agent = agent.AgentInjectAsset(definition, settings)

    test_agent.start()

    assert len(agent_mock) == 1
    assert agent_mock[0].selector == "v3.asset.repository"
    assert agent_mock[0].raw == REPOSITORY_MESSAGE_RAW
    assert clone_calls == [("https://github.com/owner/repo", "abc123", "/code")]
