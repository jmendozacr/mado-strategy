import pytest

from fixtures.synthetic import bearish_purge_setup


@pytest.fixture
def bearish_purge_series():
    return bearish_purge_setup()
