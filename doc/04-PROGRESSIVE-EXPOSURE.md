# Progressive Exposure 전략

> 작성 관점: UX/DX(Developer Experience) 전문가
> 최종 업데이트: 2026-02-13

## 1. Progressive Exposure란

Progressive Exposure(점진적 노출)은 사용자가 **필요한 시점에 필요한 만큼의 복잡성만 접하도록** 설계하는 기법입니다. 처음에는 단순한 인터페이스를 보여주고, 사용자가 익숙해질수록 고급 기능을 노출합니다.

이 개념을 스킬 시스템에 적용하면: **팀이 처음부터 20개의 검증 규칙에 압도되지 않고, 점진적으로 품질 기준을 높여가는 전략**이 됩니다.

## 2. 3단계 노출 모델

```
┌─────────────────────────────────────────────────┐
│  Layer 3: 고급 (Expert)                          │
│  자동 스킬 생성, CI 통합, 프로젝트 간 공유        │
│                                                  │
│  ┌──────────────────────────────────────────┐    │
│  │  Layer 2: 중급 (Intermediate)             │    │
│  │  도메인별 검증, 커스텀 규칙, 팀 워크플로우  │    │
│  │                                           │    │
│  │  ┌───────────────────────────────────┐    │    │
│  │  │  Layer 1: 기본 (Beginner)          │    │    │
│  │  │  /verify-implementation 실행       │    │    │
│  │  │  기본 검증 결과 확인               │    │    │
│  │  └───────────────────────────────────┘    │    │
│  └──────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
```

## 3. Layer 1 — 기본 (첫 주)

### 목표
팀원이 `/verify-implementation` 명령 하나만 기억하면 됩니다.

### 제공하는 것
- 사전 정의된 2-3개의 기본 verify 스킬
- 간결한 요약 리포트 (PASS/FAIL 테이블)
- 원클릭 자동 수정

### 숨기는 것
- 스킬 내부 구조 (SKILL.md 포맷)
- manage-skills의 존재
- 스킬 생성/수정 방법

### 구현 방법

**CLAUDE.md에 간결한 가이드 추가:**

```markdown
## Quick Start

코드 작성 후, PR 전에 실행하세요:
/verify-implementation

문제가 발견되면 "Fix All"을 선택하세요.
```

**첫 주에 제공할 스킬 예시:**

| 스킬 | 검증 내용 | 이유 |
|------|---------|------|
| verify-file-structure | 파일/폴더 명명 규칙 | 가장 직관적이고 비침습적 |
| verify-imports | 금지된 import 패턴 | 즉시 이해 가능한 규칙 |
| verify-todos | TODO 주석의 형식 준수 | 팀 협업의 기본 |

## 4. Layer 2 — 중급 (2-4주차)

### 목표
팀원이 자신의 도메인에 맞는 스킬의 의미를 이해하고, 예외를 인지합니다.

### 새로 노출하는 것
- 개별 verify 스킬 직접 실행 (`/verify-api`, `/verify-types` 등)
- Exceptions 섹션의 존재 (거짓양성 이해)
- 스킬 리포트의 상세 내용 (파일 경로, 라인 번호)

### 여전히 숨기는 것
- 스킬 생성 방법
- manage-skills의 내부 동작
- 메타 스킬 패턴

### 구현 방법

**도메인별 스킬 추가:**

```
Week 2: verify-api-contracts    (백엔드 팀)
Week 3: verify-component-rules  (프론트엔드 팀)
Week 4: verify-test-patterns    (QA 팀)
```

**팀별 맞춤 가이드:**

```markdown
## Backend Team Guide

API 작업 후 실행하세요:
/verify-api-contracts

이 스킬은 다음을 확인합니다:
- 모든 엔드포인트에 인증 미들웨어 존재 여부
- 응답 타입의 일관성
- 에러 처리 패턴

예외: internal/ 디렉토리의 헬스체크 엔드포인트는 인증 불필요
```

## 5. Layer 3 — 고급 (1개월+)

### 목표
팀원이 스킬을 직접 생성하고, 시스템의 전체 구조를 이해합니다.

### 새로 노출하는 것
- `/manage-skills` 명령
- SKILL.md 템플릿과 작성법
- 스킬 간 관계 (오케스트레이터 패턴)
- 이 doc/ 문서 전체

### 구현 방법

**스킬 생성 워크숍:**

