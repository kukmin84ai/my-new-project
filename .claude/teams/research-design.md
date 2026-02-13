# 리서치 & 설계 팀 템플릿

## 사용 시점
- 새로운 아키텍처 결정이 필요할 때
- 기술 스택 선정, 마이그레이션 전략 수립
- 복잡한 기능의 설계 단계

## 프롬프트 예시

```
Create an agent team to research and design [주제].

Spawn 3 teammates:
1. **architect**: Explore architecture options.
   - Analyze current codebase structure and patterns
   - Propose 2-3 architecture approaches with trade-offs
   - Consider scalability, maintainability, team familiarity
   - Require plan approval before finalizing

2. **researcher**: Deep-dive into technical options.
   - Research libraries, frameworks, and tools for the approach
   - Compare alternatives with concrete criteria (bundle size,
     community, maintenance, compatibility)
   - Find real-world examples and case studies
   - Check for known issues and migration paths

3. **critic**: Challenge proposals and find weaknesses.
   - Review architect's proposals for hidden assumptions
   - Identify risks, edge cases, and failure modes
   - Play devil's advocate on technology choices
   - Propose risk mitigation strategies
   - Check if simpler alternatives were overlooked

Process:
1. architect and researcher work in parallel (Phase 1)
2. critic reviews both outputs and challenges (Phase 2)
3. architect revises based on criticism (Phase 3)
4. Lead synthesizes into ADR (Architecture Decision Record)

Have teammates communicate directly during Phase 2-3.
```

## ADR 출력 포맷

```markdown
## Architecture Decision Record

### Title
[결정 제목]

### Status
Proposed / Accepted / Deprecated / Superseded

### Context
[왜 이 결정이 필요한가?]

### Options Considered
| Option | Pros | Cons | Risk |
|--------|------|------|------|
| A: ... | ... | ... | ... |
| B: ... | ... | ... | ... |
| C: ... | ... | ... | ... |

### Decision
[선택한 옵션 + 이유]

### Consequences
- Positive: [기대 효과]
- Negative: [감수해야 할 단점]
- Risks: [리스크 + 완화 방안]

### Critic's Unresolved Concerns
[비판자가 제기했으나 해소되지 않은 우려사항]
```

## 팁
- architect에게 현재 코드베이스의 특정 디렉토리를 분석하도록 지시
- researcher에게 `WebSearch` 사용을 명시하면 최신 정보 반영 가능
- critic에게 "다른 두 teammate의 메시지를 읽고 반박하라"고 지시
