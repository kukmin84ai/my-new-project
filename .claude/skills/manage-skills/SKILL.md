---
name: manage-skills
description: Analyzes session changes to detect missing verification skills. Dynamically explores existing skills, creates new skills or updates existing ones, and manages CLAUDE.md.
disable-model-invocation: true
argument-hint: "[optional: specific skill name or area to focus on]"
---

# Session-Based Skill Maintenance

## Purpose

Detects and corrects drift in verification skills by analyzing changes in the current session:

1. **Missing Coverage** — Changed files not referenced by any verify skill
2. **Invalid References** — Skills referencing deleted or moved files
3. **Missing Checks** — New patterns/rules not covered by existing checks
4. **Outdated Values** — Configuration values or detection commands that no longer match

## When to Run

- After implementing features that introduce new patterns or rules
- When you want to check consistency after modifying existing verify skills
- To confirm that verify skills cover changed areas before a PR
- When verification runs miss expected issues
- To periodically align skills with codebase changes

## Registered Verification Skills

List of verification skills currently registered in the project. Update this list when creating/deleting new skills.

(No verification skills registered yet)

<!-- When skills are added, register in the following format:
| Skill | Description | Coverage File Patterns |
|-------|-------------|------------------------|
| `verify-example` | Example verification | `src/example/**/*.ts` |
-->

## Workflow

### Step 1: Analyze Session Changes

Collect all files changed in the current session:

```bash
# Uncommitted changes
git diff HEAD --name-only

# Commits on current branch (if branched from main)
git log --oneline main..HEAD 2>/dev/null

# All changes since branching from main
git diff main...HEAD --name-only 2>/dev/null
```

Merge into a deduplicated list. If a skill name or area is specified as an optional argument, filter to related files only.

**Display:** Group files by top-level directory (first 1-2 path segments):

```markdown
## Session Changes Detected

**N files changed in this session:**

| Directory | Files |
|-----------|-------|
| src/components | `Button.tsx`, `Modal.tsx` |
| src/server | `router.ts`, `handler.ts` |
| tests | `api.test.ts` |
| (root) | `package.json`, `.eslintrc.js` |
```

### Step 2: Map Registered Skills to Changed Files

Build file-to-skill mapping by referencing skills listed in the **Registered Verification Skills** section above.

#### Sub-step 2a: Check Registered Skills

Read each skill's name and coverage file patterns from the **Registered Verification Skills** table.

If 0 skills are registered, jump directly to Step 4 (CREATE vs UPDATE Decision). All changed files are treated as "UNCOVERED".

If 1 or more skills are registered, read each skill's `.claude/skills/verify-<name>/SKILL.md` and extract additional file path patterns from:

1. **Related Files** section — Parse table to extract file paths and glob patterns
2. **Workflow** section — Extract file paths from grep/glob/read commands

#### Sub-step 2b: Match Changed Files to Skills

For each changed file collected in Step 1, compare against registered skills' patterns. A file matches a skill when:

- It matches that skill's coverage file pattern
- It's located within a directory referenced by that skill
- It matches the regex/string patterns used in that skill's detection commands

#### Sub-step 2c: Display Mapping

```markdown
### File → Skill Mapping

| Skill | Trigger Files (Changed Files) | Action |
|-------|-------------------------------|--------|
| verify-api | `router.ts`, `handler.ts` | CHECK |
| verify-ui | `Button.tsx` | CHECK |
| (no skill) | `package.json`, `.eslintrc.js` | UNCOVERED |
```

### Step 3: Analyze Coverage Gaps in Affected Skills

For each AFFECTED skill (skills with matched changed files), read the entire SKILL.md and check for:

1. **Missing File References** — Are there changed files related to this skill's domain not listed in the Related Files section?
2. **Outdated Detection Commands** — Do the skill's grep/glob patterns still match the current file structure? Test by running sample commands.
3. **Uncovered New Patterns** — Read changed files and identify new rules, configurations, or patterns that the skill doesn't check. Check for:
   - New type definitions, enum variants, or exported symbols
   - New registrations or configurations
   - New file naming or directory conventions
