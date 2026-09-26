# Phase 4: oracle for v2026.10

Optimum over the listed stores (open-book / tool modes) and over every valid store in SF (closed book).

| tier | tasks | feasible | optimal duration, median (min) | global beats listed stores | median gain (min) | DP seconds, p95 (global) |
|---|---|---|---|---|---|---|
| easy | 100 | 90 | 60 | 24 | 4 | 0.1 |
| medium | 100 | 90 | 95 | 58 | 4 | 0.17 |
| hard | 100 | 90 | 146 | 64 | 8 | 0.88 |

- Brute force (every order x every listed store) reproduces the DP optimum on 100/100 easy tasks.
- HiGHS MILP on static relaxations agrees with the DP on 90/90 easy tasks (0 skipped: a listed store had split hours that day).
- Every infeasible task is proven infeasible by the exhaustive DP in both universes.
