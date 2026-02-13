# 코드 리뷰 팀 템플릿

## 사용 시점
- PR 머지 전 다각도 리뷰가 필요할 때
- 중요한 변경사항(보안, 인프라, 성능)을 포함한 PR

## 프롬프트 예시

```
Create an agent team to review [PR/변경사항 설명].

Spawn 3 reviewers:
1. **security-reviewer**: Focus on security implications.
   - Check for hardcoded secrets, injection vulnerabilities, auth bypasses
   - Review input validation and sanitization
   - Check dependency vulnerabilities
   - Severity rating: Critical / High / Medium / Low

2. **performance-reviewer**: Check performance impact.
   - Identify N+1 queries, unnecessary re-renders, large bundle imports
   - Check for memory leaks (event listeners, subscriptions)
   - Review database query efficiency
   - Flag any O(n²) or worse algorithms

3. **quality-reviewer**: Validate code quality and test coverage.
   - Check naming conventions and code organization
   - Verify test coverage for new code paths
   - Review error handling completeness
   - Check type safety (no `any`, proper generics)

Have them each review independently and report findings.
Then have them challenge each other's findings — a finding
that two reviewers agree on gets elevated priority.

Synthesize into a final review report with:
- Blocking issues (must fix before merge)
- Suggestions (recommended but not blocking)
- Positive observations (good patterns found)
```

## 리뷰 리포트 포맷

```markdown
## Code Review Report

### Blocking Issues
| # | Reviewer | File:Line | Severity | Issue | Fix |
|---|---------|-----------|----------|-------|-----|

### Suggestions
| # | Reviewer | File:Line | Category | Suggestion |
|---|---------|-----------|----------|------------|

### Positive Observations
- [reviewer]: [observation]

### Cross-Review Consensus
- Issues confirmed by 2+ reviewers: [list]
```
