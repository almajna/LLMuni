# Checkpoint 2: example tasks

## Easy: v2026.10-easy-009

> It's Wednesday, October 7, and I'm heading out from 3rd & 22nd (Dogpatch) around 10:25 am. I don't have a car, so I'll get around on Muni, BART and on foot. Today I need to get cash from a bank or ATM (about 5 minutes), grab a coffee at a café (about 10 minutes), and drop off a suit at a dry cleaner (about 5 minutes). Tell me exactly which stores to visit and in what order so I finish as early as I can. If it can't all be done, tell me it's impossible and why.

| # | Errand | Store | Arrive | Start | Done | Getting there |
|---|---|---|---|---|---|---|
| 1 | Coffee | Paper Son Coffee - Dogpatch | 10:27 am | 10:27 am | 10:37 am | Walk 3 |
| 2 | Bank / ATM | Chase | 10:50 am | 10:50 am | 10:55 am | Walk 14 |
| 3 | Dry cleaning | Fanta Cleaners | 11:07 am | 11:07 am | 11:12 am | Walk 1 → T THIRD 10 → Walk 2 |

Optimal finish **11:12 am** (47 min) over the listed stores; over every store in SF: 11:05 am (40 min).

![v2026.10-easy-009](example_easy.png)

## Medium: v2026.10-medium-002

> Plan my Thursday (October 8) for me. I'll leave Columbus & Union (North Beach) at 2:55 pm. I don't have a car, so I'll get around on Muni, BART and on foot. Today I need to drop off library books at a library (about 10 minutes), pick up a prescription at a pharmacy (about 10 minutes), drop off a parcel at a post office (about 15 minutes), withdraw cash at a bank or ATM (about 5 minutes), and drop off a suit at a dry cleaner (about 5 minutes). When I'm done I'm meeting a friend at 6th Ave & Clement (Richmond) and need to be there by 5:15 pm. Which specific stores should I go to, and in what order, so I'm done as early as possible? If it can't all be done, tell me it's impossible and why.

| # | Errand | Store | Arrive | Start | Done | Getting there |
|---|---|---|---|---|---|---|
| 1 | Post office | Chinatown Station | 3:03 pm | 3:03 pm | 3:18 pm | Walk 10 |
| 2 | Pharmacy | CVS Pharmacy | 3:48 pm | 3:48 pm | 3:58 pm | Walk 1 → T THIRD 2 → Walk 1 → 38R GEARY RAPID 19 → Walk 1 |
| 3 | Dry cleaning | Soapbox | 3:59 pm | 3:59 pm | 4:04 pm | Walk 1 |
| 4 | Library | Richmond Branch - San Francisco Public Library | 4:14 pm | 4:14 pm | 4:24 pm | Walk 2 → 38 GEARY 3 → Walk 2 |
| 5 | Bank / ATM | Industrial and Commercial Bank of China | 4:27 pm | 4:27 pm | 4:32 pm | Walk 4 |
| → | End | 6th Ave & Clement | 4:33 pm | | | Walk 2 |

Optimal finish **4:33 pm** (98 min) over the listed stores; over every store in SF: 4:30 pm (95 min).

![v2026.10-medium-002](example_medium.png)

## Hard: v2026.10-hard-009

> Plan my Sunday (October 11) for me. I'll leave 6th Ave & Clement (Richmond) at 11:05 am. I don't have a car, so I'll get around on Muni, BART and on foot. Today I need to get a replacement faucet washer at a hardware store (about 10 minutes), pick up a book I ordered at a bookstore (about 15 minutes), grab my prescription from a pharmacy (about 10 minutes), return books at a library (about 10 minutes), grab a coffee at a café (about 10 minutes), get a bouquet from a florist (about 10 minutes), and pick up a loaf of bread at a bakery (about 5 minutes). I have to pick up a book I ordered at a bookstore by 11:40 am at the latest. I have to grab my prescription from a pharmacy by 12:15 pm at the latest. When I'm done I'm meeting a friend at 3rd & Palou (Bayview) and need to be there by 2:05 pm. Which specific stores should I go to, and in what order, so I'm done as early as possible? If it can't all be done, tell me it's impossible and why.

| # | Errand | Store | Arrive | Start | Done | Getting there |
|---|---|---|---|---|---|---|
| 1 | Bookstore | Green Apple Books | 11:05 am | 11:05 am | 11:20 am | Walk 0 |
| 2 | Coffee | Pixlcat "Butter Mochi" Coffee | 11:20 am | 11:20 am | 11:30 am | Walk 1 |
| 3 | Hardware | Standard Plumbing Ace Hardware | 11:34 am | 11:34 am | 11:44 am | Walk 5 |
| 4 | Pharmacy | CVS Pharmacy | 11:50 am | 11:50 am | 12:00 pm | Walk 7 |
| 5 | Bakery | Arsicault Bakery | 12:04 pm | 12:04 pm | 12:09 pm | Walk 4 |
| 6 | Florist | La Poblanita | 12:47 pm | 12:47 pm | 12:57 pm | Walk 4 → 38R GEARY RAPID 19 → Walk 3 → BART Blue-S 6 → Walk 2 |
| 7 | Library | Mission Temporary Branch, San Francisco Public Library | 1:02 pm | 1:02 pm | 1:12 pm | Walk 5 |
| → | End | 3rd & Palou | 1:44 pm | | | Walk 17 → 24 DIVISADERO 13 → Walk 0 |

Optimal finish **1:44 pm** (159 min) over the listed stores; over every store in SF: 1:32 pm (147 min).

![v2026.10-hard-009](example_hard.png)

