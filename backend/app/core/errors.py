from __future__ import annotations


class WdspError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class FetchError(WdspError):
    pass


class ParseError(WdspError):
    pass