```
1. manage-skills 실행하여 갭 분석
2. 팀 토론: 어떤 규칙을 스킬화할 것인가
3. 페어 작성: 시니어 + 주니어가 함께 첫 스킬 작성
4. 리뷰 & 시범 운영
```

## 6. Progressive Exposure를 극대화하는 7가지 기법

### 기법 1: 디폴트 프리셋 제공

팀이 처음 시스템을 접할 때, **빈 상태가 아닌 동작하는 상태**로 시작해야 합니다.

```
초기 셋업 시 자동 포함:
├── verify-naming     (파일/변수 명명 규칙)
├── verify-structure  (디렉토리 구조 규칙)
└── verify-basics     (기본 코드 위생)
```

### 기법 2: 경고 모드 (Warning-Only Phase)

새 스킬을 도입할 때 바로 블로킹하지 않고, **2주간 경고만 표시**합니다.

```markdown
## Output Mode

### Warning Phase (default for new skills)
Status: ⚠️ WARNING
Behavior: Report issues but do not block

### Enforcement Phase (after team review)
Status: ❌ FAIL
Behavior: Report issues and recommend blocking
```

이렇게 하면 팀이 규칙에 적응할 시간을 가집니다.

### 기법 3: 맥락 인식 실행

변경된 파일의 도메인에 따라 **관련 스킬만 실행**합니다.

```
수정한 파일: src/api/users.ts
→ verify-api-contracts만 실행 (verify-ui-rules는 스킵)

수정한 파일: src/components/Button.tsx
→ verify-component-rules만 실행 (verify-api-contracts는 스킵)
```

manage-skills의 파일-스킬 매핑이 이를 가능하게 합니다.

### 기법 4: 단계적 엄격도

같은 스킬이라도 시간이 지나며 기준을 높입니다:

```
Month 1: verify-test-coverage → 커버리지 50% 이상
Month 2: verify-test-coverage → 커버리지 60% 이상
Month 3: verify-test-coverage → 커버리지 70% 이상
```

스킬의 PASS/FAIL 기준에 날짜 기반 임계값을 설정합니다.

### 기법 5: 성과 가시화

월간 "스킬 대시보드"를 생성하여 팀에 공유합니다:

```markdown
## Monthly Skill Report - January 2026

| 스킬 | 실행 횟수 | 초기 FAIL 비율 | 현재 FAIL 비율 | 개선도 |
|------|---------|-------------|-------------|-------|
| verify-api | 47 | 34% | 8% | ↓ 76% |
| verify-types | 31 | 22% | 5% | ↓ 77% |
```

팀이 "스킬 덕분에 좋아졌다"를 체감해야 지속적으로 사용합니다.

### 기법 6: 발견 가능한 힌트

AI가 코드를 작성하거나 리뷰할 때, 관련 스킬의 존재를 **자연스럽게 언급**합니다.

CLAUDE.md에 추가:

```markdown
## AI Behavior Hints

When writing API endpoints, remind about /verify-api-contracts.
When creating new components, suggest running /verify-component-rules.
```

### 기법 7: 실패에서 배우기

스킬이 잡은 문제를 **학습 자료**로 전환합니다:

```markdown
## Common Mistakes Caught by Skills

### verify-api: Missing auth middleware
- Found 12 times in January
- Root cause: copy-paste from internal endpoints
- Prevention: template with auth pre-included

### verify-types: any type usage
- Found 8 times in January
- Root cause: quick prototyping that wasn't cleaned up
- Prevention: IDE snippet with proper typing
```

## 7. 반(反)패턴: 피해야 할 것들

### 빅뱅 도입
**나쁜 예:** "오늘부터 15개 스킬을 모두 적용합니다"
**결과:** 팀 반발, 스킬 시스템 자체에 대한 부정적 인식

### 설명 없는 강제
**나쁜 예:** FAIL만 표시하고 "왜"를 설명하지 않음
**결과:** "이거 왜 실패야?" → 좌절 → 스킬 비활성화

### 예외 없는 완벽주의
**나쁜 예:** Exceptions 섹션 없이 100% 엄격 적용
**결과:** 거짓양성으로 인한 경고 피로(Alert Fatigue)

### 기술 부채로의 전락
**나쁜 예:** 스킬을 만들고 업데이트하지 않음
**결과:** 코드는 진화했는데 스킬은 옛날 규칙을 강제 → 신뢰 상실
