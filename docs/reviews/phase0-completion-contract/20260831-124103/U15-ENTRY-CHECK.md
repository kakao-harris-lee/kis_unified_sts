# U15-ENTRY-CHECK — D0A-FIRST 실전 진입 transcript (스탬프 20260831-124103)

이 문서는 **U-15-e 결속 transcript** 다.  §12.3 단계 8 의 유일한 규정 착수
형식(U-15-f-1 · 3단 가드)으로 **D0A-FIRST**(`config/tos_completion.yaml` 도입
커밋 — §12.1 명명·대리 아님)를 개시하는 실전 기록이며, 계약이 강제하는
흐름 순서 **H → d → T**(§12.3.4-G G6: transcript 는 커밋 «전» 저작 측
scratchpad 에서 확정되어 SHA256 이 뜨고, d 이후 이 추적 경로로 착지한다)를
따른다.  발행 후 이 파일은 **불변**이다(U-15-e (4d)) — 후속 관측(가드 rc·
산물 생성 실측)은 같은 스탬프의 **U15-ENTRY-CHECK-ADDENDUM.md** 로 발행한다.

## (3) 실행 시점 결속

- 실행 시점 HEAD: `e2048397eb7497c9a45287f2a3532f2e38619150`
  (산출 원문은 아래 run 1 을 여는 리터럴 라인이다 — U-15-e (4c)·(4c-2).
  이 파일에서 그 여는 라인은 **정확히 1회** 나타나며, 따라서 이 transcript 의
  run 은 하나뿐이고 **k = 1** 이다)
- 실행 시각: 2026-08-31T03:41:03Z (UTC) = 2026-08-31 12:41:03 (KST)
- 실행 위치: 저장소 루트 `/Users/harris/Development/private/kis_unified_sts`
  (worktree 아님) · 브랜치 `mission-critical-trading-operating-system`
- 좌변 하니스의 권위 입력 동결은 하니스 R-0 자신이 검사한다(통과 —
  아래 출력 원문).  이 transcript 는 확정 시점까지 scratchpad 에만 있으므로
  `$STAMPS` 동결을 깨지 않는다(G6 흐름 순서 주의의 이행).

## (1)(2) 명령 원문과 출력 원문 — 가드 좌·중변 사전 실행 (H 단계)

명령 원문 (생략 없음 · 저장소 루트에서 실행):

```sh
bash tools/tos_entry_harness.sh && bash tools/u17-verify.sh; printf 'two_arm_rc=%d\n' $?
```

출력 원문 (stdout+stderr 병합 · 요약·발췌 없음 — U-3 전문 노출 규율.
첫 줄이 run 1 을 여는 라인이고, 상태 라인은 run 안에 정확히 1개다):

