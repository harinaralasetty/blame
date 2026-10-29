# Implementation report

## What works (with evidence)

The local CLI reads generic JSONL and the documented Inspect v2 text JSON subset. It writes Markdown, JSON, and one static HTML file with class/model summaries and per-observation drill-down. Every verdict includes evidence and a fixed confidence. There are no third-party dependencies or LLM calls. Verification used Python 3.13.4 in this workspace.

The generic fixture contains three tasks, three models, two judge runs, and two rubric items per task: 36 records. All four detectors fire, and six lost records use the default class. Negative controls explicitly assert that the formal greeting cases do not fire any detector. Tests also cover error discussion versus actual error-shaped output, changed judge identities, partial credit, missing judge IDs, quoted missing terms, input validation, CSV quoting, metric mistakes and overlaps, escaping, and repeatable CLI output.

Actual command output, exit 0:

```text
$ make test
python3 -m unittest discover -s tests -v
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
test_precision_recall_with_false_positives_false_negatives_and_overlap (test_workflow.LabelTests.test_precision_recall_with_false_positives_false_negatives_and_overlap) ... ok
test_reject_invalid_labels_duplicate_ids_and_inconsistent_predictions (test_workflow.LabelTests.test_reject_invalid_labels_duplicate_ids_and_inconsistent_predictions) ... ok
test_template_preserves_text_and_blanks (test_workflow.LabelTests.test_template_preserves_text_and_blanks) ... ok
test_bad_input_fails_without_writing_report (test_workflow.WorkflowTests.test_bad_input_fails_without_writing_report) ... ok
test_cli_end_to_end_and_repeatable_reports (test_workflow.WorkflowTests.test_cli_end_to_end_and_repeatable_reports) ... ok
test_fixture_shape_and_all_expected_verdicts (test_workflow.WorkflowTests.test_fixture_shape_and_all_expected_verdicts) ... ok
test_html_is_self_contained_and_escapes_untrusted_text (test_workflow.WorkflowTests.test_html_is_self_contained_and_escapes_untrusted_text) ... ok
test_partial_loss_and_all_pass_model (test_workflow.WorkflowTests.test_partial_loss_and_all_pass_model) ... ok

----------------------------------------------------------------------
Ran 29 tests in 0.249s

OK
```

Actual demo and CSV template command output, both exit 0:

```text
$ make demo
python3 -m blame_cli report fixtures/synthetic.jsonl --out demo
Wrote demo/report.md, report.json, report.html (21 lost items)
python3 -m blame_cli report fixtures/inspect.json --out demo-inspect
Wrote demo-inspect/report.md, report.json, report.html (2 lost items)
$ ./blame label fixtures/synthetic.jsonl --out labels.csv
Wrote labels.csv (21 rows; human_label is blank)
```

`./blame score labels.csv` returned exit 0, with 0 labeled rows and 21 unlabeled rows. All precision/recall values were null, as expected for an untouched template. The template does not present predicted labels as human truth.

For a separate arithmetic check, `validation/synthetic-labels.csv` contains five manually constructed rows, not human annotations: one infra true positive, two infra false positives, one infra false negative, an overlapping unstated-requirement match, and one blank human label. The full real command output below demonstrates the calculation, not measured detector quality on real data. Exit 0:

```text
$ ./blame score validation/synthetic-labels.csv
{
  "labeled_rows": 4,
  "unlabeled_rows": 1,
  "note": "Blank human labels excluded; undefined precision/recall is null. Counts are per scored observation. Synthetic labels do not establish real precision.",
  "per_detector": {
    "infra": {
      "tp": 1,
      "fp": 2,
      "fn": 1,
      "support": 2,
      "precision": 0.3333333333333333,
      "recall": 0.5
    },
    "judge_unstable": {
      "tp": 0,
      "fp": 0,
      "fn": 0,
      "support": 0,
      "precision": null,
      "recall": null
    },
    "item_everyone_loses": {
      "tp": 0,
      "fp": 0,
      "fn": 0,
      "support": 0,
      "precision": null,
      "recall": null
    },
    "unstated_requirement": {
      "tp": 1,
      "fp": 0,
      "fn": 0,
      "support": 1,
      "precision": 1.0,
      "recall": 1.0
    },
    "genuine_failure": {
      "tp": 0,
      "fp": 1,
      "fn": 1,
      "support": 1,
      "precision": 0.0,
      "recall": 0.0
    }
  },
  "per_verdict": {
    "infra": {
      "tp": 1,
      "fp": 2,
      "fn": 1,
      "support": 2,
      "precision": 0.3333333333333333,
      "recall": 0.5
    },
    "judge_unstable": {
      "tp": 0,
      "fp": 0,
      "fn": 0,
      "support": 0,
      "precision": null,
      "recall": null
    },
    "item_everyone_loses": {
      "tp": 0,
      "fp": 0,
      "fn": 0,
      "support": 0,
      "precision": null,
      "recall": null
    },
    "unstated_requirement": {
      "tp": 0,
      "fp": 0,
      "fn": 1,
      "support": 1,
      "precision": null,
      "recall": 0.0
    },
    "genuine_failure": {
      "tp": 0,
      "fp": 1,
      "fn": 1,
      "support": 1,
      "precision": 0.0,
      "recall": 0.0
    }
  }
}
```

