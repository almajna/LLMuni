# Cost estimate: final

150 tasks (closed_book: 7 models; open_book: 7 models; tool_use: 3 models); uncached calls only; reasoning effort medium, max_tokens 8000. *Calibrated* rows use measured token counts from cached answers; the worst case assumes every call hits max_tokens.

| Model | Calls | Calibrated | Expected | Worst case |
|---|---:|:---:|---:|---:|
| openai/gpt-6-astra | 420 | yes | $110.73 | $2947.36 |
| x-ai/grok-4.7 | 420 | yes | $102.87 | $2532.67 |
| google/gemini-3.1-pro-preview | 420 | yes | $50.61 | $701.31 |
| qwen/qwen3.8-max-prime | 270 | yes | $29.56 | $80.67 |
| anthropic/claude-fable-5.1 | 270 | yes | $26.67 | $234.84 |
| deepseek/deepseek-v4-pro-0813 | 270 | yes | $8.06 | $14.11 |
| meta-llama/llama-4-maverick | 270 | yes | $0.20 | $2.96 |
| **Total** | 2340 | | **$328.71** | $6513.91 |

Budget: $30.00 total across all runs (hard cap).