```text
R-0 head=e2048397eb7497c9a45287f2a3532f2e38619150
R-3 verdict=docs/reviews/phase0-completion-contract/20260830-223406
d0a_entry_state=ENTRY_OK
reason=R-0~R-7 전부 기대와 일치
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /Users/harris/Development/private/kis_unified_sts/.git/info/grafts=no · is_shallow=false · entry HEAD=e2048397eb7497c9a45287f2a3532f2e38619150
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /Users/harris/Development/private/kis_unified_sts /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.P4cUYfVd5Z/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=e2048397eb7497c9a45287f2a3532f2e38619150 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.P4cUYfVd5Z/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 2396개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.1cvQcRsOIa
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=live rc=0
  | github.com
  |   ✓ Logged in to github.com account kakao-harris-lee (keyring)
  |   - Active account: true
  |   - Git operations protocol: https
  |   - Token: gho_************************************
  |   - Token scopes: 'gist', 'read:org', 'repo', 'workflow'
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.P4cUYfVd5Z/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.P4cUYfVd5Z/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/Users/harris/Development/private/kis_unified_sts/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-31T03:43:32Z  http=200  x-github-request-id=5C14:1BF29E:1E7B22:295935:6A94F863
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-31T03:43:32Z  http=200  x-github-request-id=BB17:335A1F:1DA67A:2885BF:6A94F863  (.default_branch=main)
U17-A0W repos/kakao-harris-lee/kis_unified_sts/actions/workflows/tos-gate.yml  utc=2026-08-31T03:43:32Z  http=200  x-github-request-id=38C0:338BD1:1EA1B0:298235:6A94F864
  | {"id":343700405,"node_id":"W_kwDOQ9V_3c4UfHO1","name":"tos-gate","path":".github/workflows/tos-gate.yml","state":"active","created_at":"2026-08-27T20:03:34.000+09:00","updated_at":"2026-08-28T21:33:25.000+09:00","url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/actions/workflows/343700405","html_url":"https://github.com/kakao-harris-lee/kis_unified_sts/blob/main/.github/workflows/tos-gate.yml","badge_url":"https://github.com/kakao-harris-lee/kis_unified_sts/workflows/tos-gate/badge.svg"}
U17-0w 핀 workflow_id=343700405 (state=active · repos/kakao-harris-lee/kis_unified_sts/actions/workflows/tos-gate.yml 의 .id · 구조 파생 · ①-R 전 결속 · 폴백 없음)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=∅(선택 키 부재 → 핀 유일 소스) target_branch=∅(선택 키 부재 → default_branch 유일 소스) host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-31T03:43:33Z  http=200  x-github-request-id=F230:339B3F:1D7B33:2859D7:6A94F865
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-31T03:43:34Z  http=200  x-github-request-id=30F4:33A29E:1E5E84:293E85:6A94F865
  | [{"type":"required_status_checks","parameters":{"strict_required_status_checks_policy":true,"do_not_enforce_on_create":false,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]},"ruleset_source_type":"Repository","ruleset_source":"kakao-harris-lee/kis_unified_sts","ruleset_id":21886181},{"type":"pull_request","parameters":{"required_approving_review_count":0,"dismiss_stale_reviews_on_push":true,"required_reviewers":[],"require_code_owner_review":false,"require_last_push_approval":false,"required_review_thread_resolution":false,"require_extra_approval_for_unattributed_changes":true,"allowed_merge_methods":["merge","squash","rebase"]},"ruleset_source_type":"Repository","ruleset_source":"kakao-harris-lee/kis_unified_sts","ruleset_id":21886181},{"type":"non_fast_forward","ruleset_source_type":"Repository","ruleset_source":"kakao-harris-lee/kis_unified_sts","ruleset_id":21886181},{"type":"deletion","ruleset_source_type":"Repository","ruleset_source":"kakao-harris-lee/kis_unified_sts","ruleset_id":21886181}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-31T03:43:34Z  http=200  x-github-request-id=38A6:338D71:1E4318:292434:6A94F866
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"},{"id":21886181,"name":"tos-gate","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"active","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgFN9OU","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/21886181"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/21886181"}},"created_at":"2026-08-31T08:51:12.269+09:00","updated_at":"2026-08-31T08:54:29.714+09:00"}]
U17-DELTA repos/kakao-harris-lee/kis_unified_sts/rules/branches/main?per_page=100  utc=2026-08-31T03:43:35Z  http=200  x-github-request-id=D7FE:29630F:1E6D87:294CF6:6A94F867
  | [{"type":"required_status_checks","parameters":{"strict_required_status_checks_policy":true,"do_not_enforce_on_create":false,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]},"ruleset_source_type":"Repository","ruleset_source":"kakao-harris-lee/kis_unified_sts","ruleset_id":21886181},{"type":"pull_request","parameters":{"required_approving_review_count":0,"dismiss_stale_reviews_on_push":true,"required_reviewers":[],"require_code_owner_review":false,"require_last_push_approval":false,"required_review_thread_resolution":false,"require_extra_approval_for_unattributed_changes":true,"allowed_merge_methods":["merge","squash","rebase"]},"ruleset_source_type":"Repository","ruleset_source":"kakao-harris-lee/kis_unified_sts","ruleset_id":21886181},{"type":"non_fast_forward","ruleset_source_type":"Repository","ruleset_source":"kakao-harris-lee/kis_unified_sts","ruleset_id":21886181},{"type":"deletion","ruleset_source_type":"Repository","ruleset_source":"kakao-harris-lee/kis_unified_sts","ruleset_id":21886181}]
U17-B2s --slurp repos/kakao-harris-lee/kis_unified_sts/rules/branches/main?per_page=100  utc=2026-08-31T03:43:36Z  status=200  (본문 = 페이지 배열의 배열)
  | [[{"type":"required_status_checks","parameters":{"strict_required_status_checks_policy":true,"do_not_enforce_on_create":false,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]},"ruleset_source_type":"Repository","ruleset_source":"kakao-harris-lee/kis_unified_sts","ruleset_id":21886181},{"type":"pull_request","parameters":{"required_approving_review_count":0,"dismiss_stale_reviews_on_push":true,"required_reviewers":[],"require_code_owner_review":false,"require_last_push_approval":false,"required_review_thread_resolution":false,"require_extra_approval_for_unattributed_changes":true,"allowed_merge_methods":["merge","squash","rebase"]},"ruleset_source_type":"Repository","ruleset_source":"kakao-harris-lee/kis_unified_sts","ruleset_id":21886181},{"type":"non_fast_forward","ruleset_source_type":"Repository","ruleset_source":"kakao-harris-lee/kis_unified_sts","ruleset_id":21886181},{"type":"deletion","ruleset_source_type":"Repository","ruleset_source":"kakao-harris-lee/kis_unified_sts","ruleset_id":21886181}]]U17-DELTAt repos/kakao-harris-lee/kis_unified_sts/rules/branches/main?per_page=100&page=2  utc=2026-08-31T03:43:36Z  http=200  x-github-request-id=E715:337685:1E9A37:297AF8:6A94F868
  | []
  | PL-R [gen-2 READER] 관측면 = «--paginate --slurp 본문» · 페이지 수 N=1 · 페이지별 원소 수 [4] · 수집 원소 = concat = 4개 · total_count=None
  | PL-R 미소비 인자(gen-2): merged=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.1cvQcRsOIa/repos_kakao-harris-lee_kis_unified_sts_rules_branches_main_per_page_100.body · hdr=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.1cvQcRsOIa/repos_kakao-harris-lee_kis_unified_sts_rules_branches_main_per_page_100.hdr · mode=loose(무동작) — 이 판의 limb ② 피연산자는 «본문»이다
  | PL-1 limb ① N/A — 이 엔드포인트는 `total_count` 를 주지 않는다
  | PL-2 limb ② [gen-2] 피연산자 = «본문» · 종단 프로브 ?page=<N+1> (N=1 → page=2) · 본문 = []
  | PL-2 종단 프로브 «정확히 []» 확인 → limb ② PASS — **본문만으로 재판정 가능**하고 헤더에 무의존이다(헤더는 보조이고 판정 피연산자가 아니다·(5))
  | PL-2m mode=loose 는 이 판에서 «무동작» — 피연산자가 관측 가능해져 두 독법이 갈리던 자리가 사라졌다
  | PL-2r 미결(정직 등재) — ① `?page=<N+1>` 이 «없는 페이지»에 `[]` 를 준다는 것은 «실측»이고 문서 규정은 확인되지 않았다 · ② 페이지 «사이»의 삽입·삭제로 원소가 경계를 넘는 것은 limb ① 이 잡고 이 limb 은 잡지 못한다(문서 침묵으로부터의 추론 · 잔여)
  | PL-C 수집(평탄화) 원소 4개 → /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.1cvQcRsOIa/repos_kakao-harris-lee_kis_unified_sts_rules_branches_main_per_page_100.delta.collected.json  (하류 술어는 이 결과를 소비한다)
  | RESULT=PAGES_OK|limb ①=N/A · limb ②=PASS(mode=loose) · 수집 4 · total_count=None
U17-DELTA repos/kakao-harris-lee/kis_unified_sts/rulesets?per_page=100  utc=2026-08-31T03:43:37Z  http=200  x-github-request-id=66BD:3386D0:1EE359:29C319:6A94F869
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"},{"id":21886181,"name":"tos-gate","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"active","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgFN9OU","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/21886181"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/21886181"}},"created_at":"2026-08-31T08:51:12.269+09:00","updated_at":"2026-08-31T08:54:29.714+09:00"}]
U17-B2s --slurp repos/kakao-harris-lee/kis_unified_sts/rulesets?per_page=100  utc=2026-08-31T03:43:37Z  status=200  (본문 = 페이지 배열의 배열)
  | [[{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"},{"id":21886181,"name":"tos-gate","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"active","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgFN9OU","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/21886181"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/21886181"}},"created_at":"2026-08-31T08:51:12.269+09:00","updated_at":"2026-08-31T08:54:29.714+09:00"}]]U17-DELTAt repos/kakao-harris-lee/kis_unified_sts/rulesets?per_page=100&page=2  utc=2026-08-31T03:43:38Z  http=200  x-github-request-id=CD4D:1C6149:1E51ED:293126:6A94F86A
  | []
  | PL-R [gen-2 READER] 관측면 = «--paginate --slurp 본문» · 페이지 수 N=1 · 페이지별 원소 수 [2] · 수집 원소 = concat = 2개 · total_count=None
  | PL-R 미소비 인자(gen-2): merged=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.1cvQcRsOIa/repos_kakao-harris-lee_kis_unified_sts_rulesets_per_page_100.body · hdr=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.1cvQcRsOIa/repos_kakao-harris-lee_kis_unified_sts_rulesets_per_page_100.hdr · mode=loose(무동작) — 이 판의 limb ② 피연산자는 «본문»이다
  | PL-1 limb ① N/A — 이 엔드포인트는 `total_count` 를 주지 않는다
  | PL-2 limb ② [gen-2] 피연산자 = «본문» · 종단 프로브 ?page=<N+1> (N=1 → page=2) · 본문 = []
  | PL-2 종단 프로브 «정확히 []» 확인 → limb ② PASS — **본문만으로 재판정 가능**하고 헤더에 무의존이다(헤더는 보조이고 판정 피연산자가 아니다·(5))
  | PL-2m mode=loose 는 이 판에서 «무동작» — 피연산자가 관측 가능해져 두 독법이 갈리던 자리가 사라졌다
  | PL-2r 미결(정직 등재) — ① `?page=<N+1>` 이 «없는 페이지»에 `[]` 를 준다는 것은 «실측»이고 문서 규정은 확인되지 않았다 · ② 페이지 «사이»의 삽입·삭제로 원소가 경계를 넘는 것은 limb ① 이 잡고 이 limb 은 잡지 못한다(문서 침묵으로부터의 추론 · 잔여)
  | PL-C 수집(평탄화) 원소 2개 → /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.1cvQcRsOIa/repos_kakao-harris-lee_kis_unified_sts_rulesets_per_page_100.delta.collected.json  (하류 술어는 이 결과를 소비한다)
  | RESULT=PAGES_OK|limb ①=N/A · limb ②=PASS(mode=loose) · 수집 2 · total_count=None
U17-DELTA (다) 관측(target-scope): {"rules_branches": {"observed": true, "discriminated": true, "why": "partial last page(4<100)"}, "rulesets": {"observed": true, "discriminated": true, "why": "partial last page(2<100)"}}
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-31T03:43:39Z  http=200  x-github-request-id=2A5A:337685:1E9B5E:297C63:6A94F86A
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/21886181  utc=2026-08-31T03:43:39Z  http=200  x-github-request-id=2EA5:33DD3B:1E72E4:2953D1:6A94F86B
  | {"id":21886181,"name":"tos-gate","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"active","conditions":{"ref_name":{"exclude":[],"include":["refs/heads/main"]}},"rules":[{"type":"required_status_checks","parameters":{"strict_required_status_checks_policy":true,"do_not_enforce_on_create":false,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","parameters":{"required_approving_review_count":0,"dismiss_stale_reviews_on_push":true,"required_reviewers":[],"require_code_owner_review":false,"require_last_push_approval":false,"required_review_thread_resolution":false,"require_extra_approval_for_unattributed_changes":true,"allowed_merge_methods":["merge","squash","rebase"]}},{"type":"non_fast_forward"},{"type":"deletion"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgFN9OU","created_at":"2026-08-31T08:51:12.269+09:00","updated_at":"2026-08-31T08:54:29.714+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/21886181"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/21886181"}}}
U17-α0 적용 룰셋(연속성 입력우주) = [21886181]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[17017682 21886181])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
U17-BT0 repos/kakao-harris-lee/kis_unified_sts/branches/main  utc=2026-08-31T03:43:40Z  http=200  x-github-request-id=0F25:2231BA:1DBB03:289B47:6A94F86C
  | {"name":"main","commit":{"sha":"0932645d1ba44d1067ac793780bf10ba4f41e591","node_id":"C_kwDOQ9V_3doAKDA5MzI2NDVkMWJhNDRkMTA2N2FjNzkzNzgwYmYxMGJhNGY0MWU1OTE","commit":{"author":{"name":"harris.lee","email":"harris.lee@kakaocorp.com","date":"2026-08-30T23:47:27Z"},"committer":{"name":"harris.lee","email":"harris.lee@kakaocorp.com","date":"2026-08-30T23:47:27Z"},"message":"chore(tos): U-17 예방 통제 3종 정본 재착지 — tos-gate.yml(정본 잡 템플릿 BLOB_OK)·하니스(§12.3.4-R sha 1817c9ef 일치)·u17-verify(61차 의미 정합판)\n\n운영자 지시(2026-08-31 «D0-A 잔여 블로커 해소»). 계약 §12.2 도입 순서\n이행 — 파일 3종을 target 에 «먼저» 착지하고 룰셋은 approve 취득 후\n«마지막»에 활성화한다(자기 봉쇄 회피). 착지 전 실측: HEAD 판\ntos-gate.yml = wfcanon BLOB_OK · 하니스 sha256 = 계약 결속값\n1817c9ef…cfbffb byte-일치 · u17-verify = e2048397 (61차).\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>","tree":{"sha":"6f5c958c4fd185bfcdbfadbb6da79497d2ada9e3","url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/git/trees/6f5c958c4fd185bfcdbfadbb6da79497d2ada9e3"},"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/git/commits/0932645d1ba44d1067ac793780bf10ba4f41e591","comment_count":0,"verification":{"verified":false,"reason":"unsigned","signature":null,"payload":null,"verified_at":null}},"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/commits/0932645d1ba44d1067ac793780bf10ba4f41e591","html_url":"https://github.com/kakao-harris-lee/kis_unified_sts/commit/0932645d1ba44d1067ac793780bf10ba4f41e591","comments_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/commits/0932645d1ba44d1067ac793780bf10ba4f41e591/comments","author":{"login":"kakao-harris-lee","id":130432481,"node_id":"U_kgDOB8Y94Q","avatar_url":"https://avatars.githubusercontent.com/u/130432481?v=4","gravatar_id":"","url":"https://api.github.com/users/kakao-harris-lee","html_url":"https://github.com/kakao-harris-lee","followers_url":"https://api.github.com/users/kakao-harris-lee/followers","following_url":"https://api.github.com/users/kakao-harris-lee/following{/other_user}","gists_url":"https://api.github.com/users/kakao-harris-lee/gists{/gist_id}","starred_url":"https://api.github.com/users/kakao-harris-lee/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/kakao-harris-lee/subscriptions","organizations_url":"https://api.github.com/users/kakao-harris-lee/orgs","repos_url":"https://api.github.com/users/kakao-harris-lee/repos","events_url":"https://api.github.com/users/kakao-harris-lee/events{/privacy}","received_events_url":"https://api.github.com/users/kakao-harris-lee/received_events","type":"User","user_view_type":"public","site_admin":false},"committer":{"login":"kakao-harris-lee","id":130432481,"node_id":"U_kgDOB8Y94Q","avatar_url":"https://avatars.githubusercontent.com/u/130432481?v=4","gravatar_id":"","url":"https://api.github.com/users/kakao-harris-lee","html_url":"https://github.com/kakao-harris-lee","followers_url":"https://api.github.com/users/kakao-harris-lee/followers","following_url":"https://api.github.com/users/kakao-harris-lee/following{/other_user}","gists_url":"https://api.github.com/users/kakao-harris-lee/gists{/gist_id}","starred_url":"https://api.github.com/users/kakao-harris-lee/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/kakao-harris-lee/subscriptions","organizations_url":"https://api.github.com/users/kakao-harris-lee/orgs","repos_url":"https://api.github.com/users/kakao-harris-lee/repos","events_url":"https://api.github.com/users/kakao-harris-lee/events{/privacy}","received_events_url":"https://api.github.com/users/kakao-harris-lee/received_events","type":"User","user_view_type":"public","site_admin":false},"parents":[{"sha":"b46c6a17cfd2bbcd0363749823f90461abc5bd0a","url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/commits/b46c6a17cfd2bbcd0363749823f90461abc5bd0a","html_url":"https://github.com/kakao-harris-lee/kis_unified_sts/commit/b46c6a17cfd2bbcd0363749823f90461abc5bd0a"}]},"_links":{"self":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main","html":"https://github.com/kakao-harris-lee/kis_unified_sts/tree/main"},"protected":true,"protection":{"enabled":true,"required_status_checks":{"enforcement_level":"non_admins","contexts":["test"],"checks":[{"context":"test","app_id":15368}]}},"protection_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection"}
U17-BT [M-7] target HEAD sha = 0932645d1ba44d1067ac793780bf10ba4f41e591   (계약 :5583 «verbatim 수록 필수» — 리뷰어 재조회 대조용)
U17-BT1 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=0932645d1ba44d1067ac793780bf10ba4f41e591  utc=2026-08-31T03:43:41Z  http=200  x-github-request-id=1235:33B1BA:1DDC64:28BCC7:6A94F86C
  | {"name":"tos-gate.yml","path":".github/workflows/tos-gate.yml","sha":"c610e6d8efbf832b2a3357662c5d97459ed7e7f9","size":639,"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=0932645d1ba44d1067ac793780bf10ba4f41e591","html_url":"https://github.com/kakao-harris-lee/kis_unified_sts/blob/0932645d1ba44d1067ac793780bf10ba4f41e591/.github/workflows/tos-gate.yml","git_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/git/blobs/c610e6d8efbf832b2a3357662c5d97459ed7e7f9","download_url":"https://raw.githubusercontent.com/kakao-harris-lee/kis_unified_sts/0932645d1ba44d1067ac793780bf10ba4f41e591/.github/workflows/tos-gate.yml","type":"file","content":"bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCnBlcm1pc3Npb25z\nOgogIGNvbnRlbnRzOiByZWFkCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBuYW1l\nOiB0b3MtZ2F0ZQogICAgcnVucy1vbjogdWJ1bnR1LWxhdGVzdAogICAgc3Rl\ncHM6CiAgICAgIC0gdXNlczogYWN0aW9ucy9jaGVja291dEAzZDNjNDJlNWFh\nYzViYTgwNTgyNWRhNzY0MTBjMTgxMjczYmE5MGIxCiAgICAgICAgd2l0aDoK\nICAgICAgICAgIGZldGNoLWRlcHRoOiAwCiAgICAgICAgICBwZXJzaXN0LWNy\nZWRlbnRpYWxzOiBmYWxzZQogICAgICAtIG5hbWU6ICJ0b3MtZ2F0ZTogdmVy\naWZ5IGhhcm5lc3Mgc2hhMjU2IgogICAgICAgIHJ1bjogfAogICAgICAgICAg\nc2V0IC1ldW8gcGlwZWZhaWwKICAgICAgICAgIHByaW50ZiAnJXMgIHRvb2xz\nL3Rvc19lbnRyeV9oYXJuZXNzLnNoXG4nIDE4MTdjOWVmNWQ3OTBjMTExZDQ3\nMzhiODllM2MzYWRkODBkYzJkOWY4MGY5YjhhZjdlZjU3Mzg2MzZjZmJmZmIg\nfCBzaGFzdW0gLWEgMjU2IC1jIC0KICAgICAgLSBuYW1lOiAidG9zLWdhdGU6\nIHJ1biBoYXJuZXNzIgogICAgICAgIHJ1bjogfAogICAgICAgICAgc2V0IC1l\ndW8gcGlwZWZhaWwKICAgICAgICAgIGJhc2ggdG9vbHMvdG9zX2VudHJ5X2hh\ncm5lc3Muc2gK\n","encoding":"base64","_links":{"self":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=0932645d1ba44d1067ac793780bf10ba4f41e591","git":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/git/blobs/c610e6d8efbf832b2a3357662c5d97459ed7e7f9","html":"https://github.com/kakao-harris-lee/kis_unified_sts/blob/0932645d1ba44d1067ac793780bf10ba4f41e591/.github/workflows/tos-gate.yml"}}
U17-BT1 decoded .github/workflows/tos-gate.yml@0932645d1ba44d1067ac793780bf10ba4f41e591 (target HEAD · encoding=base64 size=639):
  | name: tos-gate
  | on: [pull_request]
  | permissions:
  |   contents: read
  | jobs:
  |   tos-gate:
  |     name: tos-gate
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
  |         with:
  |           fetch-depth: 0
  |           persist-credentials: false
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 1817c9ef5d790c111d4738b89e3c3add80dc2d9f80f9b8af7ef5738636cfbffb | shasum -a 256 -c -
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  | WF-P0 파서 핀 = mikefarah v4.48.* · `yq --version` = 'yq (https://github.com/mikefarah/yq/) version v4.48.1' → 일치 True
  | WF-D0 [G3] C-1 파서 = PyYAML 6.0.3 (계약에 «버전 핀 없음» — 측정 기록이지 핀이 아니다)
  | WF-D1 [C-1] compose 전 매핑 노드 중복 키 = 0건 
  | WF-D2 [M-4] `<<` merge key = 0건 
  | WF-D2c [G4] 순환 alias(방문집합 = 노드 identity) = 0건 
  | WF-D3 [C-1 벨트] 두 파서 `.value` 키 트리 일치 = True
  | WF-C0 판정 파서 = yq -o=json · 대조 = 정규화 후 byte 비교 · 대상 = 정본 «잡 템플릿» 전체
  | WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 1817c9ef5d790c111d4738b89e3c3add80dc2d9f80f9b8af7ef5738636cfbffb | shasum -a 256 -c -"
  | WF-T1 [M-2] 최상위 키 = ['jobs', 'name', 'on', 'permissions'] · allowlist = ['jobs', 'name', 'on', 'permissions', 'run-name']
  | WF-T2 [F#4①] permissions = {'contents': 'read'}
  | WF-T3 [M-1] on = ['pull_request'] → 트리거 집합 ['pull_request']
  | WF-J1 [F#2ii] jobs 키 = ['tos-gate'] (개수 1 · 요구 1) · 계약 리터럴 잡 id = 'tos-gate'
  | WF-J2 게이트 잡 키 = ['name', 'runs-on', 'steps'] · 닫힌 집합 = ['name', 'runs-on', 'steps']
  | WF-J3 [F#2i-b] 잡 name = 'tos-gate' · 계약 리터럴 = 'tos-gate'
  | WF-J4 [F#4②] runs-on = 'ubuntu-latest' · 허용 = ['ubuntu-24.04', 'ubuntu-latest']
  | WF-S1 [F#1] steps 개수 = 3 (요구 3·순서 고정) · 이름 = [None, 'tos-gate: verify harness sha256', 'tos-gate: run harness']
  | WF-S2 [①체크아웃] 키 = ['uses', 'with'] · uses = 'actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1' · with = {'fetch-depth': 0, 'persist-credentials': False}
  | WF-C3 [②B/verify sha256] 정규형 = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 1817c9ef5d790c111d4738b89e3c3add80dc2d9f80f9b8af7ef5738636cfbffb | shasum -a 256 -c -"
  | WF-C3 [②B/verify sha256] 정본   = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 1817c9ef5d790c111d4738b89e3c3add80dc2d9f80f9b8af7ef5738636cfbffb | shasum -a 256 -c -"
  | WF-C4 [②B/verify sha256] byte 일치 = True
  | WF-C5 [②B/verify sha256] 스텝 키 = ['name', 'run'] · 닫힌 집합 = True
  | WF-C3 [③A/run harness] 정규형 = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C3 [③A/run harness] 정본   = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C4 [③A/run harness] byte 일치 = True
  | WF-C5 [③A/run harness] 스텝 키 = ['name', 'run'] · 닫힌 집합 = True
  | WF-C6 blob 층 판정 = BLOB_OK
  | RESULT=BLOB_OK
U17-BT (b-blob)@target 판정 = OK   [무조건 항 · D 와 무관]
P_first(집합·|1|)=[ec9daa0c950f7b92d749f934a9b1ff751b39bfb0 ] P_last(집합·|1|·blob=27bf97434240a0b463c120148ddf1fc859b5462d)=[ec9daa0c950f7b92d749f934a9b1ff751b39bfb0 ] |D|=0 D=[ ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 1건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.P4cUYfVd5Z/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B D=∅ — (b-blob)@d·(b-server)·(c) 는 «D-지표 항»이라 평가 대상 없음.  **(b-blob)@target 은 위에서 «무조건 항»으로 이미 평가됐다**(v2.22·M-7 — v2.21 은 (b)(c) 를 통째로 접었다·심판 #3 vacuity)
U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ **(b-blob)@target=OK(무조건 항·target HEAD=0932645d1ba44d1067ac793780bf10ba4f41e591)** ∧ (b-blob)@d·(b-server) 전 리비전 검증(|D|=0 · ①-R→②-S→③-C E₀ 파생 ∧ α/β 독립 관측 ∧ ⑥ 완전성 인증서) ∧ (α) 연속성 성립(t_land=∅) — responder=gh
two_arm_rc=0
```

