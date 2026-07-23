#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const requiredMemoryFiles = [
  "AGENTS.md",
  "CLAUDE.md",
  "GEMINI.md",
  "docs/ai/README.md",
  "docs/ai/PROJECT_BRIEF.md",
  "docs/ai/PROJECT_CONTEXT.md",
  "docs/ai/CURRENT_STATE.md",
  "docs/ai/HANDOFF.md",
  "docs/ai/FEATURES.md",
  "docs/ai/ARCHITECTURE.md",
  "docs/ai/COMMANDS.md",
  "docs/ai/RULES.md",
  "docs/ai/CODING_RULES.md",
  "docs/ai/DATABASE.md",
  "docs/ai/KNOWN_ISSUES.md",
  "docs/ai/TASK_LOG.md",
  "docs/ai/DECISIONS.md",
  "docs/ai/SECURITY.md",
  "docs/ai/TESTING.md",
  "docs/ai/DEVELOPMENT_WORKFLOW.md",
];
const requiredHandoffAdapters = [
  ".claude/commands/HANDOFF.md",
  ".claude/commands/TAKEOFF.md",
  ".agents/skills/agent-handoff/SKILL.md",
  ".agents/skills/agent-takeoff/SKILL.md",
  ".agents/workflows/HANDOFF.md",
  ".agents/workflows/TAKEOFF.md",
  ".gemini/commands/HANDOFF.toml",
  ".gemini/commands/TAKEOFF.toml",
];
const optionalAdapters = [
  ".agents/skills/ai-memory-maintainer/SKILL.md",
  ".agents/skills/backend-api-review/SKILL.md",
  ".agents/skills/code-review/SKILL.md",
  ".agents/skills/frontend-ui-review/SKILL.md",
  ".agents/skills/safe-database-changes/SKILL.md",
  ".agents/skills/testing-and-validation/SKILL.md",
  ".agents/skills/feature-implementation/SKILL.md",
  ".agents/skills/bug-fix/SKILL.md",
  ".agents/skills/trading-pipeline-change/SKILL.md",
  ".agents/skills/capital-execution-safety/SKILL.md",
  ".agents/skills/model-and-training/SKILL.md",
  ".agents/skills/news-intelligence/SKILL.md",
  ".agents/skills/market-session-change/SKILL.md",
  ".agents/skills/performance-concurrency-review/SKILL.md",
  ".agents/skills/security-review/SKILL.md",
  ".agents/skills/docs-sync/SKILL.md",
  ".agents/skills/refactor-safe/SKILL.md",
  ".agents/skills/pr-review/SKILL.md",
  ".claude/skills/ai-memory-maintainer/SKILL.md",
  ".claude/skills/code-review/SKILL.md",
  ".claude/skills/feature-implementation/SKILL.md",
  ".claude/skills/bug-fix/SKILL.md",
  ".claude/skills/testing-and-validation/SKILL.md",
  ".claude/skills/docs-sync/SKILL.md",
  ".claude/skills/refactor-safe/SKILL.md",
  ".claude/skills/pr-review/SKILL.md",
  ".claude/skills/trading-pipeline-change/SKILL.md",
  ".claude/skills/capital-execution-safety/SKILL.md",
  ".claude/skills/safe-database-changes/SKILL.md",
  ".claude/skills/model-and-training/SKILL.md",
  ".claude/skills/news-intelligence/SKILL.md",
  ".claude/skills/market-session-change/SKILL.md",
  ".gemini/commands/ai-memory.toml",
  ".cursor/rules/00-project.mdc",
  ".cursor/rules/10-python-fastapi.mdc",
  ".cursor/rules/20-trading-pipeline.mdc",
  ".cursor/rules/30-capital-execution-safety.mdc",
  ".cursor/rules/40-storage-database.mdc",
  ".cursor/rules/50-models-kronos.mdc",
  ".cursor/rules/60-dashboard-realtime.mdc",
  ".cursor/rules/70-news-intelligence.mdc",
  ".cursor/rules/80-market-sessions.mdc",
  ".cursor/rules/90-safety.mdc",
];
const handoffHeadings = [
  "## Status",
  "## Objective",
  "## Completed",
  "## In Progress",
  "## Blockers / Unknowns",
  "## Next Safe Actions",
  "## Files Changed",
  "## Verification Performed",
  "## Verification Still Required",
  "## Safety Notes",
];
const scanRoots = [
  ".agents/skills",
  ".agents/workflows",
  ".claude/commands",
  ".claude/skills",
  ".gemini/commands",
  ".cursor/rules",
];
const scanExtensions = new Set([".md", ".mdc", ".toml"]);
const placeholders = new Set([
  "", "...", "todo", "tbd", "changeme", "change_me", "redacted", "example",
  "example_value", "your_value", "your-token", "your_token", "your-password",
  "your_password", "not_set",
]);
let failed = false;

function fail(message) {
  console.error(`ERROR: ${message}`);
  failed = true;
}

function warn(message) {
  console.warn(`WARN: ${message}`);
}

function ok(message) {
  console.log(`OK: ${message}`);
}

function fullPath(file) {
  return path.join(root, ...file.split("/"));
}

function exists(file) {
  return fs.existsSync(fullPath(file));
}

function read(file) {
  return fs.readFileSync(fullPath(file), "utf8");
}

function toRelative(filePath) {
  return path.relative(root, filePath).split(path.sep).join("/");
}

