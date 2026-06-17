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
        - Custom argument flags via @cli.argument() decorator
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
        """
        Initialize the CLI application.

        Args:
            name: Program name shown in help output.
            description: Application description shown in help output.
            version: Version string that enables --version flag.
        """
        self.name = name
        self.description = description
        self.version = version
        self._commands: Dict[str, dict] = {}

        self.parser = argparse.ArgumentParser(prog=name, description=description)

        self.subparsers = self.parser.add_subparsers(dest="command", title="Commands")

        if version:
            self.parser.add_argument("--version", action="version", version=version)

    def argument(self, *flags: str, **kwargs: Any) -> Callable:
        """
        Decorator to customize argument flags for a command function parameter.

        Use above @cli.command() to override default flag generation and add
        short flags, custom help text, or other argparse options.

        Args:
            *flags: Command-line flags (e.g., '-s', '--string')
            **kwargs: Additional options passed to argparse (help, type, required, choices, action, etc.)

        Returns:
            Decorator that attaches argument metadata to the function

        Example:
            >>> @cli.argument("-v", "--verbose", help="Enable verbose output")
            >>> @cli.command()
            >>> def process(verbose: bool = False):
            >>>     ...
        """

        def decorator(func):
            if not hasattr(func, "_cli_arguments"):
                setattr(func, "_cli_arguments", [])
            func._cli_arguments.append({"flags": list(flags), **kwargs})
            return func

        return decorator

    def add_global_argument(self, *flags: str, **kwargs: Any) -> None:
        """
        Add a global argument that applies to all commands.

        Args:
            *flags: Command-line flags (e.g., '-v', '--verbose')
            **kwargs: Additional options passed to argparse (help, type, action, etc.)

        Example:
            >>> cli.add_global_argument('-v', '--verbose', action='store_true', help='Enable verbose mode')
        """
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

        The decorated function's parameters are automatically converted to
        CLI arguments. Boolean parameters become --flag/--no-flag pairs.

        Can be combined with @cli.argument() to customize individual parameter flags.

        Args:
            name: Custom command name (defaults to function name with underscores replaced by dashes).
            description: Command description (defaults to function docstring).
            arguments: List of Argument objects for explicit argument definitions.
            **parser_kwargs: Additional arguments passed to argparse's add_parser().

        Returns:
            Decorator function that registers the command.

        Example:
            >>> @cli.command()
            >>> def greet(name: str, uppercase: bool = False):
            >>>     \"\"\"Greet a person.\"\"\"
            >>>     msg = f"Hello, {name}!"
            >>>     return msg.upper() if uppercase else msg

        Example with @cli.argument():
            >>> @cli.argument("-u", "--uppercase", help="Convert to uppercase")
            >>> @cli.command()
            >>> def greet(name: str, uppercase: bool = False):
            >>>     msg = f"Hello, {name}!"
            >>>     return msg.upper() if uppercase else msg
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

            # Collect arguments from both @cli.argument() decorators and the arguments parameter
            all_arguments = list(arguments) if arguments else []

            # Add arguments defined via @cli.argument() decorator
            cli_args = getattr(func, "_cli_arguments", None)
            if cli_args:
                for arg_config in cli_args:
                    flags = arg_config.pop("flags")
                    all_arguments.append(Argument(*flags, **arg_config))

            explicit_dests = set()
            if all_arguments:
                for arg in all_arguments:
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

        Args:
            args: Command-line arguments (defaults to sys.argv[1:]).
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

    def __call__(self, args: List[str] | None = None) -> None:
        """
        Make the CLI instance callable, delegating to run().

        Args:
            args: Command-line arguments (defaults to sys.argv[1:]).

        Example:
            >>> cli = CLI()
            >>> cli()  # Equivalent to cli.run()
        """
        return self.run(args)
