# 새 스킬 생성 가이드

> 작성 관점: 개발자
> 최종 업데이트: 2026-02-13

## 1. 스킬을 만들기 전에 자문하기

새 스킬을 만들기 전에 아래 체크리스트를 통과해야 합니다:

```
□ 이 규칙이 2번 이상 위반된 적이 있는가?
  → 한 번은 실수, 두 번은 패턴

□ 기존 도구(ESLint, TypeScript, etc.)로 잡을 수 없는가?
  → 이미 잡을 수 있다면 스킬이 아닌 린터 설정을 추가

□ 3개 이상의 파일에 적용되는 규칙인가?
  → 단일 파일 규칙은 해당 파일에 주석으로 충분

□ 팀원 과반이 이 규칙의 필요성에 동의하는가?
  → 합의 없는 규칙은 마찰만 생성

□ 자동 검증이 가능한가? (grep, glob, 파일 존재 확인 등)
  → "코드가 깔끔한지 확인" 같은 주관적 기준은 스킬화 불가
```

## 2. 스킬 설계 프로세스

### Phase 1: 규칙 수집 (30분)

실제 코드에서 규칙을 추출합니다:

```bash
# 1. 최근 PR 리뷰 코멘트에서 반복되는 지적 사항 수집
# 2. 팀 채널에서 "이렇게 하면 안 돼" 류의 메시지 수집
# 3. 버그 트래커에서 "패턴 위반으로 인한 버그" 수집
```

**출력물:** 규칙 목록 (5-10개)

### Phase 2: 규칙 그룹화 (15분)

관련 규칙을 도메인별로 묶습니다:

```
API 관련:
  - 모든 엔드포인트에 인증 필요
  - 응답 타입은 공통 인터페이스 사용
  - 에러는 AppError 클래스로 래핑

UI 관련:
  - 직접 DOM 접근 금지
  - 인라인 스타일 금지
  - 접근성 속성 필수
```

**원칙:** 하나의 스킬 = 하나의 도메인. "verify-everything"은 나쁜 스킬입니다.

### Phase 3: 검증 방법 설계 (30분)

각 규칙에 대해 구체적인 검증 명령을 설계합니다:

```markdown
규칙: "모든 API 엔드포인트에 인증 미들웨어가 있어야 한다"

검증 방법:
  도구: Grep
  패턴: "router\.(get|post|put|delete|patch)\("
  대상: src/api/**/*.ts

  기대:
    PASS: 각 라우터 정의 파일에 "authMiddleware" import가 존재
    FAIL: 라우터 정의가 있으나 authMiddleware가 없음

  예외:
    - src/api/health.ts (헬스체크 엔드포인트)
    - src/api/public/ 디렉토리 (공개 API)
```

### Phase 4: SKILL.md 작성 (45분)

아래 템플릿을 따라 작성합니다.

## 3. SKILL.md 템플릿

```markdown
---
name: verify-<domain>
description: <한 줄 설명>. Use after <트리거 조건>.
disable-model-invocation: true
argument-hint: "[optional: specific check name]"
---

# <Domain> Verification

## Purpose

Verifies <domain> compliance by checking:

1. **<카테고리 1>** — <설명>
2. **<카테고리 2>** — <설명>
3. **<카테고리 3>** — <설명>

## When to Run

- After modifying files in `<관련 디렉토리>`
- Before creating PRs that include <도메인> changes
- When <특정 이벤트 발생>

## Related Files

| File | Purpose |
|------|---------|
| `<실제 경로>` | <역할> |
| `<실제 경로>` | <역할> |

## Workflow

### Check 1: <체크 이름>

**File:** `<대상 파일 또는 패턴>`

**Check:** <무엇을 확인하는지>

```bash
<실행할 명령어>
```

**PASS:** <통과 조건>
**FAIL:** <실패 조건>
**Fix:** <수정 방법>

### Check 2: <체크 이름>

(같은 구조 반복)

## Output Format

```markdown
| # | Check | File | Status | Details |
|---|-------|------|--------|---------|
| 1 | <체크명> | <파일> | PASS/FAIL | <상세> |
```

## Exceptions

The following are **NOT violations**:

1. **<예외 1>** — <이유>
2. **<예외 2>** — <이유>
3. **<예외 3>** — <이유>
```

## 4. 실전 예제: verify-api-auth 만들기

### 완성된 스킬 예시

