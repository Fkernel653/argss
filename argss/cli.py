"""Lightweight CLI builder with decorator-based command registration."""

from __future__ import annotations

import argparse
import inspect
import sys
from typing import Any, Callable, Dict, List

from .argument import Argument
from .utils import get_type_from_annotation, is_bool_type


class CLI:
    """
    Wrapper over argparse for building command-line interfaces with decorator-based command registration.

    Features:
        - Decorator-based command registration via @cli.command()
        - Automatic argument inference from function signatures
        - Support for boolean flags with --flag/--no-flag patterns
        - Global arguments shared across all commands
    """

    def __init__(
        self,
        name: str | None = None,
        description: str | None = None,
        version: str | None = None,
    ):
        self.name = name
        self.description = description
        self.version = version
        self._commands: Dict[str, dict] = {}

        self.parser = argparse.ArgumentParser(prog=name, description=description)

        self.subparsers = self.parser.add_subparsers(dest="command", title="Commands")

        if version:
            self.parser.add_argument("--version", action="version", version=version)

    def add_global_argument(self, *flags: str, **kwargs: Any) -> None:
        """Add a global argument that applies to all commands."""
        self.parser.add_argument(*flags, **kwargs)

    def command(
        self,
        name: str | None = None,
        description: str | None = None,
        arguments: List[Argument] | None = None,
        **parser_kwargs: Any,
    ) -> Callable:
        """
        Decorator for creating a CLI command from a function.
        """

        def decorator(func: Callable) -> Callable:
            cmd_name = name or func.__name__.replace("_", "-")
            cmd_description = description or (func.__doc__ or "").strip()

            parser = self.subparsers.add_parser(
                cmd_name,
                help=cmd_description.split("\n")[0] if cmd_description else None,
                description=cmd_description,
                **parser_kwargs,
            )

            explicit_dests = set()
            if arguments:
                for arg in arguments:
                    kw = {
                        k: v
                        for k, v in vars(arg).items()
                        if k != "flags" and v is not None
                    }
                    explicit_dests.add(parser.add_argument(*arg.flags, **kw).dest)

            for param_name, param in inspect.signature(func).parameters.items():
                if param_name in explicit_dests:
                    continue
                has_default = param.default is not inspect.Parameter.empty

                if not has_default:
                    parser.add_argument(
                        param_name,
                        type=get_type_from_annotation(param.annotation, param.default),
                        help=param_name,
                    )
                elif is_bool_type(param):
                    base_flag = param_name.replace("_", "-")
                    default_val = (
                        param.default
                        if param.default is not inspect.Parameter.empty
                        else False
                    )
                    group = parser.add_mutually_exclusive_group()
                    group.add_argument(
                        f"--{base_flag}",
                        action="store_true",
                        default=default_val,
                        dest=param_name,
                        help=f"Enable {param_name}",
                    )
                    group.add_argument(
                        f"--no-{base_flag}",
                        action="store_false",
                        default=default_val,
                        dest=param_name,
                        help=f"Disable {param_name}",
                    )
                else:
                    parser.add_argument(
                        f"--{param_name.replace('_', '-')}",
                        type=get_type_from_annotation(param.annotation, param.default),
                        default=param.default,
                        help=f"{param_name} (default: {param.default})",
                    )

            self._commands[cmd_name] = {
                "func": func,
                "parser": parser,
            }
            return func

        return decorator

    def run(self, args: List[str] | None = None) -> None:
        """
        Parse command-line arguments and execute the appropriate command.
        """
        args = sys.argv[1:] if args is None else args
        namespace = self.parser.parse_args(args)

        if namespace.command is None:
            self.parser.print_help()
            return

        command_info = self._commands.get(namespace.command)

        if command_info is None:
            self.parser.print_help()
            return

        namespace_dict = vars(namespace)
        func_kwargs = {k: v for k, v in namespace_dict.items() if k != "command"}

        result = command_info["func"](**func_kwargs)

        if result is not None:
            sys.stdout.write(str(result) + "\n")
