| model | mode | feasible_pct | median_gap | impossible_plan_pct | hallucination_pct | wrong_address_pct | not_in_osm_pct | correct_infeasible_pct | cost_per_task_usd |
|---|---|---|---|---|---|---|---|---|---|
| x-ai/grok-4.7 | closed_book | 0.0 | — | 40.7 | 37.5 | 43.8 | 50.0 | 100.0 | 0.0999 |
| anthropic/claude-fable-5.1 | closed_book | 0.0 | — | 66.7 | 3.7 | 66.7 | 55.6 | 100.0 | 0.1129 |
| deepseek/deepseek-v4-pro-0813 | closed_book | 0.0 | — | 66.7 | 13.6 | 81.8 | 27.3 | 100.0 | 0.0202 |
| openai/gpt-6-astra | closed_book | 0.0 | — | 70.4 | 11.1 | 63.0 | 48.1 | 100.0 | 0.0874 |
| qwen/qwen3.8-max-prime | closed_book | 0.0 | — | 88.9 | 4.0 | 96.0 | 28.0 | 100.0 | 0.1061 |
| google/gemini-3.1-pro-preview | closed_book | 0.0 | — | 92.6 | 18.5 | 81.5 | 37.0 | 100.0 | 0.035 |
| meta-llama/llama-4-maverick | closed_book | 0.0 | — | 96.3 | 69.0 | 93.1 | 13.8 | 33.3 | 0.0009 |
| openai/gpt-6-astra | open_book | 96.3 | 0.0185 | 3.7 | 0.0 | 0.0 | 0.0 | 100.0 | 0.0685 |
| x-ai/grok-4.7 | open_book | 96.3 | 0.0697 | 0.0 | 0.0 | 0.0 | 0.0 | 100.0 | 0.0831 |
| google/gemini-3.1-pro-preview | open_book | 92.6 | 0.0828 | 7.4 | 0.0 | 0.0 | 0.0 | 100.0 | 0.0405 |
| anthropic/claude-fable-5.1 | open_book | 85.2 | 0.0217 | 14.8 | 0.0 | 0.0 | 0.0 | 100.0 | 0.0949 |
| qwen/qwen3.8-max-prime | open_book | 77.8 | 0.1316 | 22.2 | 0.0 | 0.0 | 0.0 | 100.0 | 0.1212 |
| baseline:greedy | open_book | 70.4 | 0.0849 | 22.2 | 0.0 | 0.0 | 0.0 | 66.7 | 0.0 |
| deepseek/deepseek-v4-pro-0813 | open_book | 59.3 | 0.113 | 14.8 | 0.0 | 0.0 | 0.0 | 100.0 | 0.0335 |
| meta-llama/llama-4-maverick | open_book | 55.6 | 0.2642 | 44.4 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0005 |
| baseline:random | open_book | 37.0 | 0.8598 | 63.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
