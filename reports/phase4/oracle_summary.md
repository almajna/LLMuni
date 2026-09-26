# Phase 4: oracle for v2026.10

Optimum over the listed stores (open-book / tool modes) and over every valid store in SF (closed book).

| tier | tasks | feasible | optimal duration, median (min) | global beats listed stores | median gain (min) | DP seconds, p95 (global) |
|---|---|---|---|---|---|---|
| easy | 100 | 90 | 60 | 29 | 5 | 0.07 |
| medium | 100 | 90 | 97 | 53 | 4 | 0.11 |
| hard | 100 | 90 | 148 | 59 | 9 | 0.66 |

- Brute force (every order x every listed store) reproduces the DP optimum on 100/100 easy tasks.
- HiGHS MILP on static relaxations agrees with the DP on 90/90 easy tasks (0 skipped: a listed store had split hours that day).
- Every infeasible task is proven infeasible by the exhaustive DP in both universes.
