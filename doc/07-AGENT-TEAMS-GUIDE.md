# Agent Teams 운용 가이드

> 작성 관점: DevOps / 팀 운영
> 최종 업데이트: 2026-02-14

## 1. Agent Teams란

Claude Code Agent Teams는 **여러 Claude 인스턴스가 하나의 팀으로 협업**하는 실험적 기능입니다. 하나의 세션이 팀 리더(Lead)가 되어 작업을 분배하고, 각 팀원(Teammate)은 독립적인 컨텍스트 윈도우에서 병렬로 작업합니다.

기존 서브에이전트(subagent)와의 핵심 차이: 서브에이전트는 결과만 보고하지만, 팀원들은 **서로 직접 대화하고 도전**할 수 있습니다.

## 2. 이 프로젝트의 설정 상태

### 활성화 설정

`.claude/settings.local.json`:

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  },
  "teammateMode": "in-process"
}
```

### 표시 모드: in-process

- 모든 팀원이 하나의 터미널에서 실행됩니다
- **Shift+Up/Down**: 팀원 간 전환
- **Enter**: 선택된 팀원의 세션 보기
- **Escape**: 현재 팀원의 턴 중단
- **Ctrl+T**: 공유 태스크 목록 토글
- **Shift+Tab**: delegate mode 전환 (리더가 직접 구현하지 않게 함)

## 3. 팀 시나리오 템플릿

`.claude/teams/` 디렉토리에 5개의 재사용 가능한 템플릿이 준비되어 있습니다:

### 3.1 풀스택 개발 (`fullstack-dev.md`)

```
팀 구성: backend-dev + frontend-dev + test-engineer
적합한 상황: 새 기능을 여러 레이어에 걸쳐 구현
핵심 원칙: API contracts를 먼저 정의 → 병렬 구현 → 통합 테스트
```

**사용법:**
```
.claude/teams/fullstack-dev.md의 프롬프트를 복사하여
[기능명] 부분을 실제 기능으로 교체 후 Lead에게 전달
```

### 3.2 코드 리뷰 (`code-review.md`)

```
팀 구성: security-reviewer + performance-reviewer + quality-reviewer
적합한 상황: PR 머지 전 다각도 검증
핵심 원칙: 독립 리뷰 → 교차 검증 → 합의된 이슈 우선순위 상향
```

### 3.3 디버깅 (`debugging.md`)

```
팀 구성: hypothesis-data + hypothesis-logic + hypothesis-infra
         + hypothesis-regression + devils-advocate
적합한 상황: 원인 불명의 버그 조사
핵심 원칙: 복수 가설 병렬 탐색 → 상호 반박 → 살아남은 가설이 근본 원인
```

### 3.4 리서치 & 설계 (`research-design.md`)

```
팀 구성: architect + researcher + critic
적합한 상황: 아키텍처 결정, 기술 스택 선정, 마이그레이션 전략
핵심 원칙: 탐색 + 조사 → 비판적 검토 → 수정 → ADR 생성
```

### 3.5 스킬 부트스트랩 (`skill-bootstrap.md`)

```
팀 구성: scanner-structure + scanner-patterns + scanner-config + synthesizer
적합한 상황: 기존 프로젝트에 스킬 시스템 최초 도입
핵심 원칙: 3방향 병렬 스캔 → 규칙 통합 → 우선순위 정렬 → 시드 스킬 생성
```

## 4. 실전 운용 절차

### Step 1: 시나리오 선택

작업의 성격에 맞는 템플릿을 선택합니다.

```
"새 기능 개발" → fullstack-dev.md
"PR 리뷰 요청" → code-review.md
"버그가 재현되는데 원인 모름" → debugging.md
"새 라이브러리 도입 검토" → research-design.md
"이 프로젝트에 스킬 처음 적용" → skill-bootstrap.md
```

### Step 2: 프롬프트 커스터마이즈

템플릿의 `[placeholder]`를 실제 값으로 교체합니다. 중요한 것은 **각 팀원에게 충분한 컨텍스트**를 주는 것입니다:

```
나쁜 예: "프론트엔드 개발해줘"
좋은 예: "src/components/에 사용자 프로필 편집 폼을 구현해줘.
         기존 src/components/UserCard.tsx 패턴을 따르고,
         src/hooks/useUserData.ts 훅을 사용해.
         Tailwind CSS로 스타일링하고 반응형 지원 필요."
