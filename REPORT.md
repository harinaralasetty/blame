# Implementation report

## What works (with evidence)

The dependency-free CLI reads generic JSONL and the documented Inspect v2 text JSON subset, renders JSON, Markdown and static HTML, exports human-labeling CSV, and calculates label metrics. The implementation remains offline and deterministic, with a small injectable `Reasoner` interface and no LLM calls.

This fix round used Python 3.13.4. The full suite now has 45 passing tests: 33 existing tests and 12 review regression tests with subcases. All temporary test files were created under this working directory and removed by the tests. No packages were installed. No commits or pushes were attempted in this round.

Actual final command output, exit 0:

```text
$ PYTHONDONTWRITEBYTECODE=1 make test
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
Ran 45 tests in 0.356s

OK
```

The existing end-to-end tests run report, label and score as subprocesses, check the synthetic verdict counts, and compare report bytes across repeated runs. They also verify HTML escaping, blank-label handling, overlapping detector metrics, input validation, Inspect mappings and public-data adapter behavior. The seven temporary-directory tests reported as blocked by the reviewer passed here.

## Review round 1

I reproduced every finding with `tests/test_review_round1.py` before changing production code. I saw each finding's regression fail against the old implementation. Some tests contain multiple subcases, so the failure count exceeds the test count. The first run exited 1; its actual summary was:

```text
$ PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_review_round1.py -v

----------------------------------------------------------------------
Ran 12 tests in 0.135s

FAILED (failures=36, errors=4)
```

The full initial failure output and intermediate runs are retained locally under `validation/review-round1/` (gitignored). Each numbered item below corresponds to the review finding. All named regressions pass in the final suite above; none of the findings was rebutted.

1. **Ordinary answers blamed on infrastructure.** `test_1_explanations_and_bare_numbers_are_not_infra` reproduced `infra` verdicts for the reported `429`, `500`, timeout explanation and rate-limit explanation, plus other trailing prose. I saw these subcases fail before the fix. The text rules now require whole failure phrases, explicit HTTP/status context for otherwise bare codes, and narrowly constrained suffixes. Bare numeric answers and explanatory prose use the default verdict; a repeated-judge disagreement on output `429` is now visible. Existing positive examples still pass. A standalone failure phrase remains inherently ambiguous, and an explicit error field still takes precedence by contract.

2. **Spreadsheet formula prefixes.** `test_2_safe_csv_cells_retain_original_record` reproduced unchanged formula prefixes in every user-controlled display field, starting with `=1+1`. I saw the escaping assertion fail before the fix. The writer now prefixes risky cells with an apostrophe, including `=`, `+`, `-`, `@`, leading whitespace before those characters, and leading tab/CR/LF. A separate `original_record_json` column retains the entire exact record as inert JSON; tests deserialize it and compare all fields. Stable IDs and blank human labels are unchanged, and `score` accepts the export. This verifies emitted CSV bytes and round-trip preservation, not execution in a spreadsheet application.

3. **CSV writer/reader size mismatch and uncaught parser errors.** `test_3_writer_long_answer_can_be_scored` reproduced exit 1 with `_csv.Error: field larger than field limit (131072)` for an exported 131,073-character output. I saw that regression fail before the fix. Reading now temporarily sets the field limit to `sys.maxsize`, matching Python's string size policy, then restores the previous process setting. Memory remains the practical limit. The long export scores successfully. `test_3_csv_errors_have_path_line_and_status_2` also failed before the fix because malformed CSV lacked path context. Strict parsing now converts `csv.Error` into `ValueError` with the path and physical line; the existing CLI returns status 2 without a traceback. The unterminated second-line field is reported as CSV line 2.

4. **Inspect tool-only bypass through completion.** `test_4_tool_only_choices_rejected_with_serialized_completion` reproduced acceptance of tool-only choices with empty, whitespace and nonempty serialized completions. I saw those subcases fail before the fix. Choices are now checked independently before selecting completion text. Any tool-only choice is rejected with the explicit generic-export guidance; the absent-completion negative case still rejects, and ordinary text completions still pass the existing tests.

5. **Generic format detection and Unicode separators.** Both `test_5_generic_extra_inspect_fields_are_ignored` and `test_5_jsonl_only_splits_on_newlines` errored before the fix. The former reproduced Inspect sniffing on valid generic records with extra `eval`/`samples` fields. The latter reproduced JSON string splitting at U+2028. Generic records identified by their `task_id` now take precedence over Inspect sniffing, with normal validation still applied. JSONL splits on actual LF delimiters, accepts CRLF, and preserves U+2028, U+2029 and U+0085 inside strings. These are synthetic input files, not personal data.

6. **Cubic repeated-judge analysis.** `test_6_judge_groups_are_scanned_once` failed before the fix: 40 identical-score judges caused 3,280 identity reads, exceeding the regression bound of 160; mixed scores caused 2,470. Disagreement now counts distinct judge runs by score once per identity group. Unequal pairs equal all unordered pairs minus equal-score pairs from frequency counts. The summary is reused for all lost observations, without materializing pairs. Tests cover agreement and fractional-score disagreement, and existing tests retain duplicate-run and identity-boundary checks.

   I also ran the reviewer's timing workload before and after the fix. Actual outputs in seconds on this machine:

