# Claude Instructions

Always read and follow:

@AGENTS.md
@docs/ai/README.md
@docs/ai/CURRENT_STATE.md
@docs/ai/HANDOFF.md

Use these additional files when relevant:

@docs/ai/PROJECT_CONTEXT.md
@docs/ai/ARCHITECTURE.md
@docs/ai/CODING_RULES.md
@docs/ai/TESTING.md
@docs/ai/DATABASE.md
@docs/ai/SECURITY.md

## Claude-Specific Rules

1.  **Careful Planning**: Before starting any large implementation, outline the steps and confirm with the user.
2.  **Avoid Unnecessary Rewrites**: Focus on fixing the specific issue or adding the requested feature without rewriting unrelated surrounding code.
3.  **Summarize Changes**: After every code generation, provide a clear, bulleted summary of files changed and tests that should be run.
4.  **Review Protocols**: Follow the rules in `.agents/skills/code-review/SKILL.md` when asked to perform a general code review.
