"""argss — Stupidly Simple CLI builder (sync-only, no groups)"""

from __future__ import annotations

import argparse
import inspect
import sys
from typing import Any, Callable, Dict, List

from .utils import get_type_from_annotation, is_bool_type


class Argss:
    """
    Wrapper over argparse for building command-line interfaces with decorator-based command registration.

    Features:
        - Decorator-based command registration via @app.command()
        - Automatic argument inference from function signatures
        - Support for boolean flags with --flag/--no-flag patterns
        - Global arguments shared across all commands
        - Custom argument definitions via arguments parameter

    Args:
        name: Application name (defaults to sys.argv[0] if None).
        description: Application description shown in help.
        version: Version string, adds --version flag if provided.

    Example:
        app = Argss(name="myapp", description="My CLI app", version="1.0.0")

        @app.command()
        def say(text: str, bold: bool = False):
            '''Print text with optional bold formatting.'''
            return f"\\033[1m{text}\\033[0m" if bold else text

        app.run()
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
        self._parsers_setup = False

        self.parser = argparse.ArgumentParser(prog=name, description=description)

        self.subparsers = self.parser.add_subparsers(dest="command", title="Commands")

        if version:
            self.parser.add_argument("--version", action="version", version=version)

    def add_global_argument(self, *flags: str, **kwargs: Any) -> None:
        """
        Add a global argument that applies to all commands.

        Args:
            *flags: Flag strings (e.g., "--verbose", "-v").
            **kwargs: Any argparse argument options.
        """
        self.parser.add_argument(*flags, **kwargs)

    def command(
        self,
        name: str | None = None,
        description: str | None = None,
        arguments: List[List] | None = None,
        **parser_kwargs: Any,
    ) -> Callable:
        """
        Decorator that registers a function as a CLI command.

        Automatically infers CLI arguments from the function signature. Parameters
        without defaults become required positional arguments, parameters with
        defaults become optional flags, and bool parameters get --flag/--no-flag
        boolean switches.

        Args:
            name: Command name (defaults to function name with underscores replaced by hyphens).
            description: Command description (defaults to function docstring).
            arguments: List of argument definitions in [flags..., {kwargs}] format.
                      Each item is a list where the last element is a dict of argparse options.
            **parser_kwargs: Additional arguments passed to argparse.ArgumentParser.add_parser().

        Returns:
            Decorator function that registers the command.

        Example:
            @app.command("greet", description="Say hello")
            def greet(name: str, times: int = 1):
                '''Greet someone multiple times.'''
                for _ in range(times):
                    print(f"Hello, {name}!")

        Example with arguments:
            @app.command(arguments=[
                ["-n", "--name", {"type": str, "help": "Your name"}],
                ["-v", "--verbose", {"action": "store_true", "help": "Verbose output"}]
            ])
            def greet(name: str, verbose: bool = False):
                ...
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

            self._commands[cmd_name] = {
                "func": func,
                "parser": parser,
                "arguments": arguments,
            }
            return func

        return decorator

    def _setup_parsers(self):
        for cmd_info in self._commands.values():
            func = cmd_info["func"]
            parser = cmd_info["parser"]
            explicit_args = cmd_info["arguments"]

            explicit_dests = set()

            if explicit_args:
                for arg_def in explicit_args:
                    flags = []
                    kwargs = {}
                    for item in arg_def:
                        if isinstance(item, str):
                            flags.append(item)
                        elif isinstance(item, dict):
                            kwargs.update(item)

                    if not flags:
                        continue

                    param_name = None
                    for flag in flags:
                        if flag.startswith("--"):
                            param_name = flag.lstrip("-").replace("-", "_")
                            break

                    if not param_name:
                        param_name = flags[-1].lstrip("-").replace("-", "_")

                    param = inspect.signature(func).parameters.get(param_name)
                    arg_kwargs = {}

                    if "default" in kwargs:
                        arg_kwargs["default"] = kwargs["default"]
                    elif param and param.default is not inspect.Parameter.empty:
                        arg_kwargs["default"] = param.default

                    if "required" in kwargs:
                        arg_kwargs["required"] = kwargs["required"]
                    elif (
                        param
                        and param.default is inspect.Parameter.empty
                        and not is_bool_type(param)
                    ):
                        arg_kwargs["required"] = True

                    if "help" in kwargs:
                        arg_kwargs["help"] = kwargs["help"]
                    elif param:
                        arg_kwargs["help"] = param_name

                    if "choices" in kwargs:
                        arg_kwargs["choices"] = kwargs["choices"]

                    if "dest" in kwargs:
                        arg_kwargs["dest"] = kwargs["dest"]
                    else:
                        arg_kwargs["dest"] = param_name

                    if "action" in kwargs:
                        if kwargs["action"] in ("store_true", "store_false"):
                            arg_kwargs["action"] = kwargs["action"]
                            if "default" not in arg_kwargs:
                                arg_kwargs["default"] = (
                                    False if kwargs["action"] == "store_true" else True
                                )
                        elif kwargs["action"] == "boolean_optional_action":
                            arg_kwargs["action"] = argparse.BooleanOptionalAction
                        else:
                            arg_kwargs["action"] = kwargs["action"]
                            if "type" in kwargs:
                                arg_kwargs["type"] = kwargs["type"]
                    elif param and is_bool_type(param):
                        arg_kwargs["action"] = argparse.BooleanOptionalAction
                    else:
                        if "type" in kwargs:
                            arg_kwargs["type"] = kwargs["type"]
                        elif param:
                            arg_kwargs["type"] = get_type_from_annotation(
                                param.annotation,
                                param.default
                                if param.default is not inspect.Parameter.empty
                                else None,
                            )

                    parser.add_argument(*flags, **arg_kwargs)
                    explicit_dests.add(arg_kwargs["dest"])

            for param_name, param in inspect.signature(func).parameters.items():
                if param_name in explicit_dests:
                    continue

                has_default = param.default is not inspect.Parameter.empty

                if is_bool_type(param):
                    base_flag = param_name.replace("_", "-")

                    if has_default:
                        default_val = param.default
                        parser.add_argument(
                            f"--{base_flag}",
                            action=argparse.BooleanOptionalAction,
                            default=default_val,
                            dest=param_name,
                            help=f"{param_name} (default: {default_val})",
                        )
                    else:
                        parser.add_argument(
                            f"--{base_flag}",
                            action=argparse.BooleanOptionalAction,
                            required=True,
                            dest=param_name,
                            help=f"{param_name} (required)",
                        )

                elif not has_default:
                    parser.add_argument(
                        param_name,
                        type=get_type_from_annotation(param.annotation, param.default),
                        help=param_name,
                    )
                else:
                    parser.add_argument(
                        f"--{param_name.replace('_', '-')}",
                        type=get_type_from_annotation(param.annotation, param.default),
                        default=param.default,
                        help=f"{param_name} (default: {param.default})",
                    )

    def run(self, args: List[str] | None = None) -> None:
        """
        Parse arguments and execute the matched command.

        Args:
            args: List of command-line arguments (defaults to sys.argv[1:]).
        """
        args = sys.argv[1:] if args is None else args

        if not self._parsers_setup:
            self._setup_parsers()
            self._parsers_setup = True

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
