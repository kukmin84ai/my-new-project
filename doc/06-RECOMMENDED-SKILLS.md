# 추천 스킬 카탈로그

> 작성 관점: 팀 리드
> 최종 업데이트: 2026-02-13

## 1. 우선순위 매트릭스

스킬을 **영향도(Impact)**와 **구현 난이도(Effort)**로 분류합니다.

```
높은 영향도 │ verify-naming    │ verify-security
            │ verify-structure │ verify-perf
            │ (Quick Wins)     │ (Strategic)
            │─────────────────│─────────────────
            │ verify-todos     │ verify-architecture
            │ verify-imports   │ verify-data-flow
낮은 영향도 │ (Fill-ins)       │ (Defer)
            └─────────────────┴─────────────────
              낮은 난이도         높은 난이도
```

## 2. Phase 1 — 즉시 필요 (Quick Wins)

### verify-naming

**목적:** 파일, 변수, 함수, 컴포넌트의 명명 규칙 준수 확인

**검증 항목:**
- 파일명: kebab-case (컴포넌트는 PascalCase)
- 함수명: camelCase
- 상수: UPPER_SNAKE_CASE
- 타입/인터페이스: PascalCase

**구현 방법:** glob 패턴 + grep으로 파일명 검사, 파일 내부 export 패턴 검사

**난이도:** 낮음 — 순수 패턴 매칭
**가치:** 높음 — 코드베이스 일관성의 기초

---

### verify-structure

**목적:** 프로젝트 디렉토리 구조와 파일 배치 규칙 준수 확인

**검증 항목:**
- 필수 디렉토리 존재 여부
- 파일이 올바른 디렉토리에 위치하는지
- index 파일의 export 패턴
- 순환 의존성 징후

**구현 방법:** glob으로 디렉토리 구조 확인, grep으로 import 패턴 분석

**난이도:** 낮음
**가치:** 높음 — 새 파일 추가 시 즉시 가이드

---

### verify-todos

**목적:** TODO/FIXME/HACK 주석의 형식과 추적 가능성 확인

**검증 항목:**
- TODO에 담당자가 표기되어 있는지: `// TODO(@username): description`
- FIXME에 이슈 번호가 있는지: `// FIXME(#123): description`
- HACK이 사유와 함께 작성되었는지
- 오래된 TODO 감지 (git blame으로 3개월 이상)

**구현 방법:** grep으로 패턴 매칭, git blame으로 날짜 확인

**난이도:** 낮음
**가치:** 중 — 기술 부채 가시화

## 3. Phase 2 — 도메인별 심화

### verify-api-contracts

**목적:** API 엔드포인트의 구조적 일관성 확인

**검증 항목:**
- 모든 엔드포인트에 타입이 정의된 요청/응답 스키마가 있는지
- 에러 응답이 공통 포맷을 따르는지
- HTTP 메서드와 명명이 RESTful 규칙을 따르는지
- 인증/인가 미들웨어 적용 여부

**난이도:** 중
**가치:** 높음 — API 품질의 핵심

---

### verify-test-patterns

**목적:** 테스트 코드의 품질과 커버리지 패턴 확인

**검증 항목:**
- 새로 추가된 소스 파일에 대응하는 테스트 파일이 있는지
- 테스트 파일이 올바른 describe/it 구조를 따르는지
- mock이 적절히 정리(cleanup)되는지
- 스냅샷 테스트가 과도하게 사용되지 않는지

**난이도:** 중
**가치:** 높음 — 테스트 품질 유지

---

### verify-type-safety

**목적:** TypeScript 타입 안전성 관행 준수 확인

**검증 항목:**
- `any` 타입 사용 금지 (허용 목록 제외)
- `as` 타입 단언 최소화
- 함수 반환 타입 명시
- 제네릭의 적절한 사용

**난이도:** 중
**가치:** 중-높음 — TypeScript 프로젝트의 핵심

## 4. Phase 3 — 전략적 스킬

### verify-security

**목적:** 보안 관련 코딩 관행 준수 확인

