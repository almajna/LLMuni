# Cost estimate: calibration

5 tasks (open_book: 7 models); uncached calls only; reasoning effort medium, max_tokens 8000. *Calibrated* rows use measured token counts from cached answers; the worst case assumes every call hits max_tokens.

| Model | Calls | Calibrated | Expected | Worst case |
|---|---:|:---:|---:|---:|
| openai/gpt-6-astra | 5 | no | $1.57 | $2.09 |
| anthropic/claude-fable-5.1 | 5 | no | $1.57 | $2.09 |
| qwen/qwen3.8-max-prime | 5 | no | $0.39 | $0.52 |
| google/gemini-3.1-pro-preview | 5 | no | $0.37 | $0.50 |
| x-ai/grok-4.7 | 5 | no | $0.16 | $0.21 |
| deepseek/deepseek-v4-pro-0813 | 5 | no | $0.03 | $0.03 |
| meta-llama/llama-4-maverick | 5 | no | $0.02 | $0.03 |
| **Total** | 35 | | **$4.11** | $5.46 |

Budget: $27.00 total across all runs (hard cap).
