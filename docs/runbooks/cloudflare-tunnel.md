# Cloudflare Tunnel — /tos 화면을 인터넷에서 열기

운영자 1명이 외부에서 `https://<TOS_PUBLIC_HOSTNAME>` 으로 `/tos` 를 보기 위한
절차. 모델은 **아웃바운드 전용**이다: `cloudflared` 컨테이너가 Cloudflare 로
나가서 연결을 유지하고, 들어오는 요청은 그 연결을 타고 `caddy:5080` 으로 간다.
호스트에 새로 열리는 포트는 **없다**(`docs/ports.md` 는 그대로 한 줄).

- 구성: `docker-compose.yml` 의 `cloudflared` 서비스, compose 프로파일 `tunnel`.
- 토큰: `CLOUDFLARE_TUNNEL_TOKEN` (커밋되지 않는 env 파일). `.env.example` 참고.
- 호스트명: `TOS_PUBLIC_HOSTNAME`. 실제 라우팅·정책은 Cloudflare 대시보드가 보관.

전제: Cloudflare 계정에 도메인(zone)이 등록돼 있고, 기본 스택(`dashboard` ·
`strategy-builder-ui` · `caddy`)이 이미 떠 있을 것. 터널은 앞단에 붙기만 한다.

## 1. 터널 생성 → 토큰

1. Cloudflare **Zero Trust → Networks → Tunnels → Create a tunnel**.
2. 커넥터로 **Cloudflared** 선택, 이름을 정한다(예: `kis-tos`).
3. 설치 명령에 섞여 나오는 **토큰 문자열**만 복사한다(`cloudflared service
   install <TOKEN>` 의 `<TOKEN>`). 호스트에 cloudflared 를 설치하지는 않는다 —
   컨테이너가 그 역할을 한다.
4. 스택을 띄울 때 쓰는 env 파일에 넣는다. `--env-file` 로 다른 파일을 쓴다면
   **그 파일**에 넣어야 한다(compose 는 건네받은 파일만 읽는다).

   ```
   CLOUDFLARE_TUNNEL_TOKEN=<복사한 토큰>
   TOS_PUBLIC_HOSTNAME=tosdesk.dev
   ```

   토큰은 자격증명이다. 저장소·PR·이슈·로그에 붙여 넣지 않는다.

## 2. Public hostname → origin

같은 터널 화면의 **Published application routes / Public hostname → Add**:

| 항목 | 값 |
|---|---|
| Subdomain / Domain | 비움 / `tosdesk.dev` (= `TOS_PUBLIC_HOSTNAME`) |
| Service type | `HTTP` |
| URL | `caddy:5080` |

`caddy` 는 compose 네트워크 안의 서비스명이다. cloudflared 가 같은
`trading-network` 에 있으므로 그대로 해석된다.

> SAFETY: 공개 호스트명은 **이 하나만** 둔다. 같은 터널에 호스트명을 더 얹거나
> WARP private network 라우트를 켜면 `dashboard:8001` 이 Access 없이 인터넷에
> 노출된다 — 그 포트의 `/health` · `/docs` · `/openapi.json` 은 무인증이다.

## 3. Cloudflare Access (필수)

**Zero Trust → Access → Applications → Add an application → Self-hosted**.

- Application domain: `tosdesk.dev` — **경로 없이 호스트명 전체**.
- Policy: Action `Allow`, Include → `Emails` → `<operator email>`.
- 로그인 방법은 **One-time PIN** 하나면 된다.

> SAFETY: 경로를 좁혀 `/tos` 에만 걸지 않는다. 브라우저 번들에는 빌드 시점에
> `NEXT_PUBLIC_API_KEY`(= 대시보드 API 키)가 박혀 있고, `/_next/*` 나
> `/health` · `/docs` 가 Access 밖에 남으면 그 키와 무인증 엔드포인트가 그대로
> 공개된다. Access 가 이 호스트명의 유일한 문지기다.

## 4. 기동 · 검증 · 롤백

```bash
docker compose --profile tunnel up -d cloudflared     # 기동 (이것만 뜬다)
docker compose --profile tunnel logs -f cloudflared   # "Registered tunnel connection" 4줄
docker compose --profile tunnel ps                    # 상태 확인
```

- 브라우저로 `https://tosdesk.dev` → Access 로그인(One-time PIN) → `/tos` 리다이렉트.
- 토큰이 비었거나 틀리면 컨테이너가 바로 종료되고 로그에
  `Provided Tunnel token is not valid` 가 남는다. 기본 스택에는 영향이 없다.
- 롤백(공개만 내리기): `docker compose --profile tunnel stop cloudflared`.

> ⛔ `docker compose down` 금지. 운영자 상주 스택(caddy · dashboard · ui)이 같이
> 죽는다. 터널만 내릴 때는 위의 `stop cloudflared` 를 쓴다.

Access 세션이 만료되면 화면의 15초 폴링은 로그인 페이지로 리다이렉트되어
「상태 조회 연결 오류」로 보인다. 새로고침해 다시 로그인하면 복구된다.