## (4) 판정 — 프로그램 산출 (해석을 적는 자리가 없다)

- run 1 의 상태 라인(위 출력 원문 3행째)이 하니스의 프로그램 산출이며 값은
  `ENTRY_OK` 다.  중변 u17-verify 의 프로그램 산출은 `PREVENTION_ACTIVE` 다.
- exit code: 체인 최종 rc 는 출력 원문 마지막 줄 `two_arm_rc=0` 이 기록한다.
  `&&` 의미론상 중변이 실행됐다는 사실(출력 원문의 `U17-SNAP` 이후 전부)이
  **좌변 하니스 exit code = 0** 의 관측면이고, 체인 rc 0 이 **중변 exit
  code = 0** 의 관측면이다 — 이 억제 구조 자체가 U-15-f-1 이 소비하는
  성질이며 별도 해석이 아니다.

## (4b) 하니스 원문의 무결성 결속

명령 원문과 출력 원문:

```text
$ shasum -a 256 tools/tos_entry_harness.sh
1817c9ef5d790c111d4738b89e3c3add80dc2d9f80f9b8af7ef5738636cfbffb  tools/tos_entry_harness.sh
```

이 값은 계약 핀(u17-verify 의 `LIT2` = §12.3.4-R 블록 sha256)과 일치하며,
target 의 `.github/workflows/tos-gate.yml` ② 스텝이 같은 리터럴로 검증하는
것을 중변 출력 원문(WF-C3/C4)이 함께 보였다.  digest 의 보유처는 이
transcript 이고 대상은 실행한 스크립트 파일이라 측정 범위가 분리된다.

