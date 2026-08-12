import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from yakult_mybini.agent.stateless_llm.openai_compatible_llm import _strip_image_parts


def test_strip_image_parts_replaces_image_url_with_text():
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "halo"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,xxx"}},
            ],
        },
        {"role": "assistant", "content": "hai"},
    ]
    out = _strip_image_parts(messages)
    parts = out[0]["content"]
    assert all(p.get("type") != "image_url" for p in parts)
    assert any("does not support images" in p["text"] for p in parts if p.get("type") == "text")


def test_strip_image_parts_keeps_text_and_plain_messages():
    messages = [{"role": "user", "content": "text saja"}]
    out = _strip_image_parts(messages)
    assert out == messages


if __name__ == "__main__":
    test_strip_image_parts_replaces_image_url_with_text()
    test_strip_image_parts_keeps_text_and_plain_messages()
    print("OK")
