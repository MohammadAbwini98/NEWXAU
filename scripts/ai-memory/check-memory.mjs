#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const requiredFiles = [
  "AGENTS.md",
  "CLAUDE.md",
  "GEMINI.md",
  "docs/ai/PROJECT_BRIEF.md",
  "docs/ai/CURRENT_STATE.md",
  "docs/ai/FEATURES.md",
  "docs/ai/ARCHITECTURE.md",
  "docs/ai/COMMANDS.md",
  "docs/ai/RULES.md",
  "docs/ai/KNOWN_ISSUES.md",
  "docs/ai/TASK_LOG.md",
  "docs/ai/DECISIONS.md",
  "docs/ai/SECURITY.md",
  "docs/ai/TESTING.md",
  "docs/ai/DEVELOPMENT_WORKFLOW.md"
];
const optionalFiles = [
  ".claude/skills/ai-memory-maintainer/SKILL.md",
  ".agents/skills/ai-memory-maintainer/SKILL.md",
  ".gemini/commands/ai-memory.toml"
];
const placeholderValues = new Set([
  "",
  "...",
  "todo",
  "tbd",
  "changeme",
  "change_me",
  "redacted",
  "example",
  "example_value",
  "your_value",
  "your-token",
  "your_token",
  "your-password",
  "your_password",
  "not_set"
]);
let failed = false;

function fail(message) {
  console.error("ERROR: " + message);
  failed = true;
}

function warn(message) {
  console.warn("WARN: " + message);
}

function ok(message) {
  console.log("OK: " + message);
}

function fullPath(file) {
  return path.join(root, file);
}

function exists(file) {
  return fs.existsSync(fullPath(file));
}

function read(file) {
  return fs.readFileSync(fullPath(file), "utf8");
}

function isPlaceholderValue(value) {
  const normalized = value.trim().replace(/^['"]|['"]$/g, "").toLowerCase();
  return (
    placeholderValues.has(normalized) ||
    normalized.startsWith("<") ||
    normalized.startsWith("your_") ||
    normalized.startsWith("example_") ||
    normalized.includes("redacted") ||
    normalized.includes("placeholder")
  );
}

function findSecretLikeLines(content) {
  const hits = [];
  const lines = content.split(/\r?\n/);
  const assignment = /\b(api[_-]?key|token|password|secret|cst|x-security-token)\b\s*[:=]\s*([^\s#]+)/i;

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    if (/-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----/i.test(line)) {
      hits.push({ line: index + 1, type: "Private key" });
      continue;
    }

    const match = line.match(assignment);
    if (!match) continue;

    const value = match[2] || "";
    if (!isPlaceholderValue(value) && value.length >= 8) {
      hits.push({ line: index + 1, type: match[1] });
    }
  }

  return hits;
}

for (const file of requiredFiles) {
  if (!exists(file)) {
    fail("Missing required memory file: " + file);
    continue;
  }

  const content = read(file);
  if (!content.trim()) fail("Empty memory file: " + file);

  for (const hit of findSecretLikeLines(content)) {
    fail("Possible secret-like value in " + file + " line " + hit.line + " (" + hit.type + ")");
  }
}

if (exists("CLAUDE.md") && !read("CLAUDE.md").includes("AGENTS.md")) {
  fail("CLAUDE.md should reference AGENTS.md");
}
if (exists("GEMINI.md") && !read("GEMINI.md").includes("AGENTS.md")) {
  fail("GEMINI.md should reference AGENTS.md");
}
if (exists("AGENTS.md") && !read("AGENTS.md").includes("docs/ai/")) {
  fail("AGENTS.md should point agents to docs/ai/");
}

for (const file of optionalFiles) {
  if (!exists(file)) warn(file + " is missing");
}

if (!failed) ok("AI memory files passed required checks.");
process.exit(failed ? 1 : 0);
