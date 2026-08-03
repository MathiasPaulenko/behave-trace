"""Calculator application for behave-trace example.

A simple calculator class that supports basic arithmetic operations.
Used to demonstrate behave-trace's ability to capture passing and
failing scenarios with attachments.
"""

from __future__ import annotations


class Calculator:
    """A simple calculator with basic arithmetic operations."""

    def __init__(self) -> None:
        self.first: float = 0
        self.second: float = 0
        self.result: float | None = None
        self.error: str | None = None
        self.history: list[str] = []
        self._enter_count: int = 0

    def enter(self, number: float) -> None:
        """Enter a number into the calculator (first then second operand)."""
        if self._enter_count == 0:
            self.first = number
        else:
            self.second = number
        self._enter_count += 1
        self.error = None
        self.history.append(f"Entered: {number}")

    def _operate(self, op: str, func) -> float:  # type: ignore[no-untyped-def]
        result = func(self.first, self.second)
        self.result = result
        self.history.append(f"{self.first} {op} {self.second} = {result}")
        return result

    def add(self) -> float:
        """Add the two entered numbers."""
        return self._operate("+", lambda a, b: a + b)

    def subtract(self) -> float:
        """Subtract the second number from the first."""
        return self._operate("-", lambda a, b: a - b)

    def multiply(self) -> float:
        """Multiply the two entered numbers."""
        return self._operate("*", lambda a, b: a * b)

    def divide(self) -> float | None:
        """Divide the first number by the second.

        Raises:
            ZeroDivisionError: If second operand is zero.
        """
        if self.second == 0:
            self.error = "Cannot divide by zero"
            self.history.append(f"{self.first} / {self.second} = ERROR: {self.error}")
            raise ZeroDivisionError(self.error)
        return self._operate("/", lambda a, b: a / b)

    def render(self) -> str:
        """Render the calculator display as HTML (for DOM snapshots)."""
        display = "Error" if self.error else str(self.result)
        history_html = "<br>".join(self.history) if self.history else "No operations yet"
        return f"""<div class="calculator">
  <div class="display">{display}</div>
  <div class="history">{history_html}</div>
</div>"""

    def screenshot(self) -> bytes:
        """Return a placeholder PNG screenshot (1x1 pixel)."""
        return bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452"
            "000000010000000108060000001f15c4"
            "890000000d49444154789c63f8cf0000"
            "00030200016dcb24dd0000000049454e"
            "44ae426082"
        )