```markdown
---
name: verify-api-auth
description: Verifies all API endpoints have proper authentication. Use after modifying API routes.
disable-model-invocation: true
argument-hint: "[optional: specific route file]"
---

# API Authentication Verification

## Purpose

Ensures API security by verifying:

1. **Auth Middleware** — All route handlers use authentication middleware
2. **Role Guards** — Protected routes specify required roles
3. **Public Routes** — Only explicitly allowed routes skip authentication

## When to Run

- After adding or modifying API route files
- Before PRs that touch `src/api/` directory
- When authentication logic changes

## Related Files

| File | Purpose |
|------|---------|
| `src/api/routes/*.ts` | Route definitions |
| `src/middleware/auth.ts` | Auth middleware implementation |
| `src/api/public.routes.ts` | Explicitly public routes |

## Workflow

### Check 1: Auth middleware import

**File:** `src/api/routes/*.ts`

**Check:** Every route file imports the auth middleware.

```bash
# Find route files without auth import
for f in $(glob "src/api/routes/*.ts"); do
  grep -L "authMiddleware\|authenticate\|requireAuth" "$f"
done
```

**PASS:** All route files have auth middleware import
**FAIL:** Route file exists without auth import
**Fix:** Add `import { authMiddleware } from '@/middleware/auth'`

### Check 2: Middleware usage in route chain

**File:** Each route file from Check 1

**Check:** Route definitions include auth middleware in the chain.

```bash
grep -n "router\.\(get\|post\|put\|delete\)" <file> |
  grep -v "authMiddleware\|authenticate\|requireAuth"
```

**PASS:** Every route definition includes auth middleware
**FAIL:** Route definition without auth in the middleware chain
**Fix:** Add `authMiddleware` before the handler:
`router.get('/path', authMiddleware, handler)`

## Exceptions

The following are **NOT violations**:

1. **Health check endpoint** — `GET /health` and `GET /ready` do not need auth
2. **Public routes file** — Routes in `src/api/public.routes.ts` are intentionally public
3. **Webhook receivers** — Routes in `src/api/webhooks/` use signature verification instead
```

## 5. 스킬 작성 후 체크리스트

```
□ frontmatter의 name이 verify-* 패턴인가?
□ Purpose에 2개 이상의 검증 카테고리가 있는가?
□ Related Files의 모든 경로가 실제 존재하는가?
□ Workflow의 모든 명령어가 실행 가능한가?
□ 각 Check에 PASS/FAIL/Fix가 모두 있는가?
□ Exceptions에 2개 이상의 예외가 있는가?
□ manage-skills의 Registered Skills 테이블에 등록했는가?
□ verify-implementation의 Target Skills 테이블에 등록했는가?
□ CLAUDE.md의 Skills 테이블에 등록했는가?
```

## 6. 스킬 품질 등급

| 등급 | 기준 | 결과 |
|------|------|------|
| A | 모든 체크가 결정적 (grep/glob 기반) | 매번 동일한 결과 |
| B | 대부분 결정적, 일부 AI 판단 포함 | 95% 일관성 |
| C | AI 판단 비중 높음 | 80% 일관성 |
| D | 대부분 AI 판단 | 가이드라인 수준, 검증보다는 제안 |

**목표:** 가능하면 A-B 등급 스킬을 만드세요.

## 7. verify가 아닌 스킬 만들기

검증 외에도 다양한 패턴의 스킬이 가능합니다:

| 패턴 | 접두어 | 예시 |
|------|-------|------|
| 검증 | verify-* | verify-api, verify-types |
| 생성 | generate-* | generate-component, generate-test |
| 변환 | transform-* | transform-legacy, transform-format |
| 분석 | analyze-* | analyze-deps, analyze-performance |
| 문서화 | document-* | document-api, document-decisions |

각 패턴은 고유한 워크플로우 구조를 가지지만, SKILL.md의 기본 골격(frontmatter, Purpose, Workflow, Exceptions)은 동일합니다.

## 8. /manage-skills로 스킬 생성하기

직접 SKILL.md를 작성하는 대신, `/manage-skills`를 사용하면 자동으로:

1. 변경된 파일을 분석하여 누락된 스킬 영역을 감지
2. 스킬 이름을 제안하고 사용자 확인
3. SKILL.md를 생성하고 Related Files에 실제 경로를 채움
4. 3개 관련 파일을 동시에 업데이트

**추천 워크플로우:**

```
코드 작성 완료
    ↓
/manage-skills 실행
    ↓
"verify-<suggested> 스킬을 생성할까요?" → Yes
    ↓
생성된 SKILL.md 리뷰
    ↓
필요시 수동으로 Check 추가/수정
    ↓
/verify-implementation으로 테스트
```
