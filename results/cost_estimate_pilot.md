# Cost estimate: pilot

15 tasks (closed_book: 7 models; open_book: 7 models); uncached calls only; reasoning effort medium, max_tokens 8000. *Calibrated* rows use measured token counts from cached answers; the worst case assumes every call hits max_tokens.

| Model | Calls | Calibrated | Expected | Worst case |
|---|---:|:---:|---:|---:|
| qwen/qwen3.8-max-prime | 19 | yes | $1.43 | $5.67 |
| anthropic/claude-fable-5.1 | 18 | yes | $1.16 | $14.88 |
| openai/gpt-6-astra | 18 | yes | $0.97 | $14.88 |
| x-ai/grok-4.7 | 22 | yes | $0.62 | $12.53 |
| google/gemini-3.1-pro-preview | 18 | yes | $0.55 | $3.55 |
| deepseek/deepseek-v4-pro-0813 | 19 | yes | $0.50 | $0.99 |
| meta-llama/llama-4-maverick | 19 | yes | $0.01 | $0.21 |
| **Total** | 133 | | **$5.25** | $52.72 |

Budget: $27.00 total across all runs (hard cap).
