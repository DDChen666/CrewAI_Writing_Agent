# Scrapers Setup Guide

This document explains how to configure the Python environment and run the Reddit, Facebook, Threads, and X scrapers used by `scraepr_test1.py`.

> [!IMPORTANT]
> The X/Twitter workflow is temporarily unavailable in this environment because outbound requests to the supported endpoints are blocked. The CLI still exposes the interface for completeness, but executions will raise a network error until connectivity is restored.

## Prerequisites
- Python 3.13.5 (or any compatible Python 3.10+ interpreter)
- `python3 -m pip` available on your PATH

## Create the virtual environment
1. From the project root (`CrewAI_Writing_Agent`), create the environment:
   ```bash
   python3 -m venv .venv
   ```
2. Activate it:
   - macOS/Linux:
     ```bash
     source .venv/bin/activate
     ```
   - Windows (PowerShell):
     ```powershell
     .venv\Scripts\Activate.ps1
     ```

After activation, your shell prompt should show `(.venv)` to indicate that the environment is active.

## Install dependencies
With the virtual environment active, install the packages needed by the scrapers:
```bash
pip install -r requirement.txt
```

The `requirement.txt` file includes the core dependencies (`requests`, `facebook-scraper`, `snscrape`).

## Running the scrapers
Use the CLI entry point `scraepr_test1.py` to scrape specific platforms:
```bash
python scraepr_test1.py reddit <subreddit>
python scraepr_test1.py facebook <full_facebook_url>
python scraepr_test1.py threads <threads_url>
python scraepr_test1.py x <username>  # will currently fail because the upstream endpoints are blocked
```

Additional options:
- `--limit N` sets the number of posts to fetch.
- `--skip-media` skips posts containing media.
- `--include-media` forces inclusion of media posts.

Scraped data is saved under the directory defined by `output_root` in `scraper.json` (defaults to `scraepr/`). Each run creates a timestamped JSON file.

### Smoke tests for preset targets

To execute the four demo scenarios described in the main task, run:

```bash
python scraepr_test1.py tests
```

This command sequentially runs the Facebook and Threads scrapers (both primary and fallback strategies) against the provided public targets, logging success or any network issues encountered.

## Deactivate the environment
When you are done:
```bash
deactivate
```
