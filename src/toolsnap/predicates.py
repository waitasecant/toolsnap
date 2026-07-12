class contains:
    def __init__(self, substring: str):
        self.s = substring

    def __call__(self, value: str) -> bool:
        return self.s in value

    def __repr__(self) -> str:
        return f"contains({self.s!r})"


class matches:
    def __init__(self, pattern: str):
        import re
        self.pattern = pattern
        self._re = re.compile(pattern)

    def __call__(self, value: str) -> bool:
        return bool(self._re.search(value))

    def __repr__(self) -> str:
        return f"matches({self.pattern!r})"


class any_of:
    def __init__(self, *values):
        self.values = values

    def __call__(self, value) -> bool:
        return value in self.values

    def __repr__(self) -> str:
        return f"any_of({', '.join(repr(v) for v in self.values)})"


class gt:
    def __init__(self, threshold):
        self.threshold = threshold

    def __call__(self, value) -> bool:
        return value > self.threshold

    def __repr__(self) -> str:
        return f"gt({self.threshold!r})"


class lt:
    def __init__(self, threshold):
        self.threshold = threshold

    def __call__(self, value) -> bool:
        return value < self.threshold

    def __repr__(self) -> str:
        return f"lt({self.threshold!r})"
