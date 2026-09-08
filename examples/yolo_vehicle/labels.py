"""GPU 표시에서 사용하는 고정 차급 레이블."""

DISPLAY_LABELS = {
    "소형": "SMALL",
    "중형": "MEDIUM",
    "대형": "LARGE",
    "미분류": "UNKNOWN",
}

# 단순 5x7 글꼴. GPU에는 초기화 시 한 번만 올린다.
GLYPHS = {
    char: tuple(0b11111 if row in (0, 6) else 0b10001 for row in range(7))
    for char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.%"
}
GLYPHS[" "] = (0, 0, 0, 0, 0, 0, 0)