4. **Stale References to Deleted Files** — Are there files in the skill's Related Files that no longer exist in the codebase?
5. **Changed Values** — Have specific values (identifiers, configuration keys, type names) that the skill checks been changed in modified files?

Record each gap found:

```markdown
| Skill | Gap Type | Details |
|-------|----------|---------|
| verify-api | Missing File | `src/server/newHandler.ts` not in Related Files |
| verify-ui | New Pattern | New component uses unchecked rule |
| verify-test | Outdated Value | Test runner pattern in config file changed |
```

### Step 4: CREATE vs UPDATE Decision

Apply the following decision tree:

```
For each uncovered file group:
    IF files are related to an existing skill's domain:
        → Decision: UPDATE existing skill (expand coverage)
    ELSE IF 3+ related files share common rules/patterns:
        → Decision: CREATE new verify skill
    ELSE:
        → Mark as "exempt" (skill not needed)
```

Present results to the user:

```markdown
### Suggested Actions

**Decision: UPDATE existing skills** (N)
- `verify-api` — Add 2 missing file references, update detection patterns
- `verify-test` — Update detection commands for new config patterns

**Decision: CREATE new skills** (M)
- New skill needed — cover <pattern description> (X uncovered files)

**No action needed:**
- `package.json` — Configuration file, exempt
- `README.md` — Documentation, exempt
```

Use `AskUserQuestion` to confirm:
- Which existing skills to update
- Whether to create suggested new skills
- Option to skip all

### Step 5: Update Existing Skills

For each skill the user approved for update, read the current SKILL.md and apply targeted edits:

**Rules:**
- **Add/modify only** — Never remove existing checks that still work
- Add new file paths to **Related Files** table
- Add new detection commands for patterns found in changed files
- Add new workflow steps or sub-steps for uncovered rules
- Remove references to files confirmed deleted from codebase
- Update changed specific values (identifiers, config keys, type names)

**Example — Adding file to Related Files:**

```markdown
## Related Files

| File | Purpose |
|------|---------|
| ... existing entries ... |
| `src/server/newHandler.ts` | New request handler with validation |
```

**Example — Adding detection command:**

````markdown
### Step N: Verify New Pattern

**File:** `path/to/file.ts`

**Check:** Description of what to verify.

```bash
grep -n "pattern" path/to/file.ts
```

**Violation:** What it looks like when incorrect.
````

### Step 6: Create New Skills

**Important:** When creating a new skill, you must confirm the skill name with the user.

For each skill to be created:

1. **Explore** — Read related changed files to deeply understand the patterns

2. **Confirm skill name with user** — Use `AskUserQuestion`:

   Present the pattern/domain the skill will cover and ask the user to provide or confirm a name.

   **Naming conventions:**
   - Name must start with `verify-` (e.g., `verify-auth`, `verify-api`, `verify-caching`)
   - If user provides name without `verify-` prefix, automatically prepend it and inform the user
   - Use kebab-case (e.g., `verify-error-handling`, not `verify_error_handling`)

3. **Create** — Generate `.claude/skills/verify-<name>/SKILL.md` according to the following template:

```yaml
---
name: verify-<name>
description: <one-line description>. Use after <trigger condition>.
---
```

Required sections:
- **Purpose** — 2-5 numbered verification categories
- **When to Run** — 3-5 trigger conditions
- **Related Files** — Table of actual file paths in codebase (verified with `ls`, no placeholders)
- **Workflow** — Check steps, each specifying:
  - Tools to use (Grep, Glob, Read, Bash)
  - Exact file paths or patterns
  - PASS/FAIL criteria
  - How to fix on failure
- **Output Format** — Markdown table for results
- **Exceptions** — At least 2-3 realistic "not a violation" cases

