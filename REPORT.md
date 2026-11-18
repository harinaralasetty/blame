# Public release preparation

## What works (with evidence)

The README now leads with the published Arena-Hard finding: changed preferences in 500 of 1,500 answer pairs (33.3%), including 268 outright winner reversals and 232 tie/win/loss changes. Its regex example quotes the findings verbatim and includes the candidate's real defect. The detailed command, input and detector reference is preserved in [docs/reference.md](docs/reference.md).

[docs/report.html](docs/report.html) is a 15,266-byte static preview generated with the existing renderer from `realdata/arena_hard/report.json`. It preserves all full-run aggregate tables and the complete audited regex item (sample 4). It explicitly marks 1,825 of 1,826 lost observations as omitted. Source attribution, the Apache-2.0 data license and the meaning of preference units appear in the preview. No screenshot is needed.

`pyproject.toml` now declares the `blame = "blame_cli.cli:main"` console script, a setuptools build backend and explicit package selection. Runtime dependencies remain empty. Build artifacts are gitignored. The README explains the sole build dependency, `setuptools>=77`.

### Fresh-venv quickstart

Verified on Python 3.13.4 in a newly created temporary directory under this checkout's gitignored `validation/release/`. Copied only the package, fixtures, README, LICENSE and pyproject, then ran the README's exact three commands in that directory. Used its local `.venv`, a local temporary/build directory and local pip cache, with the public PyPI index and no inherited Python import path. No packages were installed globally.

Selected actual output, all three commands exited 0 (pip progress and temporary paths omitted):

```text
$ python3 -m venv .venv
$ .venv/bin/python -m pip install .
Successfully built blame-cli
Installing collected packages: blame-cli
Successfully installed blame-cli-0.1.0
$ .venv/bin/blame report fixtures/synthetic.jsonl --out demo
Wrote demo/report.md, report.json, report.html (21 lost items)
```

An additional installed-package smoke check ran from an empty `away/` directory to rule out importing the source checkout. Actual output:

```text
Installed distribution: 0.1.0
Runtime dependencies: None
Module installed in venv: True
Quickstart verified: 36 observations, 21 losses; all three report formats exist.
```

Full local install output is retained in `validation/release/quickstart.txt` (gitignored).

### Release content checks

A standard-library HTML parser and assertions checked source tables, the unchanged example output and judge reasoning, local links, excerpt disclosure, the console entry point, README quotes, post length and the CI matrix. Actual output:

```text
Preview: 15,266 bytes; full-run tables match source; one unchanged audited item; all local links resolve; no scripts or external assets.
Copy: README lead and quotes match FINDINGS.md; no em dashes; LinkedIn post 1109 characters and ends with a question.
Release files: Markdown links resolve; blame entry point and Python 3.11-3.13 make test matrix present. Workflow not executed here.
```

[docs/linkedin_draft.md](docs/linkedin_draft.md) contains the 1,109-character post, including newlines, with one hashtag, a question at the end, and a separate first-comment draft for the repo link. The post count excludes headings, the first comment and the editor note.

### PyPI name check

Checked the official PyPI JSON endpoints on 2026-10-29, using both the web tool and curl. Actual curl output:

```text
blame: HTTP 200
eval-blame: HTTP 404
blame-evals: HTTP 404
eval-loss-triage: HTTP 404
```

