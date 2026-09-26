# Phase 5: grader round trip

Each feasible task's all-SF optimal plan, restated as a closed-book answer (store name + address, no ids),
then matched and replayed by the grader.

- Tasks replayed to exactly the optimal finish: **230/270**; other outcomes: feasible 12, infeasible 22, unverifiable 6.
- Stops matched back to the optimal plan's own store: **1208/1256** (by method: address 1068, nearest_branch 105, name 83).

Stops matched to a different store (name-only fallback picks a branch of the same chain):

- v2026.10-easy-031: Walgreens -> w194903899 (matched, nearest_branch)
- v2026.10-easy-049: Golden 1 Credit Union ATM -> n10874914127 (matched, nearest_branch)
- v2026.10-easy-065: Bank of America ATM -> n806228029 (matched, nearest_branch)
- v2026.10-easy-076: Walgreens -> n1639950739 (matched, nearest_branch)
- v2026.10-easy-093: FedEx 24h office -> n4632000744 (matched, nearest_branch)
- v2026.10-medium-000: Walgreens -> n1966301828 (matched, nearest_branch)
- v2026.10-medium-001: Bank of America ATM -> n3504141935 (matched, nearest_branch)
- v2026.10-medium-002: Walgreens -> n1639950739 (matched, nearest_branch)
- v2026.10-medium-010: Wells Fargo -> n13226586649 (unverifiable, address)
- v2026.10-medium-011: Wells Fargo -> n13226586649 (unverifiable, address)
- v2026.10-medium-015: Bank of America ATM -> n340235848 (matched, nearest_branch)
- v2026.10-medium-016: Walgreens -> n459506892 (matched, nearest_branch)
