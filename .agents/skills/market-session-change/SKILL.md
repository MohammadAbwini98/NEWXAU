---
name: market-session-change
description: Modify or review XAUUSD market-session behavior while preserving Asia/Amman conversion, DAILY_BREAK priority, aliases, and boundary correctness.
---

# Market Session Change

1. Read `market_sessions.py`, Control Unit/session consumers, dashboard rendering, and focused tests.
2. Use `Asia/Amman`; never use server-local time. Store source timestamps in UTC.
3. Preserve canonical intervals and `DAILY_BREAK` as non-trading with highest overlap priority.
4. Preserve legacy aliases where compatibility requires them.
5. Inspect every session-name consumer before changing labels or schedules.
6. Test exact boundaries, midnight crossing, aliases, and non-trading behavior; update memory and run the checker.
