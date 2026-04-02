# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Python job-scraper project (Python 3.13+) managed with [uv](https://docs.astral.sh/uv/). Currently in early scaffolding — the core scraping logic lives in `main.py`.

## Commands

```bash
# Install dependencies
uv sync

# Run the project
uv run main.py
# or
uv run python main.py

# Add a dependency
uv add <package>

# Run a script/module directly
uv run python -m <module>
```

## Stack

- **Package manager**: `uv` (see `pyproject.toml` and `uv.lock`)
- **Runtime**: Python 3.13 (pinned in `.python-version`)
- **Dependencies**: `requests` for HTTP