## (5) 가드 실행 기록 (U-15-f 형태)

가드 명령 원문 — 이 transcript 확정 직후 저장소 루트에서 **아래 블록
그대로** 실행된다.  `T_SHA` 는 이 파일 자신의 sha256 이므로 리터럴로
자기포함할 수 없고(자기참조), 확정본에서 실행 시점에 파생하는 변수형이
정본이다.  우변(D0A-FIRST)은 §12.1 이 명명한 실제 행위이며 대리가 아니다:

```sh
cd /Users/harris/Development/private/kis_unified_sts
S=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/7edbfc95-a416-4a69-89d9-f24a839ede41/scratchpad
T_PATH=docs/reviews/phase0-completion-contract/20260831-124103/U15-ENTRY-CHECK.md
T_RUN=1
T_SHA=$(shasum -a 256 "$S/U15-ENTRY-CHECK.md" | cut -d' ' -f1)
bash tools/tos_entry_harness.sh && bash tools/u17-verify.sh && \
  cp "$S/tos_completion.yaml" config/tos_completion.yaml && \
  git add config/tos_completion.yaml && \
  git commit -m "feat(tos): D0A-FIRST — config/tos_completion.yaml 도입 (D0-A 최초 행위 · §12.1)" \
    -m "U-15-f-1 규정 착수 형식(3단 가드)으로 개시한다 — 좌변 하니스 ENTRY_OK ·
중변 u17-verify PREVENTION_ACTIVE(실 서버 · responder=gh)를 이 커밋의 부모
e2048397 에서 실측한 뒤에만 우변이 도달한다.  내용은 전부 계약 파생:

- U-1a 임계값 3종 = 3 / 0 / 7 (§13.6.4 — 원리 파생 · 이 파일이 유일 런타임 소스)
- T-71 분류 분포 앵커 = 2 / 3 / 6 (§4.2.2 결합 규칙 · §4.2.1 표 11행)
- U-9a closable=NO 집합 = UNCHK-014 (§13.2 시드 · closable_no_rows = 1)
- T-76 레벨 원시값 26종 (값, 행수) — tos-spec/src 두 레지스터 490행에서 csv
  파서로 재파생(§5.2.8.0 스냅샷과 전 쌍 일치 · book 산출물 제외)
- oq11_response_deadline = DEADLINE_UNSET — 운영자 게이트 named-TBD 의 정직
  노출 (§12.3.1 ④ · 미정은 무한대가 아니라 차단)

transcript(U-15-e)는 H→d→T 순서(§12.3.4-G G6)에 따라 이 커밋 직후 같은
스탬프로 착지하며, 아래 트레일러가 그 파일·run·sha256 을 핀한다." \
    -m "Entry-Transcript: $T_PATH
Entry-Transcript-Run: $T_RUN
Entry-Transcript-SHA256: $T_SHA
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
printf 'guard_rc=%d\n' $?
```

