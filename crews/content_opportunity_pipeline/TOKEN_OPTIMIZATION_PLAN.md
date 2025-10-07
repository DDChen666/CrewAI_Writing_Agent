# Content Opportunity Pipeline Token Optimisation Plan

## Background
The `crews/content_opportunity_pipeline` crew chains four Gemini agents that coordinate through a set of Reddit-specific tools. Recent runs show rapid token growth on both input and output channels, which can be traced to the tools streaming large JSON payloads between agents. The current defaults prioritise completeness, but they make it easy for any agent call that omits explicit limits to pull thousands of fields at once.

## Current Pressure Points
1. **Dataset explorer tools stream the entire corpus by default.**
   * `reddit_dataset_lookup` returns the full list of stored summaries whenever `post_ids` and `limit` are omitted, so a single call can emit hundreds of posts with full metadata.【F:crews/content_opportunity_pipeline/tools.py†L1045-L1084】
   * `content_explorer` follows the same pattern via `_select_pointers`, and it also materialises full normalised posts (with comments) without a guard rail, multiplying tokens when agents inspect trends.【F:crews/content_opportunity_pipeline/tools.py†L1103-L1187】
2. **Exports embed multi-field previews that exceed downstream needs.**
   * `reddit_dataset_exporter` always injects the preview slice into `content_stream.items`. Even at the default preview of 10 posts, each record carries ~20 keys, so the payload dominates the hand-off context despite the task spec asking for compact summaries.【F:crews/content_opportunity_pipeline/tools.py†L1015-L1044】
3. **Loader responses echo full records twice when focus filters are applied.**
   * When `max_items` or `filters` are supplied, the loader adds a `focus_view` list on top of the existing `preview`, duplicating heavy post objects instead of returning lightweight references.【F:crews/content_opportunity_pipeline/tools.py†L928-L1007】
4. **Comment retrieval has no sampling guard.**
   * Requesting `data_level="full_comments"` surfaces entire trees, and the recursion can expand quickly because there is no automatic cap on descendants beyond the top-level `comment_limit`.【F:crews/content_opportunity_pipeline/tools.py†L1150-L1176】

## Design Principles
* **Minimal surface changes:** Adjust defaults and payload shapes without rewriting tool APIs so existing prompts remain valid.
* **Token-aware summaries:** Replace bulky arrays with ID-first digests that agents can expand on demand using existing lookup capabilities.
* **Quality preservation:** Keep schema fidelity so downstream agents can still compute trend metrics and reference pointers.

## Proposed Iterations
1. **Introduce conservative default limits.**
   * Add a module-wide constant (e.g. `DEFAULT_SAMPLE_LIMIT = 20`) applied whenever lookup or explorer calls are made without explicit `limit`/`post_ids`. Include a `truncated` flag in responses so agents know to request more when truly necessary.【F:crews/content_opportunity_pipeline/tools.py†L1045-L1187】
2. **Slim down exporter previews.**
   * Replace `content_stream.items` with a `preview` section that only carries `post_id`, `title`, `score`, `permalink`, and `raw_pointer`. Keep counts and aggregate statistics so later agents can fetch full posts via lookup if required.【F:crews/content_opportunity_pipeline/tools.py†L1015-L1044】
3. **Deduplicate loader focus outputs.**
   * Change `reddit_scrape_loader` so `focus_view` contains only `post_id` references (plus essential metrics) instead of entire summary dicts, or reuse the trimmed preview structure proposed above.【F:crews/content_opportunity_pipeline/tools.py†L928-L1007】
4. **Comment tree safeguards.**
   * Apply a recursive cap (e.g. max descendants of 100 by default) and surface a `comments_truncated` indicator when the limit is hit. This keeps qualitative analysis intact while preventing runaway context dumps.【F:crews/content_opportunity_pipeline/tools.py†L1132-L1176】
5. **Prompt hygiene updates.**
   * Update the Data Triage and Trend Analysis task descriptions to remind agents to request explicit limits or rely on lookup tools for deep dives, aligning behaviour with the new conservative defaults.【F:crews/content_opportunity_pipeline/tasks.py†L14-L78】

## Implementation Plan
1. **Baseline tests:** Capture current tool outputs on a medium dataset to quantify token counts for `lookup`, `explorer`, and `exporter` calls.
2. **Apply code changes:** Implement steps 1–4 above, ensuring backwards-compatible JSON keys and adding documentation for new flags/limits.
3. **Update prompts:** Refine task `expected_output` guidance so agents expect condensed previews and know how to expand datasets on demand.
4. **Regression pass:** Re-run the sandbox workflow (or unit tests if available) verifying that each agent still receives schema-compliant JSON and that token deltas fall within the target range.
5. **Document learnings:** Append a section to `README_content_opportunity_pipeline.md` covering the new defaults and recommended agent prompting patterns.

## Expected Outcome
These adjustments should cut inter-agent payload size by ~60–80% in the nominal case while preserving the structured metadata needed for clustering, scoring, and brief creation. Agents can still retrieve full objects using explicit parameters, but the pipeline now defaults to token-frugal summaries that align with the "索引全量、按需深挖" operating principle.