**검증 항목:**
- 하드코딩된 비밀번호/토큰/키 감지
- SQL 인젝션 취약 패턴 감지
- XSS 취약 패턴 감지
- 의존성의 알려진 취약점 확인

**난이도:** 높음 — 거짓양성 관리 필요
**가치:** 매우 높음 — 보안 사고 예방

---

### verify-performance

**목적:** 성능 안티패턴 감지

**검증 항목:**
- N+1 쿼리 패턴 감지
- 불필요한 리렌더링 유발 패턴 (React)
- 대용량 번들 import (lodash 전체 import 등)
- 메모리 누수 패턴 (이벤트 리스너 미해제 등)

**난이도:** 높음 — 맥락 의존적
**가치:** 높음 — 프로덕션 안정성

## 5. 비검증(Non-verify) 스킬 추천

### generate-component

**목적:** 프로젝트 규칙에 맞는 컴포넌트 보일러플레이트 생성

**워크플로우:**
1. 컴포넌트 이름과 유형(page/layout/widget) 입력
2. 프로젝트의 컴포넌트 패턴을 분석하여 템플릿 생성
3. 파일 생성: 컴포넌트, 스타일, 테스트, 스토리

**가치:** 일관된 컴포넌트 구조 + 개발 속도 향상

---

### generate-test

**목적:** 기존 코드에 대한 테스트 파일 자동 생성

**워크플로우:**
1. 대상 소스 파일 분석
2. export된 함수/클래스 목록 추출
3. 각 함수에 대한 기본 테스트 케이스 생성
4. edge case 제안

---

### analyze-deps

**목적:** 의존성 분석 및 업데이트 가이드

**워크플로우:**
1. package.json / requirements.txt 파일 분석
2. 사용하지 않는 의존성 감지
3. 보안 취약점이 있는 버전 확인
4. 업데이트 우선순위 및 호환성 리포트 생성

---

### document-decisions

**목적:** 아키텍처 결정 기록(ADR) 자동 생성

**워크플로우:**
1. 최근 변경사항 분석
2. 구조적 변경이 감지되면 ADR 템플릿 제안
3. 컨텍스트, 결정, 결과를 구조화하여 기록
4. doc/decisions/ 디렉토리에 저장

## 6. 도입 로드맵

```
Week 1-2:  verify-naming + verify-structure + verify-todos
           (기초 위생, 팀 적응)

Week 3-4:  verify-api-contracts + verify-test-patterns
           (도메인별 심화, 백엔드/QA 참여)

Week 5-6:  verify-type-safety + generate-component
           (타입 안전성 + 생산성 도구)

Week 7-8:  verify-security + analyze-deps
           (보안 + 의존성 관리)

Month 3:   verify-performance + document-decisions
           (성능 + 문서화 자동화)

Month 4+:  팀 피드백 기반 커스텀 스킬 추가
           (자체 진화 단계)
```

## 7. 스킬 조합 전략

개별 스킬의 가치를 넘어, **조합**에서 시너지가 발생합니다:

```
verify-api-contracts + verify-test-patterns
→ "API 변경 시 테스트도 함께 변경되었는가?" 교차 검증

verify-naming + verify-structure
→ "파일명이 규칙에 맞고, 올바른 디렉토리에 있는가?" 이중 검증

generate-component + verify-naming + verify-structure
→ "생성된 컴포넌트가 모든 규칙을 자동으로 만족" 제로 위반 보장
```

## 8. 커스텀 스킬 아이디어 발굴법

팀 고유의 스킬이 필요할 때 아이디어를 찾는 방법:

1. **PR 코멘트 마이닝:** 최근 50개 PR의 리뷰 코멘트에서 반복 패턴 추출
2. **버그 사후 분석:** "이 규칙이 있었다면 이 버그는 없었을 것" 분석
3. **온보딩 질문 수집:** 새 팀원이 자주 묻는 "이거 어떻게 해야 해?" 모음
4. **기술 부채 감사:** TODO/FIXME 클러스터 분석으로 관리 필요 영역 발견
5. **인시던트 리뷰:** 프로덕션 이슈의 근본 원인에서 예방 가능한 패턴 식별
