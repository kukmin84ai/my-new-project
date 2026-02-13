# 스킬 부트스트랩 팀 템플릿

## 사용 시점
- 기존 프로젝트에 스킬 시스템을 처음 도입할 때
- 프로젝트 전체를 스캔하여 어떤 verify 스킬이 필요한지 파악할 때

## 프롬프트 예시

```
Create an agent team to bootstrap the skill system for this project.

Spawn 4 teammates:
1. **scanner-structure**: Analyze project structure and conventions.
   - Map directory structure and file organization patterns
   - Identify naming conventions (files, variables, exports)
   - Document implicit rules that aren't enforced by linters
   - Output: list of structural rules that should be verify skills

2. **scanner-patterns**: Analyze code patterns and anti-patterns.
   - Read key source files in each domain (api, ui, services, etc.)
   - Identify repeated patterns (error handling, auth, logging, etc.)
   - Find inconsistencies where patterns are sometimes followed, sometimes not
   - Output: list of code patterns that should be verify skills

3. **scanner-config**: Analyze existing tooling and configuration.
   - Review ESLint, TypeScript, test configs
   - Identify gaps: what rules exist but aren't enforced?
   - What project-specific rules can't be expressed in existing tools?
   - Output: list of config-gap rules that should be verify skills

4. **synthesizer**: Combine findings into prioritized skill plan.
   - Wait for all scanners to report findings
   - Deduplicate and group related rules
   - Prioritize by: frequency of violation × impact of violation
   - Create a phased rollout plan (Week 1-2, Week 3-4, Month 2+)
   - Draft the first 3 SKILL.md files ready for review

Process:
1. 3 scanners work in parallel (Phase 1)
2. synthesizer reads all findings (Phase 2)
3. synthesizer creates prioritized plan + draft skills (Phase 3)
4. Lead presents plan to user for approval

Require plan approval for synthesizer before creating files.
```

## 출력 포맷

```markdown
## Skill Bootstrap Report

### Project Profile
- Language: [lang]
- Framework: [framework]
- Test runner: [runner]
- Existing linting: [tools]

### Discovered Rules (Prioritized)

| Priority | Rule | Source | Frequency | Suggested Skill |
|----------|------|--------|-----------|-----------------|
| P1 | Auth on all endpoints | scanner-patterns | 12 violations | verify-api-auth |
| P1 | No any type | scanner-config | 8 violations | verify-type-safety |
| P2 | Test file for each source | scanner-structure | 15 gaps | verify-test-coverage |
| ... | ... | ... | ... | ... |

### Phased Rollout
Week 1-2: [skill-1], [skill-2], [skill-3]
Week 3-4: [skill-4], [skill-5]
Month 2+: [skill-6], [skill-7], [skill-8]

### Draft Skills Ready for Review
1. verify-[name-1] → .claude/skills/verify-[name-1]/SKILL.md
2. verify-[name-2] → .claude/skills/verify-[name-2]/SKILL.md
3. verify-[name-3] → .claude/skills/verify-[name-3]/SKILL.md
```

## manage-skills와의 관계

이 팀은 **초기 부트스트래핑 전용**입니다. 한 번 시드 스킬이 생성되면, 이후 유지보수는 `/manage-skills`가 담당합니다.

```
skill-bootstrap 팀 (1회성)
    ↓ 시드 스킬 3개 생성
manage-skills (지속적)
    ↓ 코드 변경 시마다 스킬 갱신
verify-implementation (지속적)
    ↓ PR 전마다 검증 실행
```
