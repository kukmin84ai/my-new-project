# kimoring-ai-skills

AI 기반 코드 검증 자동화 프레임워크. 스킬 시스템과 Agent Teams를 활용한 복합 프로젝트 운용 표준.

## Skills

Custom verification and maintenance skills are defined in `.claude/skills/`.

| Skill | Purpose |
|-------|---------|
| `verify-implementation` | Sequentially executes all verify skills in the project to generate an integrated verification report |
| `manage-skills` | Analyzes session changes, creates/updates verification skills, and manages CLAUDE.md |

## Agent Teams

이 프로젝트는 Claude Code Agent Teams(실험적 기능)를 활용합니다.

### 활성화

`settings.local.json`에 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS: "1"` 설정 완료.
표시 모드: `in-process` (Shift+Up/Down으로 팀원 전환)

### 팀 시나리오

팀 프롬프트 템플릿은 `.claude/teams/` 디렉토리에 정의되어 있습니다.

| 시나리오 | 파일 | 용도 |
|---------|------|------|
| 풀스택 개발 | `fullstack-dev.md` | 프론트/백엔드/테스트 병렬 개발 |
| 코드 리뷰 | `code-review.md` | 보안/성능/품질 다각도 리뷰 |
| 디버깅 | `debugging.md` | 복수 가설 병렬 조사 |
| 리서치 & 설계 | `research-design.md` | 아키텍처 탐색 + 기술 조사 + 비판적 검토 |
| 스킬 부트스트랩 | `skill-bootstrap.md` | 기존 프로젝트에 스킬 시스템 초기화 |

### 팀 운용 규칙

1. Lead는 **delegate mode**(Shift+Tab)로 운영하여 직접 구현하지 않음
2. Teammate에게는 반드시 **충분한 컨텍스트**를 spawn prompt에 포함
3. 파일 충돌 방지: 각 teammate가 담당하는 파일/디렉토리를 명시적으로 분리
4. 복잡한 작업은 **plan approval** 요구 후 구현 진행

## Documentation

프로젝트 문서는 `doc/` 디렉토리에 정리되어 있습니다.

| 문서 | 내용 |
|------|------|
| `doc/00-INDEX.md` | 문서 인덱스 |
| `doc/01-CURRENT-STATE.md` | 현재 상태 진단 |
| `doc/02-SKILL-ARCHITECTURE.md` | 스킬 아키텍처 해설 |
| `doc/03-PROJECT-OPERATIONS.md` | 프로젝트 운용 장단점 |
| `doc/04-PROGRESSIVE-EXPOSURE.md` | Progressive Exposure 전략 |
| `doc/05-SKILL-CREATION-GUIDE.md` | 스킬 생성 가이드 |
| `doc/06-RECOMMENDED-SKILLS.md` | 추천 스킬 카탈로그 |
| `doc/07-AGENT-TEAMS-GUIDE.md` | Agent Teams 운용 가이드 |