```

### Step 3: 팀 실행

Claude Code 터미널에서 프롬프트를 입력합니다. Lead가 자동으로:
1. 팀을 생성하고
2. 태스크 리스트를 만들고
3. 팀원을 스폰하고
4. 작업을 배분합니다

### Step 4: 모니터링

- **Shift+Up/Down**으로 각 팀원의 진행 상황 확인
- **Ctrl+T**로 태스크 목록 확인
- 필요시 특정 팀원에게 직접 메시지 전송

### Step 5: 결과 수합

모든 팀원이 완료되면 Lead가 결과를 종합합니다.
팀 정리: `Clean up the team`

## 5. 스킬 시스템과의 통합

Agent Teams와 기존 스킬 시스템은 이렇게 연결됩니다:

```
Agent Teams (팀 협업)
    │
    ├─ 개발 완료 후 → /verify-implementation (품질 검증)
    │
    ├─ 검증 실패 시 → debugging 팀으로 원인 조사
    │
    ├─ 코드 변경 후 → /manage-skills (스킬 갱신)
    │
    └─ 새 프로젝트 → skill-bootstrap 팀으로 초기화
```

**추천 워크플로우:**

```
1. skill-bootstrap 팀으로 시드 스킬 생성 (최초 1회)
2. fullstack-dev 팀으로 기능 개발
3. /verify-implementation으로 검증
4. code-review 팀으로 PR 리뷰
5. /manage-skills로 스킬 업데이트
6. (버그 발생 시) debugging 팀으로 조사
7. (아키텍처 변경 시) research-design 팀으로 설계
```

## 6. 비용 및 성능 고려사항

### 토큰 사용량

각 팀원이 독립적인 컨텍스트 윈도우를 가지므로, 토큰 사용이 팀원 수에 비례하여 증가합니다.

| 시나리오 | 팀원 수 | 예상 토큰 배율 |
|---------|--------|--------------|
| 단독 세션 | 1 | 1x (기준) |
| 코드 리뷰 | 3 | ~3-4x |
| 풀스택 개발 | 3 | ~4-5x |
| 디버깅 | 5 | ~5-7x |
| 스킬 부트스트랩 | 4 | ~4-6x |

### 언제 팀을 쓰고, 언제 쓰지 않을까

**팀이 효과적인 경우:**
- 병렬 탐색이 가치 있는 작업 (리서치, 리뷰, 디버깅)
- 독립적인 파일/디렉토리에서 동시 작업 가능한 개발
- 서로 다른 관점의 교차 검증이 필요한 의사결정

**단독 세션이 나은 경우:**
- 순차적 의존성이 많은 작업
- 같은 파일을 반복 수정하는 작업
- 간단한 버그 수정이나 리팩토링
- 빠른 프로토타이핑

## 7. 트러블슈팅

### 팀원이 안 보일 때
Shift+Down을 눌러 숨겨진 팀원을 찾으세요. in-process 모드에서는 팀원이 백그라운드에서 실행 중일 수 있습니다.

### Lead가 직접 코드를 쓰기 시작할 때
`Wait for your teammates to complete their tasks before proceeding`라고 입력하거나, Shift+Tab으로 delegate mode를 활성화하세요.

### 팀원이 에러 후 멈출 때
해당 팀원을 선택하고 직접 추가 지시를 주거나, Lead에게 새 팀원을 스폰하라고 요청하세요.

### 파일 충돌 발생 시
각 팀원의 소유 디렉토리를 명확히 분리하세요. 템플릿의 "파일 소유권 분리" 표를 참고하세요.

## 8. 제한사항 (2026-02 기준)

Agent Teams는 실험적 기능이므로 알아두어야 할 제한:

- `/resume`으로 세션 복구 시 in-process 팀원은 복원되지 않음
- 한 세션에 하나의 팀만 운영 가능
- 팀원은 자신의 팀원을 스폰할 수 없음 (중첩 불가)
- 팀원의 태스크 완료 표시가 누락될 수 있어 수동 확인 필요
- 리더 역할은 변경 불가 (생성한 세션이 영구적으로 리더)
