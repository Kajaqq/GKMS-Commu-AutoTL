import textwrap
from config import FormattingConfig
from text_utils import clean_text


def wrap_per_line_limits(text: str, line_limits: list[int]) -> list[str]:
    """Word-aware wrap using a separate char limit per line.

    Spaces between words count toward the line length, but no leading space is
    counted on a fresh line. Words longer than their line's limit are placed
    alone on that line. Anything left over after the last limit becomes one
    extra trailing line.
    """
    wrapped: list[str] = []
    words = text.split()

    for limit in line_limits:
        if not words:
            break
        line_words: list[str] = []
        line_len = 0
        for j, word in enumerate(words):
            space = 1 if line_words else 0
            if line_len + space + len(word) <= limit:
                line_words.append(word)
                line_len += space + len(word)
                continue
            # Word doesn't fit: flush what we have (or the word itself if line is empty)
            if line_words:
                wrapped.append(" ".join(line_words))
                words = words[j:]
            else:
                wrapped.append(word)
                words = words[j + 1 :]
            break
        else:
            # Loop completed without break — all remaining words fit on this line
            if line_words:
                wrapped.append(" ".join(line_words))
            words = []

    if words:
        wrapped.append(" ".join(words))
    return wrapped


def resolve_wrap_params(file_name: str, message_type: str):
    """Return (max_chars, max_breaks, use_per_line) based on file and message type."""
    cfg = FormattingConfig
    is_adv_pevent = file_name.startswith(cfg.ADV_PEVENT_PREFIX)
    is_adv_unit = file_name.startswith(cfg.ADV_UNIT_PREFIX)
    has_per_line = all(
        v is not None
        for v in (
            cfg.ADV_PEVENT_CHOICE_LINE1_CHARS,
            cfg.ADV_PEVENT_CHOICE_LINE2_CHARS,
            cfg.ADV_PEVENT_CHOICE_LINE3_CHARS,
        )
    )

    if is_adv_unit:
        return float("inf"), None, False
    if message_type == "choice":
        if is_adv_pevent:
            if has_per_line:
                return float("inf"), cfg.ADV_PEVENT_MAX_CHOICE_BREAKS, True
            return cfg.ADV_PEVENT_MAX_CHARS, cfg.ADV_PEVENT_MAX_CHOICE_BREAKS, False
        return cfg.OTHER_MAX_CHARS, cfg.OTHER_MAX_CHOICE_BREAKS, False
    if message_type in cfg.DIALOGUE_TYPES:
        return (
            cfg.DEFAULT_MAX_CHARS_PER_LINE,
            cfg.DEFAULT_MAX_DIALOGUE_LINE_BREAKS,
            False,
        )
    return cfg.DEFAULT_MAX_CHARS_PER_LINE, None, False


def wrap_text(text, file_name: str, message_type: str) -> str:
    """Clean and wrap translated text for an Excel cell."""
    formatted_text = clean_text(text, message_type)
    if not formatted_text:
        return ""

    max_chars, max_breaks, use_per_line = resolve_wrap_params(file_name, message_type)

    if use_per_line:
        limits = [
            n
            for n in (
                FormattingConfig.ADV_PEVENT_CHOICE_LINE1_CHARS,
                FormattingConfig.ADV_PEVENT_CHOICE_LINE2_CHARS,
                FormattingConfig.ADV_PEVENT_CHOICE_LINE3_CHARS,
            )
            if n is not None
        ]
        wrapped_lines = wrap_per_line_limits(formatted_text, limits)
    else:
        wrapped_lines = textwrap.fill(
            formatted_text,
            width=max_chars,
            break_long_words=False,
            replace_whitespace=False,
        ).splitlines()

    # Truncate to max_breaks + 1 lines if a cap is configured
    if max_breaks is not None and len(wrapped_lines) > max_breaks + 1:
        wrapped_lines = wrapped_lines[: max_breaks + 1]

    # Choices use "\n" so the trailing space renders correctly in Excel cells
    sep = " \n" if message_type == "choice" and len(wrapped_lines) > 1 else "\n"
    return sep.join(wrapped_lines)
