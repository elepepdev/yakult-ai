"""Regression test: emotion tags like [._.] must not be split mid-tag by the sentence divider."""

import asyncio

from yakult_mybini.utils.sentence_divider import SentenceDivider


async def _stream(chunks):
    for c in chunks:
        yield c


async def _collect(text: str) -> list:
    divider = SentenceDivider(faster_first_response=True, segment_method="pysbd")
    chunks = [text[i : i + 3] for i in range(0, len(text), 3)]
    return [s.text for s in divider.process_stream(_stream(chunks)) if hasattr(s, "text")]


def test_emotion_tag_not_split():
    text = "[._.] Ehm gitu aja?Coba pikir-pikir dulu mau ngomong apa, aku tungguin."
    sentences = asyncio.run(_collect(text))
    assert sentences == [
        "[._.] Ehm gitu aja?",
        "Coba pikir-pikir dulu mau ngomong apa, aku tungguin.",
    ]


def test_partial_tag_not_flushed():
    divider = SentenceDivider()
    # The ".", "!" inside [._.] must never be treated as sentence boundaries.
    for chunk in ["[", "._.", "] Ehm gitu aja", "?"]:
        divider._buffer += chunk
        assert not (
            any(p in divider._buffer for p in "?.!。")
            and divider.is_complete_sentence(divider._buffer)
            and "]" not in divider._buffer.split("]")[0]
        ) or "?" in divider._buffer
