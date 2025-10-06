# Scrapers Setup Guide

This document explains how to configure the Python environment and run the Reddit scraper used by `scraepr_test1.py`.

> [!NOTE]
> As of the last update, only the Reddit scraper in `scrapers/` is operational. The Facebook, Threads, and X/Twitter implementations are present in the repository but currently fail at runtime. Keep an eye on future updates if you need those adapters.

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

## Configure Reddit credentials
The Reddit scraper now authenticates via the official Reddit Data API. Set up your credentials before running it:

1. Copy `.env.example` to `.env` (or export the variables directly in your shell).
2. Fill in the following keys with the values from your Reddit application:
   - `REDDIT_CLIENT_ID`
   - `REDDIT_CLIENT_SECRET`
   - `REDDIT_USER_AGENT` (e.g. `myscript/1.0 by u/your_username`)
3. The scraper automatically loads `.env` and will raise an error if any value is missing.

> [!TIP]
> Official credentials significantly reduce rate limiting and ensure the workflow remains compliant with Reddit's Terms of Service.

## Running the scrapers
Use the CLI entry point `scraepr_test1.py` to scrape Reddit:
```bash
python scraepr_test1.py reddit <subreddit>
```

Additional options:
- `--limit N` sets the number of posts to fetch.
- `--skip-media` skips posts containing media.
- `--include-media` forces inclusion of media posts.

Scraped data is saved under the directory defined by `output_root` in `scraper.json` (defaults to `scraepr/`). Each run creates a timestamped JSON file.

### Inactive scrapers

The following entry points remain in the script for future repair work but will currently error if invoked:

```bash
python scraepr_test1.py facebook <full_facebook_url>
python scraepr_test1.py threads <threads_url>
python scraepr_test1.py x <username>
```

They are documented here so you can recognize the intended interface when maintenance resumes.

### Smoke tests for preset targets

To execute the demo scenario for Reddit, run:

```bash
python scraepr_test1.py tests
```

This command currently validates only the Reddit workflow. The Facebook, Threads, and X checks remain disabled because their scrapers are broken.

## Deactivate the environment
When you are done:
```bash
deactivate
```