[`blame`](https://pypi.org/project/blame/) is already registered to another project, version 0.0.1, described as "Development experience insights". Three proposed distribution names had no registered project at check time: [`eval-blame`](https://pypi.org/pypi/eval-blame/json), [`blame-evals`](https://pypi.org/pypi/blame-evals/json), and [`eval-loss-triage`](https://pypi.org/pypi/eval-loss-triage/json). A 404 does not reserve a name or guarantee PyPI will accept registration. The existing local distribution name `blame-cli` is unchanged and was not claimed available for publication. The command stays `blame`. Nothing was published.

### Test suite

Actual final command output for 0.1.0 (45 tests), exit 0. The suite has grown since: 0.2.0 runs 160 tests; `make test` prints the current list.

```text
$ make test
python3 -m unittest discover -s tests -v
test_all_score_mappings_account_for_order_and_collapse_strength (test_arena_hard.ArenaHardTests.test_all_score_mappings_account_for_order_and_collapse_strength) ... ok
test_mismatched_published_prompt_is_rejected_instead_of_joined (test_arena_hard.ArenaHardTests.test_mismatched_published_prompt_is_rejected_instead_of_joined) ... ok
test_real_reversal_fires_with_unchanged_generation_and_full_reasoning (test_arena_hard.ArenaHardTests.test_real_reversal_fires_with_unchanged_generation_and_full_reasoning) ... ok
test_same_winner_after_swap_does_not_fabricate_instability (test_arena_hard.ArenaHardTests.test_same_winner_after_swap_does_not_fabricate_instability) ... ok
test_abstain_on_single_model_partial_credit_or_changed_rubric (test_detectors.EveryoneTests.test_abstain_on_single_model_partial_credit_or_changed_rubric) ... ok
test_zero_across_models_and_runs (test_detectors.EveryoneTests.test_zero_across_models_and_runs) ... ok
test_error_discussion_is_not_infrastructure_failure (test_detectors.InfraTests.test_error_discussion_is_not_infrastructure_failure) ... ok
test_rule_table_positive_examples (test_detectors.InfraTests.test_rule_table_positive_examples) ... ok
test_all_identity_boundaries (test_detectors.JudgeTests.test_all_identity_boundaries) ... ok
test_pairwise_flip_rate_and_quotes (test_detectors.JudgeTests.test_pairwise_flip_rate_and_quotes) ... ok
test_anchor_types (test_detectors.UnstatedTests.test_anchor_types) ... ok
test_injected_reasoner_and_default (test_detectors.UnstatedTests.test_injected_reasoner_and_default) ... ok
test_literal_presence_boundaries_and_abstentions (test_detectors.UnstatedTests.test_literal_presence_boundaries_and_abstentions) ... ok
test_missing_anchors_and_closest_sentence (test_detectors.UnstatedTests.test_missing_anchors_and_closest_sentence) ... ok
test_precedence_preserves_overlapping_matches (test_detectors.UnstatedTests.test_precedence_preserves_overlapping_matches) ... ok
test_generic_optional_fields (test_inputs.GenericTests.test_generic_optional_fields) ... ok
test_multiple_files_deduplicate_and_reject_conflicting_judges (test_inputs.GenericTests.test_multiple_files_deduplicate_and_reject_conflicting_judges) ... ok
test_source_line_in_validation_error (test_inputs.GenericTests.test_source_line_in_validation_error) ... ok
test_validation (test_inputs.GenericTests.test_validation) ... ok
test_dictionary_scores_and_no_rubric_fallback (test_inputs.InspectTests.test_dictionary_scores_and_no_rubric_fallback) ... ok
test_documented_handwritten_fixture (test_inputs.InspectTests.test_documented_handwritten_fixture) ... ok
test_message_input_text_blocks_completion_and_score_metadata (test_inputs.InspectTests.test_message_input_text_blocks_completion_and_score_metadata) ... ok
test_missing_judge_run_is_not_inferred_from_epoch (test_inputs.InspectTests.test_missing_judge_run_is_not_inferred_from_epoch) ... ok
test_reject_unsupported_instead_of_faking_scores_or_text (test_inputs.InspectTests.test_reject_unsupported_instead_of_faking_scores_or_text) ... ok
test_unscored_sample_warning_and_sample_error (test_inputs.InspectTests.test_unscored_sample_warning_and_sample_error) ... ok
test_1_explanations_and_bare_numbers_are_not_infra (test_review_round1.ReviewRound1Tests.test_1_explanations_and_bare_numbers_are_not_infra) ... ok
test_2_safe_csv_cells_retain_original_record (test_review_round1.ReviewRound1Tests.test_2_safe_csv_cells_retain_original_record) ... ok
test_3_csv_errors_have_path_line_and_status_2 (test_review_round1.ReviewRound1Tests.test_3_csv_errors_have_path_line_and_status_2) ... ok
test_3_writer_long_answer_can_be_scored (test_review_round1.ReviewRound1Tests.test_3_writer_long_answer_can_be_scored) ... ok
test_4_tool_only_choices_rejected_with_serialized_completion (test_review_round1.ReviewRound1Tests.test_4_tool_only_choices_rejected_with_serialized_completion) ... ok
test_5_generic_extra_inspect_fields_are_ignored (test_review_round1.ReviewRound1Tests.test_5_generic_extra_inspect_fields_are_ignored) ... ok
test_5_jsonl_only_splits_on_newlines (test_review_round1.ReviewRound1Tests.test_5_jsonl_only_splits_on_newlines) ... ok
test_6_judge_groups_are_scanned_once (test_review_round1.ReviewRound1Tests.test_6_judge_groups_are_scanned_once) ... ok
test_7_complete_numeric_tokens (test_review_round1.ReviewRound1Tests.test_7_complete_numeric_tokens) ... ok
test_7_prohibitions_and_examples_abstain (test_review_round1.ReviewRound1Tests.test_7_prohibitions_and_examples_abstain) ... ok
test_8_mit_license_and_metadata (test_review_round1.ReviewRound1Tests.test_8_mit_license_and_metadata) ... ok
test_9_oversized_integer_is_contextual_status_2 (test_review_round1.ReviewRound1Tests.test_9_oversized_integer_is_contextual_status_2) ... ok
test_precision_recall_with_false_positives_false_negatives_and_overlap (test_workflow.LabelTests.test_precision_recall_with_false_positives_false_negatives_and_overlap) ... ok
test_reject_invalid_labels_duplicate_ids_and_inconsistent_predictions (test_workflow.LabelTests.test_reject_invalid_labels_duplicate_ids_and_inconsistent_predictions) ... ok
test_template_preserves_text_and_blanks (test_workflow.LabelTests.test_template_preserves_text_and_blanks) ... ok
test_bad_input_fails_without_writing_report (test_workflow.WorkflowTests.test_bad_input_fails_without_writing_report) ... ok
test_cli_end_to_end_and_repeatable_reports (test_workflow.WorkflowTests.test_cli_end_to_end_and_repeatable_reports) ... ok
test_fixture_shape_and_all_expected_verdicts (test_workflow.WorkflowTests.test_fixture_shape_and_all_expected_verdicts) ... ok
test_html_is_self_contained_and_escapes_untrusted_text (test_workflow.WorkflowTests.test_html_is_self_contained_and_escapes_untrusted_text) ... ok
test_partial_loss_and_all_pass_model (test_workflow.WorkflowTests.test_partial_loss_and_all_pass_model) ... ok

----------------------------------------------------------------------
Ran 45 tests in 0.358s

OK
```

## What is heuristic/faked

No new benchmark run or independent annotation was performed in this release pass. The real-data claims come from the retained [findings](realdata/FINDINGS.md). The 12/12 disagreement and 8/8 cohort-loss checks were conducted by Codex and establish fidelity to the documented predicates on that sample, not eval-fault attribution precision. There is no measured recall or audited default-case precision. Answer-order swaps do not isolate causal positional bias.

The README demo is synthetic. The Inspect fixture is hand-written and was not validated against an installed Inspect package. Infrastructure and missing-requirement rules remain heuristics; confidence values are fixed strengths, not calibrated probabilities. `genuine_failure` remains the default for unclassified losses. A cohort-wide zero or judge disagreement is a review hypothesis and can coexist with real candidate defects. The shipped reasoner is deterministic; the existing `Reasoner` interface remains the extension point for an LLM. No LLM API calls were made.

## What failed or is flaky

The first direct PyPI check using Python's `urllib` failed because this machine's Python could not verify the certificate chain. Actual exception excerpt:

```text
ssl.SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1028)
```

The web tool and system curl verified the endpoints successfully. The clean-venv pip install also succeeded with certificate verification enabled. No trust settings were changed.

No test failures or flaky behavior were observed in the final suite. Local verification used Python 3.13.4 only. The new [GitHub Actions workflow](.github/workflows/tests.yml) runs `make test` on Python 3.11, 3.12 and 3.13; it was not executed here. Preview structure and content were checked programmatically; no browser rendering or accessibility audit was performed.

There is no git remote configured (`git remote -v` returned no output), so the LinkedIn first comment uses `REPO_URL` rather than an invented public URL. The draft explicitly marks that replacement. Package installation from a checkout was tested; PyPI publication was not attempted.

## Next steps

Replace `REPO_URL` with the actual public repository URL before posting. Let the added workflow run on GitHub before claiming the full Python matrix passes. If publishing a distribution later, choose and recheck one of the proposed names while keeping the `blame` command.

## Verdict

The release material now leads with a reproducible public result and a concrete example, explains the precision and attribution limits, and provides a small static preview plus a verified three-command installation path. The existing 45-test suite passes locally on Python 3.13.4. The LinkedIn draft meets the requested length and format, with the actual repo URL still to fill in. The CI matrix is configured but unrun. This supports sharing the tool as a local eval-review aid without claiming validated causal attribution. All changes remain uncommitted; no push or publication was performed.
