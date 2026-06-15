"""Argument descriptor for CLI commands."""

from __future__ import annotations

from typing import Any, List


class Argument:
    """Description of an argument for a command."""

    def __init__(
        self,
        *flags: str,
        type: type = str,
        default: Any = None,
        help: str = "",
        required: bool = False,
        choices: List[Any] | None = None,
        action: str | None = None,
    ):
        """
        Initialize a command argument descriptor.

        Args:
            *flags: Argument flags (e.g., "--output", "-o").
            type: Expected type of the argument value.
            default: Default value if the argument is not provided.
            help: Help text describing the argument.
            required: Whether the argument must be provided.
            choices: List of allowed values for the argument.
            action: Custom argparse action (e.g., "store_true", "store_false").
        """
        self.flags = flags
        self.type = type
        self.default = default
        self.help = help
        self.required = required
        self.choices = choices
        self.action = action