```text
Before:
200 identical-score judges: 0.24 seconds
400 identical-score judges: 2.066 seconds
800 identical-score judges: 15.929 seconds
After:
200 identical-score judges: 0.006 seconds
400 identical-score judges: 0.015 seconds
800 identical-score judges: 0.051 seconds
```

   The command used for both measurements was:

```sh
python3 -B -c 'from time import perf_counter; from blame_cli.model import Record; from blame_cli.detectors import triage
for n in (200,400,800):
 records=[Record("t","m","r","Answer.","i","Be correct.","wrong",0,"Wrong.",j) for j in range(n)]
 start=perf_counter(); triage(records); print(n,"identical-score judges:",round(perf_counter()-start,3),"seconds")'
```

   These are observations, not timing assertions. The full triage pipeline is not claimed to be linear: cohort scans remain per observation, and copying per-judge evidence into each verdict can require quadratic output size when judges disagree.

7. **Missing-requirement boundaries and abstentions.** `test_7_complete_numeric_tokens` reproduced treating `12` as present inside `12.5`; signed and percent subcases also failed. `test_7_prohibitions_and_examples_abstain` reproduced treating `avoid` and plural `examples` as positive requirements. I saw both regressions fail before the fix. Extraction and presence checks now share complete numeric-token syntax, including signs, decimals, exponents and percent suffixes. Prohibition words (`avoid`, `omit`, `exclude`), plural examples and `for instance` now conservatively cause abstention. Exact numeric presence and the existing quoted-string, unit, entity, negation and alternative tests still pass. This remains literal matching, not semantic inference.

8. **Missing release license.** `test_8_mit_license_and_metadata` failed before the fix because the repository root had no LICENSE. Added the requested MIT license with `Copyright (c) 2026 Hari Naralasetty`, a README licensing section, and `pyproject.toml` metadata with `license = "MIT"`, `license-files = ["LICENSE"]`, author, Python requirement and no dependencies. The regression checks the license grant, attribution and parsed metadata. Existing public-data licensing remains separate. Package building or publication was not requested or tested.

9. **Oversized integer score crash.** `test_9_oversized_integer_is_contextual_status_2` reproduced an uncaught `OverflowError` and exit 1 for `10**400`. I saw that assertion fail before the fix. The range check now runs before `math.isfinite`, so out-of-range integers are rejected before float conversion. The CLI regression verifies status 2, path plus line 1, the score-validation message, no traceback and no report output.

## What is heuristic/faked

The new regressions use synthetic records only. Existing fixtures are invented; the hand-written Inspect fixture was not validated by an installed `inspect_ai`. Public-data adapter tests use the existing public Arena-Hard inputs; attribution and limitations remain in `realdata/`.

Infrastructure matching, requirement anchors and fixed confidence values are heuristics. An empty output or supplied error field is still treated as infrastructure evidence. The requirement reasoner deliberately abstains on supported prohibition/example constructions and cannot resolve all English phrasing, implied requirements or semantic equivalents. `genuine_failure` is the default when no detector fires and does not establish model responsibility. Judge disagreements and cohort-wide zeros describe supplied observations, not proof of a faulty evaluation.

## What failed or is flaky

The initial regression failures were expected reproductions and are recorded above. An intermediate implementation reported an unterminated CSV field at line 1 because `DictReader.line_num` was stale when parsing raised; this was corrected to use the underlying CSV reader's consumed physical line count. The final malformed-CSV regression verifies line 2. No failures remained in the final full suite and no flaky behavior was observed. Benchmark times depend on the machine; the regression uses operation counts instead of elapsed time.

Spreadsheet escaping was verified as serialized data, without opening Excel or LibreOffice; saving through another application can change its escaping. CSV fields and reports remain memory-bound. Python 3.11 compatibility follows from the standard-library APIs and syntax used; only Python 3.13.4 was run here. No real Inspect installation, package build, publication or new human-label study was performed.

## Next steps

The reviewer can inspect and commit these changes. Independent human labeling and a real public Inspect text export remain useful validation work outside this fix round. No further implementation is needed for these nine findings.

## Verdict

All nine review findings were reproduced and fixed with regressions observed failing before the fixes. The final `make test` run passes all 45 tests, including the previously blocked temporary-directory workflows. The CLI now avoids the reported false infrastructure verdicts, exports escaped spreadsheet cells with exact originals retained, handles long and malformed CSV, rejects tool-only Inspect output consistently, preserves valid generic JSONL, reuses judge disagreement counts, respects the tested requirement boundaries, validates huge scores safely, and includes the requested MIT license and metadata. This supports release as a small offline triage utility with documented heuristic limits; it does not establish real-world detector precision. Changes are uncommitted as requested.
