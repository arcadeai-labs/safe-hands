# SafeAgentBench dataset (vendored)

Four JSONL files copied verbatim from
[shengyin1224/SafeAgentBench](https://github.com/shengyin1224/SafeAgentBench) at commit
`38ca3ab` (2025-02-25), `dataset/` directory. MIT License, copyright the SafeAgentBench authors
(Yin et al., "SafeAgentBench: A Benchmark for Safe Task Planning of Embodied LLM Agents",
[arXiv:2412.13178](https://arxiv.org/abs/2412.13178)).

| file | records | used by eval.py as |
|---|---|---|
| `unsafe_detailed_1009.jsonl` | 300 hazardous, with reference plans | DEV = first 150, TEST = last 150 |
| `safe_detailed_1009.jsonl`   | 300 safe counterparts                | DEV = first 150, TEST = last 150 |
| `abstract_1009.jsonl`        | 100 hazardous, abstract phrasing     | TEST, all 100 |
| `long_horizon_1009.jsonl`    | 50 tasks with a prose ordering constraint | not scored (no reference plan) |

Vendored so the evaluation is reproducible offline and in CI. Nothing in these files was edited.
