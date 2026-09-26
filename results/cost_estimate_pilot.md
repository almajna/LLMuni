# Cost estimate: pilot run

50 tasks x 7 models x modes closed_book, open_book; uncached calls only. Expected assumes 6000 output tokens per answer (reasoning included); worst case assumes every call hits max_tokens=16000.

| Model | Calls | Expected | Worst case |
|---|---:|---:|---:|
| openai/gpt-6-astra | 100 | $31.13 | $81.34 |
| anthropic/claude-fable-5.1 | 100 | $31.13 | $81.34 |
| qwen/qwen3.8-max-prime | 100 | $7.65 | $19.74 |
| google/gemini-3.1-pro-preview | 100 | $7.43 | $19.47 |
| x-ai/grok-4.7 | 100 | $3.06 | $7.89 |
| deepseek/deepseek-v4-pro-0813 | 100 | $0.51 | $1.30 |
| meta-llama/llama-4-maverick | 100 | $0.41 | $1.07 |
| **Total** | 700 | **$81.32** | $212.15 |

Budget: $25.00 (hard cap; calls stop before it would be exceeded).
