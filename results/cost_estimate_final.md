# Cost estimate: final

150 tasks (closed_book: 7 models; open_book: 7 models); uncached calls only; reasoning effort medium, max_tokens 8000. *Calibrated* rows use measured costs of cached answers (per model, mode and tier); the worst case assumes every call hits its output cap.

| Model | Calls | Calibrated | Expected | Worst case |
|---|---:|:---:|---:|---:|
| qwen/qwen3.8-max-prime | 270 | yes | $29.56 | $80.67 |
| anthropic/claude-fable-5.1 | 270 | yes | $26.67 | $234.84 |
| x-ai/grok-4.7 | 270 | yes | $24.04 | $194.95 |
| openai/gpt-6-astra | 270 | yes | $20.26 | $223.28 |
| google/gemini-3.1-pro-preview | 270 | yes | $9.48 | $53.30 |
| deepseek/deepseek-v4-pro-0813 | 270 | yes | $8.06 | $14.11 |
| meta-llama/llama-4-maverick | 270 | yes | $0.20 | $2.96 |
| **Total** | 1890 | | **$118.27** | $804.10 |

Budget: $29.00 total across all runs (hard cap).

Under this budget: rounds 6-10 fit (15 new tasks, one per tier per round): expected $13.14 of the $15.86 left. A round (one task per tier) starts only if the budget left covers 1.25x its expected cost.
