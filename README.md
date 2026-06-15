# argss — Stupidly Simple CLI builder (sync-only, no groups)

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![PyPI](https://img.shields.io/pypi/v/argss.svg)](https://pypi.org/project/argss/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-linux%20%7C%20macOS%20%7C%20windows-lightgrey)]()
[![Ruff](https://img.shields.io/badge/code%20style-ruff-261230?logo=ruff&logoColor=white)](https://docs.astral.sh/ruff/)

**argss** is a lightweight fork of [arg-kiss](https://github.com/Fkernel653/arg-kiss) — stripped down to the essentials.

Write type-annotated Python functions, get a CLI with argparse's native `--help` — no magic, no bloat. Flat commands only, synchronous execution.

## 🎯 Why argss?

| Feature | arg-kiss | argss |
|---------|----------|-------|
| `@cli.command()` | ✅ | ✅ |
| Type inference | ✅ | ✅ |
| Boolean flags | ✅ | ✅ |
| Global arguments | ✅ | ✅ |
| Command groups | ✅ | ❌ |
| Async support | ✅ | ❌ |
| `color` parameter (Python 3.14+ coloured help) | ✅ | ❌ |
| Dependencies | none | none |
| Lines of code | ~150 | ~110 |

> **Note:** arg-kiss provides a `color` parameter in `CLI()` that enables/disables coloured `--help` output on Python 3.14+. argss omits this parameter for simplicity.

Use **argss** when you want:
- Minimal code footprint
- No asyncio overhead
- Flat command structure (no sub-subcommands)
- Faster import time (~30% faster than arg-kiss)

## 🚀 Quick Start

```bash
pip install argss
```

```python
from argss import CLI

cli = CLI(name="todo", description="Task manager")

@cli.command()
def add(task: str, priority: int = 1, done: bool = False):
    """Add a task."""
    status = "✓" if done else "○"
    print(f"[{status}] {task} (priority: {priority})")

@cli.command()
def list_all():
    """Show all tasks."""
    print("Nothing yet!")

cli()
```

```bash
$ python todo.py add "Buy milk" --priority 2
[○] Buy milk (priority: 2)

$ python todo.py list-all
Nothing yet!

$ python todo.py --help
usage: todo [-h] {add,list-all} ...

Task manager

positional arguments:
  {add,list-all}
    add           Add a task.
    list-all      Show all tasks.

options:
  -h, --help      show this help message and exit
```

## 📋 Commands & Features

### `@cli.command()` — Define commands from functions

```python
@cli.command()
def fetch(url: str, retries: int = 3):
    """Download from URL with retries"""
    print(f"Fetched {url} (retries: {retries})")
```

### Type → CLI mapping

| Function signature | CLI argument |
|--------------------|---------------|
| `name: str` | Positional `name` |
| `count: int = 1` | `--count 1` |
| `verbose: bool = False` | `--verbose` / `--no-verbose` |
| `mode: str \| None = None` | `--mode MODE` |

### Global arguments (apply to all commands)

```python
cli.add_global_argument("--verbose", "-v", action="store_true", help="Verbose output")
cli.add_global_argument("--config", "-c", type=str, help="Config file path")

@cli.command()
def deploy(environment: str):
    """Deploy to environment."""
    # Global arguments available in parsed namespace
    pass
```

## 🎨 CLI Configuration

```python
cli = CLI(
    name="myapp",                       # Program name (default: None)
    description="Does amazing things",  # Description in help (default: None)
    version="2.0.0",                    # Adds --version flag (default: None)
)
```

| Option | Description |
|--------|-------------|
| `name` | Program name in help (default: `None`) |
| `description` | Description in help (default: `None`) |
| `version` | Adds `--version` flag (default: `None`) |

## 📄 License & Acknowledgments

MIT License — Built with Python standard library:

| Module | Purpose |
|--------|---------|
| `argparse` | CLI parsing engine |
| `inspect` | Signature introspection |

**Forked from:** [arg-kiss](https://github.com/Fkernel653/arg-kiss) by [Fkernel653](https://github.com/Fkernel653)

**argss author:** [Fkernel653](https://github.com/Fkernel653)

**Project:** [GitHub](https://github.com/Fkernel653/argss) • [PyPI](https://pypi.org/project/argss/)
