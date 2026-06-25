from typing import Sequence, Any


def truncate(text: str, width: int) -> str:
    """
    text가 width를 초과하면 ...로 줄입니다.
    """
    text = str(text)

    if width <= 0:
        return ""

    if len(text) <= width:
        return text

    if width <= 3:
        return "." * width

    return text[:width - 3] + "..."


def format_table(
    rows: Sequence[tuple[Any, ...]],
    col_widths: Sequence[int],
    headers: tuple[str, ...] | None = None,
) -> str:
    """
    고정 너비 테이블 문자열을 반환합니다.

    rows: list[tuple]
    col_widths: 각 column의 고정 너비
    headers: 선택적 header
    """
    if not rows and headers is None:
        return ""

    num_cols = len(col_widths)

    def format_row(row: Sequence[Any]) -> str:
        cells = []

        for i in range(num_cols):
            value = row[i] if i < len(row) else ""
            width = col_widths[i]
            cell = truncate(str(value), width).ljust(width)
            cells.append(cell)

        return "| " + " | ".join(cells) + " |"

    separator = "+-" + "-+-".join("-" * width for width in col_widths) + "-+"

    lines = [separator]

    if headers is not None:
        lines.append(format_row(headers))
        lines.append(separator)

    for row in rows:
        lines.append(format_row(row))

    lines.append(separator)

    return "\n".join(lines)