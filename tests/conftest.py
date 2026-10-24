import pytest

@pytest.fixture(autouse=True)
def isolated_persistent_state(tmp_path, monkeypatch):
    monkeypatch.setenv('AIRLOCK_STATE_DB', str(tmp_path / 'state.sqlite3'))
