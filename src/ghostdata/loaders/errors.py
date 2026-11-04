"""Friendly, catchable loader errors (tasks A2 and A14).

Loaders never leak a raw traceback to the user. They raise :class:`LoaderError`
with a plain-language message that says what failed, where, and what to do next.
The batch runner catches ``LoaderError``, records it as a warning on the case,
and keeps going - one bad file never aborts the run.
"""

from __future__ import annotations


class LoaderError(Exception):
    """A data file could not be read. Message is safe to show a user."""

    def __init__(self, message: str, *, path: str | None = None, hint: str | None = None) -> None:
        self.path = path
        self.hint = hint
        parts = [message.rstrip(".")]
        if path:
            parts.append(f"File: {path}")
        if hint:
            parts.append(f"What to do: {hint}")
        super().__init__(". ".join(parts) + ".")
