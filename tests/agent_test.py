"""Unittests for inject asset agent."""

from ostorlab.agent import definitions as agent_definitions
from ostorlab.agent import message
from ostorlab.runtimes import definitions as runtime_definitions

from src import agent


def testInjectAssetAgent_whenExpectFilesArePresent_rawAssetIsInjected(agent_mocker, fs):
    """Ensures file is injected using the provided selector."""
    # The pymockfs overrides the whole filesystem, which causes the message serialization to fail as it is lookgin for
    # proto files. This add a passthrough to the real filesystem.
    fs.add_real_directory('/home/')
    msg = message.Message.from_data(selector='v3.asset.file.android.apk', data={'content': b'FAKE'})
    fs.create_file(file_path=agent.ASSET_RAW_PATH, contents=msg.raw)
    fs.create_file(file_path=agent.ASSET_SELECTOR_PATH, contents='v3.asset.file.android.apk')

    definition = agent_definitions.AgentDefinition(
        name='start_test_agent',
        out_selectors=['v3.asset.file.android.apk'])
    settings = runtime_definitions.AgentSettings(key='agent/ostorlab/agent_inject_asset')

    test_agent = agent.AgentInjectAsset(definition, settings)
    test_agent.run()
    assert len(agent_mocker) == 1
    assert agent_mocker[0].selector == 'v3.asset.file.android.apk'
    assert agent_mocker[0].raw == msg.raw
