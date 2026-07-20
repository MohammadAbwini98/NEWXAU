---
name: playwright-automation
description: Use only if the project contains Playwright or browser automation. Currently marked as optional since Playwright was not found in the codebase.
---

# Playwright Automation Skill

> **Note**: Playwright or browser automation was *not found* in the codebase during initial review. This file serves as a placeholder if UI test automation is added later.

If adding browser automation:

## Stable Selector Rules
- Use `data-testid` attributes whenever possible.
- Avoid selecting by fragile CSS classes or XPath.

## Flow Design Rules
- Keep tests isolated; do not share state between test cases.

## Human-like Browser Automation Rules
- If scraping or interacting with external APIs, introduce randomized delays.

## JSON-driven Input Rules
- Separate test data from test scripts using JSON fixtures.

## Concurrent Instance Rules
- Ensure browser contexts are strictly isolated to avoid cookie cross-contamination.

## Screenshot/Logging Rules
- Take screenshots on failure and attach them to the test report.

## Retry/Timeout Rules
- Use Playwright's built-in auto-waiting. Do not use explicit `sleep()` unless absolutely necessary.
- Configure automatic retries for flaky tests.
