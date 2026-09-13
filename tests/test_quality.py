from core.audio.quality import is_hallucination


def test_empty_and_short_are_hallucinations():
    assert is_hallucination("")
    assert is_hallucination("  ")
    assert is_hallucination("ab")


def test_cjk_and_non_latin_are_hallucinations():
    assert is_hallucination("字幕字幕字幕")
    assert is_hallucination("Спасибо за просмотр")


def test_known_whisper_junk():
    assert is_hallucination("abone ol abone ol")
    assert is_hallucination("thanks for watching")
    assert is_hallucination("izlediğiniz için teşekkürler")


def test_repetition_and_runs():
    assert is_hallucination("buses buses buses buses")
    assert is_hallucination("mmmmm")


def test_valid_turkish_sentence_is_kept():
    assert not is_hallucination("Bugün sprint toplantısında deploy tarihini konuştuk.")