Artifact checks parsed both JSON reports, checked class/model counts against the drill-down, checked the generated file names, and compared the README excerpt with the actual Markdown. Actual verification output:

```text
demo: 3 report files; 36 scored observations; 21 lost items; 21 lost points
demo-inspect: 3 report files; 2 scored observations; 2 lost items; 1.5 lost points
README excerpt matches the generated report; no em dashes in README.
```

The HTML parser test verifies two summary tables, one details block per tested lost observation, escaped script text, and no external asset attributes. End-to-end tests compare report bytes across repeated runs.

## What is heuristic/faked

All task, model, output and score data in the fixtures is invented. `fixtures/inspect.json` was hand-written from the official Inspect field references linked in README. It was not emitted or validated by an installed Inspect package. No `inspect_ai` dependency was installed.

Infrastructure matching uses one table of strict text patterns. The missing-requirement detector uses literal anchors and limited name/unit extraction, with word overlap for the closest sentence. It misses uncertain names and semantic equivalents; it can flag a number that was implied by an instruction. Missing literal text is evidence to review, not proof that a requirement is unfair. `Reasoner` is an injection point; the shipped implementation is deterministic.

The everyone-loses class describes only the supplied cohort. Judge flip rates measure score disagreements among distinct explicit judge runs, including fractional scores. Confidence values are fixed strengths without statistical calibration. `genuine_failure` is the required fallback and does not prove model responsibility. Repeated judges count as separate scored observations in summaries and metrics.

## What failed or is flaky

An early detector test found that an alternation guard did not abstain on `Include "hello" or "hi".`. The word-boundary pattern was corrected; the final test output above includes that passing negative case. No test failures remained in the final run. No flaky behavior was observed in these runs.

The required milestone commit could not be created. The workspace permission profile makes `.git` read-only, so staging failed before the commit could run. Actual output from the attempted staging command, exit 128:

```text
$ git add .gitignore Makefile blame blame_cli fixtures tests
fatal: Unable to create '/Users/harinaralasetty/Development Work/blame/.git/index.lock': Operation not permitted
```

All implementation files remain in the current working directory and are uncommitted. Nothing was pushed. No files outside the working directory were read or written by shell commands, and no environment files or shared Python environments were used.

Verification ran on Python 3.13.4; compatibility with 3.11 is based on the language features used, not a separate interpreter run. HTML was checked structurally, without a browser rendering check. Binary Inspect logs, multimodal content, unresolved attachments, header-only logs, invalidated samples and ambiguous score encodings are intentionally unsupported and produce errors. Samples without scores produce warnings and are omitted rather than assigned invented zero scores.

## Next steps

Collect independent human labels using the CSV template before publishing detector precision. Validate the adapter against a real public Inspect text JSON export. When this workspace permits Git writes, create the requested milestone commit. No further implementation is needed for the stated acceptance checks.

## Verdict

The requested local CLI and fixture acceptance checks pass: `make test` passes 29 tests, and `make demo` creates all three report formats for both inputs. The reports expose the evidence, counts, uncertainty, and overlapping detector matches, and the labeling workflow calculates precision/recall without treating predictions as ground truth. This is a deterministic triage aid with documented heuristic limits, not an adjudicator of model fault. Real-data precision and actual Inspect-export compatibility remain unmeasured. The only unmet workflow requirement is committing the work, which the read-only Git permission prevented.