function isPlaceholder(value) {
  const normalized = value.trim().replace(/^["']|["']$/g, "").toLowerCase();
  return placeholders.has(normalized)
    || normalized.startsWith("<")
    || normalized.startsWith("your_")
    || normalized.startsWith("example_")
    || normalized.includes("redacted")
    || normalized.includes("placeholder");
}

function collectFiles(directory) {
  const start = fullPath(directory);
  if (!fs.existsSync(start)) return [];
  const results = [];
  const pending = [start];
  while (pending.length) {
    const current = pending.pop();
    const entries = fs.readdirSync(current, { withFileTypes: true })
      .sort((left, right) => left.name.localeCompare(right.name));
    for (const entry of entries) {
      const entryPath = path.join(current, entry.name);
      if (entry.isDirectory()) pending.push(entryPath);
      else if (entry.isFile() && scanExtensions.has(path.extname(entry.name).toLowerCase())) results.push(toRelative(entryPath));
    }
  }
  return results.sort();
}

function findSecretLikeLines(content) {
  const hits = [];
  const lines = content.split(/\r?\n/);
  const assignment = /\b(api[_-]?key|api[_-]?secret|token|password|secret|cst|x-security-token|cookie|session[_-]?(?:cookie|token|id))\b\s*[:=]\s*["']?([^\s#"']+)/i;
  const tokenPatterns = [
    { type: "GitHub token", pattern: /\bgh[pousr]_[A-Za-z0-9]{20,}\b/ },
    { type: "OpenAI-style token", pattern: /\bsk-[A-Za-z0-9_-]{20,}\b/ },
    { type: "AWS access key", pattern: /\bAKIA[A-Z0-9]{16}\b/ },
    { type: "Google API key", pattern: /\bAIza[A-Za-z0-9_-]{35}\b/ },
    { type: "Slack token", pattern: /\bxox[baprs]-[A-Za-z0-9-]{20,}\b/ },
    { type: "Bearer token", pattern: /\bBearer\s+[A-Za-z0-9._~+/=-]{12,}/i },
    { type: "Credential-bearing DSN", pattern: /\bpostgres(?:ql)?:\/\/[^\s:@/]+:[^\s@/]+@/i },
  ];

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    if (/-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/i.test(line)) {
      hits.push({ line: index + 1, type: "Private key" });
      continue;
    }
    const tokenHit = tokenPatterns.find(({ pattern }) => pattern.test(line));
    if (tokenHit) {
      hits.push({ line: index + 1, type: tokenHit.type });
      continue;
    }
    const match = line.match(assignment);
    if (match && !isPlaceholder(match[2] || "") && (match[2] || "").length >= 8) {
      hits.push({ line: index + 1, type: match[1] });
    }
  }
  return hits;
}

for (const file of [...requiredMemoryFiles, ...requiredHandoffAdapters]) {
  if (!exists(file)) {
    fail(`Missing required file: ${file}`);
    continue;
  }
  if (!read(file).trim()) fail(`Empty required file: ${file}`);
}

for (const file of optionalAdapters) {
  if (!exists(file)) warn(`Optional adapter is missing: ${file}`);
}

const rootFiles = ["AGENTS.md", "CLAUDE.md", "GEMINI.md"];
for (const file of rootFiles) {
  if (!exists(file)) continue;
  const content = read(file);
  if (!content.includes("docs/ai/README.md")) fail(`${file} should reference docs/ai/README.md`);
  if (!content.includes("docs/ai/HANDOFF.md")) fail(`${file} should reference docs/ai/HANDOFF.md`);
}

if (exists("CLAUDE.md") && !read("CLAUDE.md").includes("AGENTS.md")) fail("CLAUDE.md should reference AGENTS.md");
if (exists("GEMINI.md") && !read("GEMINI.md").includes("AGENTS.md")) fail("GEMINI.md should reference AGENTS.md");
if (exists("AGENTS.md")) {
  const agents = read("AGENTS.md");
  if (!agents.includes("docs/ai/")) fail("AGENTS.md should point agents to docs/ai/");
  if (!agents.includes("XAUUSD")) fail("AGENTS.md should contain current XAUUSD context");
  if (!agents.includes("CAPITAL_EXECUTION_DEMO_ONLY")) fail("AGENTS.md should preserve CAPITAL_EXECUTION_DEMO_ONLY guidance");
  if (!agents.includes("Asia/Amman") && !agents.includes("market_sessions.py")) fail("AGENTS.md should reference canonical market-session rules");
  if (agents.includes("src/dashboard_static/")) fail("AGENTS.md contains stale src/dashboard_static/ path");
}
if (exists("GEMINI.md") && /(?:natively handling|current default[^\n]*)ETHUSD/i.test(read("GEMINI.md"))) {
  fail("GEMINI.md describes ETHUSD as the current default");
}

if (exists("docs/ai/HANDOFF.md")) {
  const handoff = read("docs/ai/HANDOFF.md");
  for (const heading of handoffHeadings) {
    if (!handoff.includes(heading)) fail(`docs/ai/HANDOFF.md is missing heading: ${heading}`);
  }
}

const scanFiles = new Set(requiredMemoryFiles);
for (const directory of scanRoots) {
  for (const file of collectFiles(directory)) scanFiles.add(file);
}
for (const file of [...scanFiles].sort()) {
  if (!exists(file)) continue;
  for (const hit of findSecretLikeLines(read(file))) {
    fail(`Possible ${hit.type} in ${file} line ${hit.line}`);
  }
}

if (exists(".claude/scheduled_tasks.lock")) {
  warn("Transient .claude/scheduled_tasks.lock is present; remove it from tracking and ignore .claude/*.lock");
}

if (!failed) ok("AI memory and cross-agent architecture passed required checks.");
process.exit(failed ? 1 : 0);
