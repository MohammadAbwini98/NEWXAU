---
name: playwright-automation
description: Dormant optional guidance. Use only after Playwright or browser automation is explicitly added to NEWXAU; do not load for normal dashboard work.
---

# Playwright Automation Skill

> **Dormant:** Playwright is not a current NEWXAU dependency. Do not require, install, or load this skill by default.

If adding browser automation:

## Stable Selector Rules
- Use `data-testid` attributes whenever possible.
- Avoid selecting by fragile CSS classes or XPath.

## Flow Design Rules
- Keep tests isolated; do not share state between test cases.

## JSON-driven Input Rules
- Separate test data from test scripts using JSON fixtures.

## Concurrent Instance Rules
- Ensure browser contexts are strictly isolated to avoid cookie cross-contamination.

## Screenshot/Logging Rules
- Take screenshots on failure and attach them to the test report.

## Retry/Timeout Rules
- Use Playwright's built-in auto-waiting. Do not use explicit `sleep()` unless absolutely necessary.
- Configure automatic retries for flaky tests.
