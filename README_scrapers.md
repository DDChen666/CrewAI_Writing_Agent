# Scrapers Setup Guide

This document explains how to configure the Python environment and run the Reddit and X scrapers used by `scraepr_test1.py`.

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

The `requirement.txt` file includes the core dependencies (`requests`, `snscrape`).

## Running the scrapers
Use the CLI entry point `scraepr_test1.py` to scrape Reddit or X:
```bash
python scraepr_test1.py x <username>
python scraepr_test1.py reddit <subreddit>
```

Additional options:
- `--limit N` sets the number of posts to fetch.
- `--skip-media` skips posts containing media.
- `--include-media` forces inclusion of media posts.

Scraped data is saved under the directory defined by `output_root` in `scraper.json` (defaults to `scraepr/`). Each run creates a timestamped JSON file.

## Deactivate the environment
When you are done:
```bash
deactivate
```
