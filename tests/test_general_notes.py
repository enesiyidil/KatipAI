from core.vault.general_notes import extract_general_note, is_general_note_command


def test_detects_common_commands():
    assert is_general_note_command("bunu genel notlara ekle")
    assert is_general_note_command("genel not olarak yarın deploy var")
    assert is_general_note_command("şunu genel notlara yaz")
    assert not is_general_note_command("sadece bir toplantı notu")
    assert not is_general_note_command("")


def test_extracts_payload():
    assert extract_general_note("genel not olarak yarın deploy var") == "yarın deploy var"
    note = extract_general_note("bunu genel notlara ekle: API timeout artacak")
    assert "API timeout" in note or "timeout" in note.lower()
