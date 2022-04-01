"""Unittests for inject asset agent."""

from ostorlab.agent import definitions as agent_definitions
from ostorlab.agent import message
from ostorlab.runtimes import definitions as runtime_definitions

from agent import agent


def testInjectAssetAgent_whenExpectFilesArePresent_rawAssetIsInjected(agent_mock, fs):
    """Ensures file is injected using the provided selector."""
    # The pymockfs overrides the whole filesystem, which causes the message serialization to fail as it is looking for
    # proto files. This adds a passthrough to the real filesystem.
    fs.add_real_directory('/home/')
    fs.add_real_directory('/opt/')

    msg = message.Message.from_data(selector='v3.asset.file.android.apk', data={'content': b'FAKE'})
    fs.create_file(file_path='/asset/asset.binproto_1', contents=msg.raw)
    fs.create_file(file_path='/asset/selector.txt_1', contents='v3.asset.file.android.apk')

    definition = agent_definitions.AgentDefinition(
        name='start_test_agent',
        out_selectors=['v3.asset.file.android.apk'])
    settings = runtime_definitions.AgentSettings(key='agent/ostorlab/agent_inject_asset')

    test_agent = agent.AgentInjectAsset(definition, settings)
    test_agent.start()
    assert len(agent_mock) == 1
    assert agent_mock[0].selector == 'v3.asset.file.android.apk'
    assert agent_mock[0].raw == msg.raw


def testInjectAssetAgent_withMultipleAsset_rawAssetAreInjected(agent_mock, fs):
    """Ensures file is injected using the provided selector."""
    # The pymockfs overrides the whole filesystem, which causes the message serialization to fail as it is looking for
    # proto files. This adds a passthrough to the real filesystem.
    fs.add_real_directory('/home/')
    fs.add_real_directory('/opt/')

    msg = message.Message.from_data(selector='v3.asset.file.android.apk', data={'content': b'FAKE'})
    fs.create_file(file_path='/asset/asset.binproto_1', contents=msg.raw)
    fs.create_file(file_path='/asset/selector.txt_1', contents='v3.asset.file.android.apk')
    fs.create_file(file_path='/asset/asset.binproto_2', contents=msg.raw)
    fs.create_file(file_path='/asset/selector.txt_2', contents='v3.asset.file.android.apk')

    definition = agent_definitions.AgentDefinition(
        name='start_test_agent',
        out_selectors=['v3.asset.file.android.apk'])
    settings = runtime_definitions.AgentSettings(key='agent/ostorlab/agent_inject_asset')

    test_agent = agent.AgentInjectAsset(definition, settings)
    test_agent.start()
    assert len(agent_mock) == 2
    assert agent_mock[0].selector == 'v3.asset.file.android.apk'
    assert agent_mock[0].raw == msg.raw
    assert agent_mock[1].selector == 'v3.asset.file.android.apk'
    assert agent_mock[1].raw == msg.raw