### 사전(pre-d) 산물 부재 실측 — 억제 음성의 짝이 되는 기준선

명령·출력 원문:

```text
$ ls -la config/tos_completion.yaml
ls: config/tos_completion.yaml: No such file or directory
$ git rev-list --full-history HEAD -- config/tos_completion.yaml
(출력 없음 = 도입 커밋 부재)
```

`--full-history` 후보 위 구조 평가가 판정 우주 `D`(U-15-g-1)의 정본이며,
중변 출력 원문의 `|D|=0` 라인이 그 구조 정의의 실행 실측이다 — 이 시점의
provenance 상태는 `NOT_STARTED`(비차단·정상)다.

### guard_rc 와 산물 «생성» 실측의 자리

- 좌·중변 사전 실행 rc = 0 (위 (1)(2) — 차단 상태가 아님의 실측).
- 3단 전체의 `guard_rc`, 산물 생성(파일 + 도입 커밋 `|D|=1`), 부모 결속
  (`parent(d) == R-0 head` — U-15-f-4) 실측은 **d 이후의 관측**이므로 이
  파일에 담을 수 없다(이 파일은 d 의 트레일러가 sha256 으로 고정한다).
  U-15-e (4d) 의 규율대로 **같은 스탬프의 새 파일**
  `U15-ENTRY-CHECK-ADDENDUM.md` 이 그 전부를 명령·출력 원문으로 담는다.
  이 항의 존재가 «가드 형태를 썼다»의 기록이다(U-15-f-2).

## (6) 소비 조건 — transcript currency

- 이 transcript 의 HEAD(`e2048397…`)는 진입 시점 HEAD 와 **같다**(동일
  커밋에서 확정·착수).  그 사이 `bound_paths` 를 건드린 커밋은 **공집합**
  이다(커밋 자체가 없다 — R-7 재적용 자명 충족).
- 우변 d 는 `config/tos_completion.yaml` 만 도입하며 `bound_paths` ·
  권위 입력 4종을 건드리지 않는다.  T(이 파일의 착지)도 `$STAMPS` 하위
  추가만이라 재심 승인(R-4~R-7)의 currency 를 만료시키지 않는다.
