# Content Opportunity Pipeline Token Optimisation – Implementation Plan

## Objectives
* Reduce default token usage across lookup, explorer, loader, and exporter tools while preserving retrieval fidelity.
* Maintain backwards compatibility for existing prompts and downstream automation.
* Surface explicit telemetry (truncation flags, counts) so agents can request deeper pulls only when justified.

## Workstreams & Tasks

### 1. Baseline Measurement & Safety Net
1. Capture representative tool outputs before any code changes:
   * Run `reddit_dataset_lookup`, `content_explorer_tool`, and `reddit_dataset_exporter` on a mid-sized dataset with default parameters.
   * Record token counts, payload sizes, and schema samples for later regression comparison.
2. Add lightweight snapshot fixtures if practical to help future testing without shipping large JSON blobs.

### 2. Guarded Defaults for Dataset Tools
1. Introduce `DEFAULT_SAMPLE_LIMIT` (value 20) and `DEFAULT_COMMENT_DESCENDANT_LIMIT` constants in `tools.py`.
2. Apply the sample limit inside `reddit_dataset_lookup` and `content_explorer_tool` when callers omit `limit`/`post_ids`.
3. Extend responses with a boolean `truncated` field and, when applicable, a `truncated_reason` string documenting which guard fired.
4. Update unit/helper functions so that limit-aware pagination honours the new defaults without double truncation.

### 3. Slimmed Exporter & Loader Payloads
1. Refactor `reddit_dataset_exporter` to replace `content_stream.items` with a `preview` array containing only:
   * `post_id`, `title`, `score`, `permalink`, and `raw_pointer` (plus `created_utc` when available for ordering).
2. Ensure aggregate metadata (`total_items`, `filters_applied`, etc.) remains intact for downstream reporting.
3. Adjust `reddit_scrape_loader` so that both its `preview` and `focus_view` reuse the slim preview schema, eliminating duplicate full objects.
4. Provide helper serializers to keep preview construction consistent between exporter and loader paths.

### 4. Comment Tree Safeguards
1. Add recursive traversal logic that counts descendants; stop expanding once `DEFAULT_COMMENT_DESCENDANT_LIMIT` is reached.
2. Mark the response with `comments_truncated: true` and `comment_sample_size` when truncation occurs.
3. Retain full fidelity for top-level comments already under explicit `comment_limit` requests to avoid regressions for narrow queries.

### 5. Prompt & Documentation Alignment
1. Update task prompts in `tasks.py` so agents are instructed to:
   * Provide explicit limits when they truly need large slices.
   * Use lookup tools for post-level deep dives rather than relying on default previews.
2. Refresh `README_content_opportunity_pipeline.md` with the new defaults, flags, and recommended agent prompting patterns.
3. Mention the truncation indicators and how to request expanded datasets in runbooks and onboarding docs.

### 6. Verification & Regression
1. Re-run the end-to-end sandbox scenario with the updated code and capture the new token metrics, comparing them to the baseline.
2. Validate that schema changes are backwards compatible (e.g., optional new fields, existing keys preserved or thoughtfully deprecated).
3. Spot-check trend clustering and topic briefs to ensure they still reference posts via `dataset_id`/`post_id` successfully.

## Deliverables
* Code updates to `crews/content_opportunity_pipeline/tools.py` and `tasks.py` implementing the guard rails and preview changes.
* Documentation updates reflecting the new behaviour.
* Measurement notes demonstrating token reductions and confirming functional parity.

## Risks & Mitigations
* **Risk:** Downstream agents relying on removed keys from previews.
  * **Mitigation:** Provide migration notes and keep detailed data fetch available via explicit lookup requests.
* **Risk:** Truncation flags ignored by prompts leading to partial analyses.
  * **Mitigation:** Explicitly call out truncation handling in prompt updates and readme, and consider adding agent evaluation checks.

## Timeline (Indicative)
* **Day 1:** Baseline capture and constant introduction.
* **Day 2:** Implement exporter/loader refactors and comment safeguards.
* **Day 3:** Prompt/documentation updates and regression verification.

