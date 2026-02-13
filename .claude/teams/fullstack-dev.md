# 풀스택 개발 팀 템플릿

## 사용 시점
- 새 기능을 프론트엔드/백엔드/테스트 레이어에 걸쳐 구현할 때
- 각 레이어가 독립적으로 작업 가능한 인터페이스가 정의되어 있을 때

## 프롬프트 예시

```
Create an agent team for fullstack development of [기능명].

Spawn 3 teammates:
1. **backend-dev**: Implement the API layer.
   - Own files: src/api/, src/services/, src/models/
   - Define API contracts (request/response types) FIRST before implementation
   - Require plan approval before making changes

2. **frontend-dev**: Implement the UI layer.
   - Own files: src/components/, src/pages/, src/hooks/
   - Use the API contracts defined by backend-dev
   - Require plan approval before making changes

3. **test-engineer**: Write tests for both layers.
   - Own files: tests/, __tests__/, *.test.ts, *.spec.ts
   - Wait for backend-dev and frontend-dev to define interfaces
   - Write unit tests + integration tests

Task dependencies:
- backend-dev defines API contracts → frontend-dev and test-engineer can start
- backend-dev and frontend-dev complete implementation → test-engineer writes integration tests

Use delegate mode. Wait for all teammates to complete before synthesizing.
```

## 파일 소유권 분리

| Teammate | 소유 디렉토리/파일 | 절대 건드리지 않는 영역 |
|----------|------------------|---------------------|
| backend-dev | src/api/, src/services/, src/models/ | src/components/, tests/ |
| frontend-dev | src/components/, src/pages/, src/hooks/ | src/api/, tests/ |
| test-engineer | tests/, __tests__/, *.test.*, *.spec.* | src/api/, src/components/ |

## 작업 흐름

```
Lead (delegate mode)
  │
  ├─ Task 1: Define API contracts (→ backend-dev)
  │     dependency: none
  │
  ├─ Task 2: Implement API endpoints (→ backend-dev)
  │     dependency: Task 1
  │
  ├─ Task 3: Implement UI components (→ frontend-dev)
  │     dependency: Task 1
  │
  ├─ Task 4: Write unit tests (→ test-engineer)
  │     dependency: Task 1
  │
  ├─ Task 5: Write integration tests (→ test-engineer)
  │     dependency: Task 2, Task 3
  │
  └─ Task 6: Final verification (→ Lead synthesizes)
        dependency: Task 2, Task 3, Task 4, Task 5
```

## 완료 조건
- [ ] API contracts 타입 파일 생성됨
- [ ] 모든 엔드포인트 구현 완료
- [ ] UI 컴포넌트 렌더링 확인
- [ ] 단위 테스트 통과
- [ ] 통합 테스트 통과
- [ ] `/verify-implementation` 통과
