# Content Opportunity Pipeline

This package contains the agents and tools that power the Content Opportunity Pipeline.

## Data Triage Agent

The Data Triage Agent is the first stage of the pipeline. It:

- Discovers relevant Reddit scrape files using `reddit_scrape_locator`.
- Loads and normalises submissions through `reddit_scrape_loader`.
- Applies additional ranking and filtering via `reddit_dataset_filter`.
- Exports a `Cleaned_Content_Stream` payload using `reddit_dataset_exporter`.

All transformations are executed by tools so the language model never reads raw JSON directly.
