"""
    Dummy conftest.py for template_agent.

    If you don't know what this is for, just leave it empty.
    Read more about conftest.py under:
    - https://docs.pytest.org/en/stable/fixture.html
    - https://docs.pytest.org/en/stable/writing_plugins.html
"""

import pytest
from ostorlab.agent.testing.mock_agent import agent_mock

@pytest.fixture
def agent_mock(agent_mock):
    yield agent_mock
