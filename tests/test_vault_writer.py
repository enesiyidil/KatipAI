from core.vault.writer import VaultWriter


def test_creates_obsidian_layout(tmp_path):
    vault = tmp_path / "vault"
    writer = VaultWriter(vault_path=vault)
    assert writer.enabled
    base = vault / "KatipAI"
    assert (base / "transcript").is_dir()
    assert (base / "notes" / "daily").is_dir()
    assert (base / "general").is_dir()
    assert (base / "README.md").is_file()


def test_disabled_without_path(monkeypatch):
    from core.config import settings

    monkeypatch.setattr(settings, "vault_path", None)
    writer = VaultWriter(vault_path=None)
    assert not writer.enabled
