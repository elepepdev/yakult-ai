from loguru import logger

try:
    import tiktoken
    _HAS_TIKTOKEN = True
except ModuleNotFoundError:
    _HAS_TIKTOKEN = False
    tiktoken = None  # type: ignore


_W = 48


class TokenTracker:
    def __init__(self, encoding_name: str = "cl100k_base"):
        self.encoding = tiktoken.get_encoding(encoding_name) if _HAS_TIKTOKEN else None
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_conversations = 0
        if not _HAS_TIKTOKEN:
            logger.warning("tiktoken not installed; token counts are approximate (chars/4)")

    def count(self, text: str) -> int:
        try:
            if self.encoding:
                return len(self.encoding.encode(text))
        except Exception:
            pass
        return len(text) // 4

    def log_conversation(self, input_text: str, output_text: str, emoji: str = ""):
        in_tokens = self.count(input_text)
        out_tokens = self.count(output_text)
        self.total_input_tokens += in_tokens
        self.total_output_tokens += out_tokens
        self.total_conversations += 1
        logger.info(self._fmt_conv(in_tokens, out_tokens, emoji))

    def _fmt_conv(self, in_tokens: int, out_tokens: int, emoji: str) -> str:
        total = in_tokens + out_tokens
        tag = f" Token {emoji} " if emoji else " Token "
        top = f"  ╭─{tag}{'─' * (_W - 1 - len(tag))}╮"
        mid = (
            f"  │  in:  {in_tokens:>6}   out:  {out_tokens:>6}"
            f"   total:  {total:<6}   │"
        )
        bot = f"  ╰{'─' * _W}╯"
        return f"\n{top}\n{mid}\n{bot}"

    def summary(self) -> str:
        total = self.total_input_tokens + self.total_output_tokens
        avg = (
            total / self.total_conversations
            if self.total_conversations
            else 0
        )
        items = [
            ("Conversations", str(self.total_conversations)),
            ("Input tokens", str(self.total_input_tokens)),
            ("Output tokens", str(self.total_output_tokens)),
            ("Total tokens", str(total)),
            ("Avg tokens/conv", f"{avg:.0f}"),
        ]
        lines = [
            f"  ╔{'═' * _W}╗",
            f"  ║{' ' * 15} Session Summary {' ' * 16}║",
            f"  ╠{'═' * _W}╣",
        ]
        for label, value in items:
            line = f"  ║  {label:<24}{value:>6}{' ' * 16}║"
            lines.append(line)
        lines.append(f"  ╚{'═' * _W}╝")
        return "\n".join(lines)


_tracker: TokenTracker | None = None


def get_tracker() -> TokenTracker:
    global _tracker
    if _tracker is None:
        _tracker = TokenTracker()
    return _tracker
