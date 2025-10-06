# Content Opportunity Pipeline

This package contains the agents and tools that power the Content Opportunity Pipeline.

## Data Triage Agent

The Data Triage Agent is the first stage of the pipeline. It:

- Discovers relevant Reddit scrape files using `reddit_scrape_locator`.
- Loads and normalises submissions through `reddit_scrape_loader`.
- Applies additional ranking and filtering via `reddit_dataset_filter`.
- Exports a `Cleaned_Content_Stream` payload using `reddit_dataset_exporter`.

All transformations are executed by tools so the language model never reads raw JSON directly.

## Trend Analysis Agent

The Trend Analysis Agent converts the `Cleaned_Content_Stream` into an `Identified_Trends_Report`:

- Clusters semantically similar posts to surface potential topic clusters.
- Calculates trend velocity and acceleration to highlight emerging signals.
- Labels overall sentiment, recognises key opinion leaders and tags lifecycle stages.
- Uses the `reddit_dataset_lookup` tool to inspect representative Reddit posts as needed.

## Brand Alignment Agent

The Brand Alignment Agent evaluates trend clusters against the JustKa AI brand guardrails:

- Cross-references the Brand Core Knowledge Base to score relevance and ICP alignment.
- Assigns funnel stages (TOFU/MOFU/BOFU) and performs qualitative risk assessments.
- Emits a `ScoredAndFilteredOpportunities` structure that preserves key momentum metrics.
- Leverages `reddit_dataset_lookup` to pull context for in-depth audience analysis.

## Topic Curator Agent

The Topic Curator Agent turns the highest value opportunities into production-ready briefs:

- Prioritises 1–3 standout topics using strategic impact and urgency signals.
- Generates 3–5 on-brand editorial angles per topic and documents supporting insights.
- Outputs a `PrioritizedTopicBrief` JSON payload consumable by downstream planners.
