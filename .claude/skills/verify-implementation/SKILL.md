---
name: verify-implementation
description: Sequentially executes all verify skills in the project to generate an integrated verification report. Use after implementing features, before PRs, and during code reviews.
disable-model-invocation: true
argument-hint: "[optional: specific verify skill name]"
---

# Implementation Verification

## Purpose

Performs integrated verification by sequentially executing all `verify-*` skills registered in the project:

- Executes checks defined in each skill's Workflow
- References each skill's Exceptions to prevent false positives
- Suggests fixes for discovered issues
- Applies fixes and re-verifies after user approval

## When to Run

- After implementing a new feature
- Before creating a Pull Request
- During code reviews
- When auditing codebase compliance with rules

## Target Skills for Execution

List of verification skills to be executed sequentially by this skill. `/manage-skills` automatically updates this list when creating/deleting skills.

(No verification skills registered yet)

<!-- When skills are added, register in the following format:
| # | Skill | Description |
|---|-------|-------------|
| 1 | `verify-example` | Example verification description |
-->

## Workflow

### Step 1: Introduction

Check the skills listed in the **Target Skills for Execution** section above.

If an optional argument is provided, filter to that skill only.

**If 0 skills are registered:**

```markdown
## Implementation Verification

No verification skills found. Run `/manage-skills` to create verification skills appropriate for your project.
```

In this case, terminate the workflow.

**If 1 or more skills are registered:**

Display the contents of the target skills table:

```markdown
## Implementation Verification

The following verification skills will be executed sequentially:

| # | Skill | Description |
|---|-------|-------------|
| 1 | verify-<name1> | <description1> |
| 2 | verify-<name2> | <description2> |

Starting verification...
```

### Step 2: Sequential Execution

For each skill listed in the **Target Skills for Execution** table, perform the following:

#### 2a. Read Skill SKILL.md

Read `.claude/skills/verify-<name>/SKILL.md` for that skill and parse the following sections:

- **Workflow** — Check steps and detection commands to execute
- **Exceptions** — Patterns not considered violations
- **Related Files** — List of files to be checked

#### 2b. Execute Checks

Execute each check defined in the Workflow section in order:

1. Use the tools specified in the check (Grep, Glob, Read, Bash) to detect patterns
2. Compare detected results against that skill's PASS/FAIL criteria
3. Exempt patterns that match the Exceptions section
4. If FAIL, record the issue:
   - File path and line number
   - Problem description
   - Fix recommendations (including code examples)

#### 2c. Record Results per Skill

After completing each skill execution, display progress:

```markdown
### verify-<name> Verification Complete

- Check items: N
- Passed: X
- Issues: Y
- Exempted: Z

[Moving to next skill...]
```

### Step 3: Integrated Report

After completing all skill executions, integrate the results into a single report:

```markdown
## Implementation Verification Report

### Summary

| Verification Skill | Status | Issue Count | Details |
|--------------------|--------|-------------|---------|
| verify-<name1> | PASS / X issues | N | Details... |
| verify-<name2> | PASS / X issues | N | Details... |

**Total Issues Found: X**
```

**When all verifications pass:**

```markdown
All verifications passed!

The implementation complies with all project rules:

- verify-<name1>: <summary of what passed>
- verify-<name2>: <summary of what passed>

Ready for code review.
```

**When issues are found:**

List each issue with file path, problem description, and fix recommendations:

```markdown
### Issues Found

| # | Skill | File | Problem | How to Fix |
|---|-------|------|---------|------------|
| 1 | verify-<name1> | `path/to/file.ts:42` | Problem description | Fix code example |
| 2 | verify-<name2> | `path/to/file.tsx:15` | Problem description | Fix code example |
```

### Step 4: Confirm User Action

If issues are found, use `AskUserQuestion` to confirm with the user:

```markdown
---

### Fix Options

**X issues were found. How would you like to proceed?**

1. **Fix All** - Automatically apply all recommended fixes
2. **Fix Individually** - Review and apply each fix one by one
3. **Skip** - Exit without changes
```

### Step 5: Apply Fixes

Apply fixes according to user selection.

**When "Fix All" is selected:**

Apply all fixes in order and display progress:

```markdown
## Applying Fixes...

- [1/X] verify-<name1>: `path/to/file.ts` fixed
- [2/X] verify-<name2>: `path/to/file.tsx` fixed

X fixes completed.
```

**When "Fix Individually" is selected:**

For each issue, show the fix content and confirm approval using `AskUserQuestion`.

### Step 6: Re-verification After Fixes

If fixes were applied, re-run only the skills that had issues to compare Before/After:

```markdown
## Re-verification After Fixes

Re-running skills that had issues...

| Verification Skill | Before Fix | After Fix |
|--------------------|------------|-----------|
| verify-<name1> | X issues | PASS |
| verify-<name2> | Y issues | PASS |

All verifications passed!
```

**If issues still remain:**

```markdown
### Remaining Issues

| # | Skill | File | Problem |
|---|-------|------|---------|
| 1 | verify-<name> | `path/to/file.ts:42` | Cannot auto-fix — manual review required |

After manually resolving, run `/verify-implementation` again.
```

---

## Exceptions

The following are **NOT problems**:

1. **Projects with no registered skills** — Display guidance message, not an error, and terminate
2. **Skills' own exceptions** — Patterns defined in each verify skill's Exceptions section are not reported as issues
3. **verify-implementation itself** — Does not include itself in the target skills list
4. **manage-skills** — Not included in execution targets as it doesn't start with `verify-`

## Related Files

| File | Purpose |
|------|---------|
| `.claude/skills/manage-skills/SKILL.md` | Skill maintenance (manages this file's target skills list) |
| `CLAUDE.md` | Project guidelines |
