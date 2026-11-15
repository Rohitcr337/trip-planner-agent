# Retrieval experiment results

All experiments rebuilt the local index before evaluation. No test cases,
queries, snippets, threshold logic beyond the explicitly tested values, or
retrieval behavior were changed. Rows marked reverted were not kept.

| Experiment | Easy top-4 | Easy top-1 | Easy MRR | Hard top-4 | Hard top-1 | Hard MRR | Hard rejection |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 100% | 90% | 0.950 | 53.3% | 46.7% | 0.483 | 3/5 |
| City + section TF-IDF prefix (reverted) | 95% | 80% | 0.875 | 53.3% | 33.3% | 0.417 | 2/5 |
| Sublinear TF-IDF + English stop words (reverted) | 90% | 80% | 0.850 | 53.3% | 33.3% | 0.411 | 3/5 |
| Word bigrams (reverted) | 70% | 65% | 0.675 | 33.3% | 33.3% | 0.333 | 4/5 |
| 150-word chunks (reverted) | 100% | 80% | 0.892 | 53.3% | 33.3% | 0.400 | 3/5 |
| Threshold 0.2 (reverted) | 30% | 30% | 0.300 | 20.0% | 20.0% | 0.200 | 5/5 |

The threshold search found no value that both rejects all five unanswerable
hard cases and preserves the easy-set 100% top-4 rate. The original threshold
of 0.1 is therefore retained. The hard set has only 15 answerable cases, so
differences of one or two cases are noise.
