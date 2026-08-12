"""Regression test: emotion tags like [._.] must not be split mid-tag by the sentence divider."""

import asyncio

from yakult_mybini.utils.sentence_divider import SentenceDivider, is_complete_sentence


async def _stream(chunks):
    for c in chunks:
        yield c


async def _collect(text: str) -> list:
    divider = SentenceDivider(faster_first_response=True, segment_method="pysbd")
    chunks = [text[i : i + 3] for i in range(0, len(text), 3)]
    out = []
    async for s in divider.process_stream(_stream(chunks)):
        if hasattr(s, "text"):
            out.append(s.text)
    return out


def test_emotion_tag_not_split():
    text = "[._.] Ehm gitu aja?Coba pikir-pikir dulu mau ngomong apa, aku tungguin."
    sentences = asyncio.run(_collect(text))
    assert sentences == [
        "[._.] Ehm gitu aja?",
        "Coba pikir-pikir dulu mau ngomong apa, aku tungguin.",
    ]


def test_partial_tag_not_flushed():
    divider = SentenceDivider()
    # The "." inside an unclosed [._ must not be treated as a sentence boundary.
    for chunk in ["[", "._", ".", "] Ehm gitu aja", "?"]:
        divider._buffer += chunk
        complete = is_complete_sentence(divider._buffer)
        if "]" not in divider._buffer:
            assert not complete, f"partial tag flushed early: {divider._buffer!r}"
    assert is_complete_sentence(divider._buffer)