4. **Update related skill files** — After creating a new skill, you must update the following 3 files:

   **4a. Update this file itself (`manage-skills/SKILL.md`):**
   - Add new skill row to table in **Registered Verification Skills** section
   - When adding first skill, remove "(No verification skills registered yet)" text and HTML comment, replace with table
   - Format: `| verify-<name> | <description> | <coverage file patterns> |`

   **4b. Update `verify-implementation/SKILL.md`:**
   - Add new skill row to table in **Target Skills for Execution** section
   - When adding first skill, remove "(No verification skills registered yet)" text and HTML comment, replace with table
   - Format: `| <number> | verify-<name> | <description> |`

   **4c. Update `CLAUDE.md`:**
   - Add new skill row to `## Skills` table
   - Format: `| verify-<name> | <one-line description> |`

### Step 7: Validation

After all edits:

1. Re-read all modified SKILL.md files
2. Verify markdown formatting is correct (no unclosed code blocks, consistent table columns)
3. Check for broken file references — verify file existence for each path in Related Files:

```bash
ls <file-path> 2>/dev/null || echo "MISSING: <file-path>"
```

4. Dry-run one detection command from each updated skill to validate syntax
5. Confirm that **Registered Verification Skills** table and **Target Skills for Execution** table are synchronized

### Step 8: Summary Report

Display final report:

```markdown
## Session Skill Maintenance Report

### Changed Files Analyzed: N

### Skills Updated: X
- `verify-<name>`: Added N new checks, updated Related Files
- `verify-<name>`: Updated detection commands for new patterns

### Skills Created: Y
- `verify-<name>`: Covers <pattern>

### Related Files Updated:
- `manage-skills/SKILL.md`: Updated Registered Verification Skills table
- `verify-implementation/SKILL.md`: Updated Target Skills for Execution table
- `CLAUDE.md`: Updated Skills table

### Unaffected Skills: Z
- (No related changes)

### Uncovered Changes (no applicable skill):
- `path/to/file` — Exempt (reason)
```

---

## Quality Criteria for Created/Updated Skills

All created or updated skills must have:

- **Actual file paths from codebase** (verified with `ls`), not placeholders
- **Working detection commands** — Use real grep/glob patterns that match current files
- **PASS/FAIL criteria** — Clear conditions for pass and fail for each check
- **At least 2-3 realistic exceptions** — Explanation of what's not a violation
- **Consistent formatting** — Same as existing skills (frontmatter, section headers, table structure)

---

## Related Files

| File | Purpose |
|------|---------|
| `.claude/skills/verify-implementation/SKILL.md` | Integrated verification skill (this skill manages its target list) |
| `.claude/skills/manage-skills/SKILL.md` | This file itself (manages registered verification skills list) |
| `CLAUDE.md` | Project guidelines (this skill manages Skills section) |

## 예외사항

다음은 **문제가 아닙니다**:

1. **Lock 파일 및 생성된 파일** — `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `Cargo.lock`, 자동 생성된 마이그레이션 파일, 빌드 출력물은 스킬 커버리지가 불필요
2. **일회성 설정 변경** — `package.json`/`Cargo.toml`의 버전 범프, 린터/포매터 설정의 사소한 변경은 새 스킬이 불필요
3. **문서 파일** — `README.md`, `CHANGELOG.md`, `LICENSE` 등은 검증이 필요한 코드 패턴이 아님
4. **테스트 픽스처 파일** — 테스트 픽스처로 사용되는 디렉토리의 파일(예: `fixtures/`, `__fixtures__/`, `test-data/`)은 프로덕션 코드가 아님
5. **영향받지 않은 스킬** — UNAFFECTED로 표시된 스킬은 검토 불필요; 대부분의 세션에서 대부분의 스킬이 이에 해당
6. **CLAUDE.md 자체** — CLAUDE.md의 변경은 문서 업데이트이며, 검증이 필요한 코드 패턴이 아님
7. **벤더/서드파티 코드** — `vendor/`, `node_modules/` 또는 복사된 라이브러리 디렉토리의 파일은 외부 규칙을 따름
8. **CI/CD 설정** — `.github/`, `.gitlab-ci.yml`, `Dockerfile` 등은 인프라이며, 검증 스킬이 필요한 애플리케이션 패턴이 아님
