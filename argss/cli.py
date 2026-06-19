"""Lightweight CLI builder with decorator-based command registration."""

from __future__ import annotations

import argparse
import inspect
import sys
from typing import Any, Callable, Dict, List, Union

from .utils import get_type_from_annotation, is_bool_type


class Argss:
    """
    Wrapper over argparse for building command-line interfaces with decorator-based command registration.

    Features:
        - Decorator-based command registration via @app.command()
        - Custom argument flags via @app.argument() decorator
        - Automatic argument inference from function signatures
        - Support for boolean flags with --flag/--no-flag patterns
        - Global arguments shared across all commands

    Args:
        name: Application name (defaults to sys.argv[0] if None).
        description: Application description shown in help.
        version: Version string, adds --version flag if provided.

    Example:
        app = Argss(name="myapp", description="My CLI app", version="1.0.0")

        @app.argument("-b", "--bold", action="store_true", help="Make text bold")
        @app.command()
        def say(text: str, bold: bool = False):
            '''Print text with optional bold formatting.'''
            return f"\\033[1m{text}\\033[0m" if bold else text

        app()
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

    def argument(
        self, *args: Union[str, List[Union[str, Dict[str, Any]]]], **kwargs: Any
    ) -> Callable:
        """
        Decorator that adds custom argument definitions to a command function.

        Can be stacked with @app.command() to define CLI arguments with custom flags,
        types, help text, and other argparse options. Arguments defined here take
        precedence over auto-inferred ones.

        Args:
            *args: Flag strings (e.g., "-b", "--bold") or a list of [flag, dict] pairs.
            **kwargs: Any argparse argument options (action, type, help, default, etc.).

        Returns:
            Decorator function that attaches argument metadata to the command.

        Example:
            @app.argument("-n", "--name", type=str, help="Your name")
            @app.argument("-v", "--verbose", action="store_true")
            @app.command()
            def greet(name: str, verbose: bool = False):
                ...
        """

        def decorator(func):
            cli_args = getattr(func, "_cli_arguments", None)
            if cli_args is None:
                setattr(func, "_cli_arguments", [])

            if not args and not kwargs:
                return func

            if len(args) == 1 and isinstance(args[0], list) and args[0]:
                for arg_def in args[0]:
                    if isinstance(arg_def, list):
                        self._parse_argument_definition(arg_def, func)
                    elif isinstance(arg_def, dict):
                        pass
            else:
                flags = [a for a in args if isinstance(a, str)]
                extra_kwargs = {}
                for a in args:
                    if isinstance(a, dict):
                        extra_kwargs.update(a)
                extra_kwargs.update(kwargs)

                if flags:
                    getattr(func, "_cli_arguments").append(
                        {"flags": flags, **extra_kwargs}
                    )

            return func

        return decorator

    def _parse_argument_definition(self, arg_def: List, func: Callable) -> None:
        flags = []
        kwargs = {}

        for item in arg_def:
            if isinstance(item, str):
                flags.append(item)
            elif isinstance(item, dict):
                kwargs.update(item)

        if flags:
            cli_args = getattr(func, "_cli_arguments", None)
            if cli_args is None:
                setattr(func, "_cli_arguments", [])
            getattr(func, "_cli_arguments").append({"flags": flags, **kwargs})

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

            if arguments:
                for arg_def in arguments:
                    flags = []
                    kwargs = {}
                    for item in arg_def:
                        if isinstance(item, str):
                            flags.append(item)
                        elif isinstance(item, dict):
                            kwargs.update(item)
                    if flags:
                        cli_args = getattr(func, "_cli_arguments", None)
                        if cli_args is None:
                            setattr(func, "_cli_arguments", [])
                        getattr(func, "_cli_arguments").append(
                            {"flags": flags, **kwargs}
                        )

            self._commands[cmd_name] = {
                "func": func,
                "parser": parser,
            }
            return func

        return decorator

    def _setup_parsers(self):
        for cmd_info in self._commands.values():
            func = cmd_info["func"]
            parser = cmd_info["parser"]

            cli_args = getattr(func, "_cli_arguments", None)
            explicit_dests = set()

            if cli_args:
                for arg_config in cli_args:
                    flags = arg_config["flags"]
                    kwargs = {k: v for k, v in arg_config.items() if k != "flags"}

                    param_name = None
                    for flag in flags:
                        if flag.startswith("--"):
                            param_name = flag.lstrip("-").replace("-", "_")
                            break
                        elif not flag.startswith("-"):
                            param_name = flag
                            break

                    if not param_name:
                        param_name = flags[-1].lstrip("-").replace("-", "_")

                    param = inspect.signature(func).parameters.get(param_name)

                    arg_kwargs = {}

                    is_bool_action = False
                    if "action" in kwargs:
                        action = kwargs["action"]
                        if action in ("store_true", "store_false"):
                            arg_kwargs["action"] = action
                            is_bool_action = True
                            if "default" not in kwargs:
                                arg_kwargs["default"] = (
                                    False if action == "store_true" else True
                                )
                        elif action == "version":
                            arg_kwargs["action"] = "version"
                        elif action == "boolean_optional_action":
                            arg_kwargs["action"] = argparse.BooleanOptionalAction
                        else:
                            arg_kwargs["action"] = action
                    elif param and is_bool_type(param):
                        arg_kwargs["action"] = argparse.BooleanOptionalAction

                    if not is_bool_action and "action" not in kwargs:
                        if "type" in kwargs:
                            arg_kwargs["type"] = kwargs["type"]
                        elif param:
                            arg_kwargs["type"] = get_type_from_annotation(
                                param.annotation,
                                param.default
                                if param.default is not inspect.Parameter.empty
                                else None,
                            )

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
                        and not is_bool_action
                    ):
                        arg_kwargs["required"] = True

                    if "help" in kwargs:
                        arg_kwargs["help"] = kwargs["help"]

                    if "choices" in kwargs:
                        arg_kwargs["choices"] = kwargs["choices"]

                    if "dest" in kwargs:
                        arg_kwargs["dest"] = kwargs["dest"]
                    else:
                        arg_kwargs["dest"] = param_name

                    parser.add_argument(*flags, **arg_kwargs)
                    explicit_dests.add(arg_kwargs.get("dest", param_name))

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

    def __call__(self, args: List[str] | None = None) -> None:
        """
        Shortcut for calling run().

        Args:
            args: List of command-line arguments (defaults to sys.argv[1:]).
        """
        return self.run(args)
