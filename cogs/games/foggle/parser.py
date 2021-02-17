# CC0 - https://github.com/LyricLy

from typing import Callable, Dict, Optional, Tuple


OPS: Dict[str, Callable[[int, int], Optional[int]]] = {
    "+": lambda x, y: x + y,
    "-": lambda x, y: x - y,
    "*": lambda x, y: x * y,
    "/": lambda x, y: x // y if not x % y else None,
}


class View:
    def __init__(self, string: str):
        self.string = string
        self.idx = 0

    def peek(self) -> str:
        try:
            return self.string[self.idx]
        except IndexError:
            return ""

    def strip_ws(self):
        while self.peek().isspace():
            self.idx += 1

    def parse_int(self) -> Optional[int]:
        n = 0
        got_digit = False
        while self.peek().isdigit():
            n = n * 10 + int(self.peek())
            self.idx += 1
            got_digit = True
        self.strip_ws()
        return n if got_digit else None

    def parse_base_expr(self) -> Optional[int]:
        if self.peek() == "(":
            self.idx += 1
            self.strip_ws()
            e = self.parse_expr()
            if e is None or self.peek() != ")":
                return None
            self.idx += 1
            self.strip_ws()
            return e
        else:
            return self.parse_int()

    def parse_prec_lvl(self, ops: Tuple[str, ...], below: Callable[[], Optional[int]]) -> Callable[[], Optional[int]]:
        def parser():
            e = below()
            if e is None:
                return None
            while self.peek() in ops:
                op = OPS[self.peek()]
                self.idx += 1
                self.strip_ws()
                next = below()
                if next is None:
                    return None
                e = op(e, next)
            return e
        return parser

    def parse_expr(self) -> Optional[int]:
        return self.parse_prec_lvl(("+", "-"), self.parse_prec_lvl(("*", "/"), self.parse_base_expr))()

    def parse_full(self) -> Optional[int]:
        self.strip_ws()
        e = self.parse_expr()
        if self.idx < len(self.string):
            return None
        return e