# Phase 3: task set v2026.10

300 tasks, pilot subset of 50 (benchmark/v2026.10/pilot_ids.json).

| tier | tasks | infeasible | by mode | errands (mean) | with end | with deadlines | branded | closing soon |
|---|---|---|---|---|---|---|---|---|
| easy | 100 | 10 | closed 3, deadline_too_early 3, end_too_early 4 | 3.0 | 30 | 3 | 5 | 0 |
| medium | 100 | 10 | closed 3, deadline_too_early 3, end_too_early 4 | 4.5 | 47 | 3 | 5 | 97 |
| hard | 100 | 10 | closed 3, deadline_too_early 3, end_too_early 4 | 6.5 | 100 | 97 | 27 | 0 |

Errands per category: hardware 128, bank_atm 127, florist 123, supermarket 121, library 120, post_office 119, bakery 116, coffee 113, pharmacy 112, bookstore 109, bike_shop 106, dry_cleaning 102.

Weekdays: Monday 31, Tuesday 38, Wednesday 35, Thursday 50, Friday 47, Saturday 51, Sunday 48.

## Example prompts

**v2026.10-easy-000**

> It's Wednesday, October 7, and I'm heading out from 9th & Folsom (SoMa) around 12:05 pm. No car today: just Muni, BART and walking. Today I need to withdraw cash at a bank or ATM (about 5 minutes), pick up a prescription at a pharmacy (about 10 minutes), and get a replacement faucet washer at a hardware store (about 10 minutes). Which specific stores should I go to, and in what order, so I'm done as early as possible? If it can't all be done, tell me it's impossible and why.

**v2026.10-medium-000**

> Plan my Thursday (October 8) for me. I'll leave 6th Ave & Clement (Richmond) at 4:55 pm. I don't have a car, so I'll get around on Muni, BART and on foot. Today I need to drop off library books at a library (about 10 minutes), buy picture hooks at a hardware store (about 10 minutes), drop off a suit at a dry cleaner (about 5 minutes), pick up groceries at a supermarket (about 20 minutes), and pick up a prescription at a pharmacy (about 10 minutes). When I'm done I'm meeting a friend at 24th & Valencia (Mission) and need to be there by 7:40 pm. Tell me exactly which stores to visit and in what order so I finish as early as I can. If it can't all be done, tell me it's impossible and why.

**v2026.10-hard-000**

> Help me plan errands on Friday, October 9. I start at 3rd & Evans (Bayview) at 11:10 am. I don't have a car, so I'll get around on Muni, BART and on foot. Today I need to buy a new inner tube at a bike shop (about 20 minutes), drop off a suit at a dry cleaner (about 5 minutes), pick up a coffee at a café (about 10 minutes), drop off library books at a library (about 10 minutes), buy a birthday present at a bookstore (about 15 minutes), and buy picture hooks at a hardware store (about 10 minutes). I have to buy a birthday present at a bookstore by 12:55 pm at the latest. When I'm done I'm meeting a friend at Grant & Washington (Chinatown) and need to be there by 1:45 pm. Tell me exactly which stores to visit and in what order so I finish as early as I can. If it can't all be done, tell me it's impossible and why.
