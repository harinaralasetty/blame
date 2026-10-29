# Source attribution and modifications

Source: [lmarena-ai/arena-hard-auto](https://huggingface.co/datasets/lmarena-ai/arena-hard-auto),
revision `15f3746e21432264ce9b453999bde4f3c946d2e6`, Arena-Hard v0.1.
The dataset card declares Apache-2.0. See the included `LICENSE` and unchanged
`SOURCE_README.md` for the upstream card and citation.

Tianle Li, Wei-Lin Chiang, Evan Frick, Lisa Dunlap, Tianhao Wu, Banghua Zhu,
Joseph E. Gonzalez and Ion Stoica. *From Crowdsourced Data to High-Quality
Benchmarks: Arena-Hard and BenchBuilder Pipeline* (2024).
https://arxiv.org/abs/2406.11939

The reports and audit files in this directory are modified/derived extracts:
blame field conversion, numeric preference mapping, triage results, aggregate
counts, sample selection and annotations were added on 2026-10-29. Retained
source prompt/answer/judgment strings are unmodified. Large full reports and raw
bulk files remain under gitignored `data/`. `audit_evidence.json` wraps selected
original pair objects with provenance and cohort score metadata. These additions
are analysis by this repository and are not conclusions endorsed by the dataset
authors or model providers.

License text copied from the upstream project at:
https://github.com/lmarena/arena-hard-auto/blob/196f6b826783b3da7310e361a805fa36f0be83f3/LICENSE
