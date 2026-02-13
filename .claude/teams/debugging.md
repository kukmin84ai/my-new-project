# 디버깅 팀 템플릿

## 사용 시점
- 원인이 불분명한 버그를 조사할 때
- 여러 가능한 원인을 병렬로 탐색해야 할 때

## 프롬프트 예시

```
Create an agent team to investigate: [버그 증상 설명]

Spawn 4-5 teammates, each investigating a different hypothesis:

1. **hypothesis-data**: The bug is caused by data issues.
   - Check data flow, transformations, and edge cases
   - Trace the data path from input to output
   - Look for null/undefined, type mismatches, encoding issues

2. **hypothesis-logic**: The bug is in the business logic.
   - Review conditional branches and state transitions
   - Check race conditions and timing issues
   - Look for off-by-one errors, boundary conditions

3. **hypothesis-infra**: The bug is infrastructure-related.
   - Check configuration, environment variables, dependencies
   - Review network calls, timeouts, retries
   - Check file system, permissions, resource limits

4. **hypothesis-regression**: The bug was introduced by a recent change.
   - Use git log and git bisect to identify suspect commits
   - Compare behavior before and after recent changes
   - Check if reverted changes fix the issue

5. **devils-advocate**: Challenge all other hypotheses.
   - Read other teammates' findings and poke holes
   - Propose alternative explanations
   - Verify that "fixes" actually address root cause, not symptoms

Have teammates communicate directly to share findings and
challenge each other's theories. The hypothesis that survives
scrutiny is most likely the root cause.
```

## 결과 포맷

```markdown
## Debugging Report

### Root Cause
[가장 유력한 원인 + 근거]

### Investigation Summary
| Hypothesis | Investigator | Verdict | Evidence |
|-----------|-------------|---------|----------|
| Data issue | hypothesis-data | Ruled out | [why] |
| Logic error | hypothesis-logic | **Confirmed** | [evidence] |
| Infra issue | hypothesis-infra | Ruled out | [why] |
| Regression | hypothesis-regression | Partial | [details] |

### Recommended Fix
[구체적인 수정 방안]

### Prevention
[재발 방지를 위한 verify 스킬 제안]
```
