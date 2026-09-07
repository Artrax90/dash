# Project Guidelines & Rules

## Autonomy & Execution Policy
- **Absolute Full Autonomy & Zero Confirmation**: The user has granted full, unconditional permission for all actions. NEVER ask for confirmation, approval, or clarifying questions before executing commands, writing code, modifying files, building, testing, or committing. Execute everything proactively, automatically, and autonomously to complete the task.
- **Automatic Dependencies**: Always install necessary dependencies (`npm install`, `pip install`, etc.) autonomously without asking for confirmation or asking clarifying questions.
- **Full Action Autonomy**: Feel free to create, modify, build, and run code/scripts automatically to accomplish the task.
- **Safety Restriction**: NEVER delete files outside of the project workspace folder (`d:/antigravity/dash`). File deletion is strictly restricted to files within the project folder.
- **Session Continuity & Change Logging**: Maintain and update `PROGRESS.md` after every change/step with timestamps, detailed log of modifications, changed files, and current project status so work can resume seamlessly if a session disconnects.
- **Always Push to GitHub**: ALWAYS push all committed changes directly to GitHub (`git push origin main`) at the end of every task or step. Never leave commits unpushed.

## Core Engineering Methodology (Superpowers)
Strictly follow the core methodologies from the installed `superpowers` skills suite:

### 1. Test-Driven Development (TDD)
- **The Iron Law**: NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST.
- Never write implementation code before writing a failing test demonstrating the desired behavior or bug.
- Always run and observe the test failure (RED) before writing minimal code to make it pass (GREEN), then refactor (REFACTOR).
- Any code written prior to tests must be discarded.

### 2. Systematic Debugging
- **The Iron Law**: NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST.
- Before proposing or implementing fixes:
  1. Read full error messages, logs, and stack traces.
  2. Reproduce the problem reliably.
  3. Gather diagnostic evidence across component boundaries and trace data flow to the origin of bad values.
  4. Form a specific hypothesis and test it minimally.
- If 3 or more fix attempts fail, stop and re-examine the architecture.

### 3. Verification Before Completion
- **The Iron Law**: NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE.
- Never claim a task, bugfix, or feature is complete, working, or fixed without running the actual verification command (tests, builds, status probes) and inspecting the exact output.
- Always provide evidence before assertions.

