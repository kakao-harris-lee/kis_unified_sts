# Cloudflare Tunnel — /tos 화면을 인터넷에서 열기

운영자 1명이 외부에서 `https://<TOS_PUBLIC_HOSTNAME>` 으로 `/tos` 를 보기 위한
절차. **아웃바운드 전용**이다: `cloudflared` 가 Cloudflare 로 나가서 연결을
유지하고, 들어오는 요청은 그 연결을 타고 `caddy:5080` 으로 간다. 호스트에 새로
열리는 포트는 **없다**(`docs/ports.md` 는 그대로 한 줄). 구성은
`docker-compose.yml` 의 `cloudflared`(프로파일 `tunnel`)이며, 연결은
`tunnel-network` 에서 `caddy` 하고만 이뤄진다 — `dashboard:8001` 은 닿지 않는다.
토큰은 `CLOUDFLARE_TUNNEL_TOKEN`, 호스트명은 `TOS_PUBLIC_HOSTNAME`(`.env.example`).

> ⛔ **순서가 안전장치다.** §3 의 Access 애플리케이션을 **먼저** 만들고 그 다음
> §4 에서 터널을 올린다. Access 없이 올라온 터널은 그 순간부터 `/tos` ·
> `/_next/*` · `/health` · `/docs` 를 무인증 공개하고, 브라우저 번들에 박힌
> 대시보드 API 키까지 같이 내준다.

전제: Cloudflare 계정에 도메인(zone)이 등록돼 있고, 기본 스택(`dashboard` ·
`strategy-builder-ui` · `caddy`)이 이미 떠 있을 것.

## 1. 터널 생성 → 토큰

1. **Zero Trust → Networks → Tunnels → Create a tunnel**, 커넥터는
   **Cloudflared**, 이름은 예컨대 `kis-tos`.
2. 설치 명령에서 **`eyJ` 로 시작하는 긴 문자열**만 복사한다
   (`cloudflared service install <TOKEN>` 의 `<TOKEN>`). 같이 보이는 36자 터널
   ID(UUID)는 토큰이 아니다. 호스트에 cloudflared 를 설치하지는 않는다 —
   컨테이너가 그 역할을 한다.
3. 스택을 띄울 때 쓰는 env 파일에 넣는다. 상주 스택은 `.env.paper`
   (`scripts/deploy_paper.sh` 가 강제, `COMPOSE_PROJECT_NAME=kis_paper`).

   ```
   CLOUDFLARE_TUNNEL_TOKEN=eyJ…
   TOS_PUBLIC_HOSTNAME=tosdesk.dev
   ```

토큰은 자격증명이다. 저장소·PR·이슈에 붙여 넣지 않는다. **`docker compose config`
와 `docker inspect` 는 이 값을 평문으로 출력한다** — 그 출력을 공유하거나 로그로
남기기 전에 지운다. 샜다면 Cloudflare 에서 그 터널의 토큰을 재발급(또는 터널을
지우고 재생성)하고 env 파일을 고친 뒤:
`docker compose --env-file .env.paper --profile tunnel up -d --force-recreate cloudflared`.

## 2. Public hostname → origin

같은 터널 화면의 **Public hostname**(최근 UI 는 **Published application routes**)
→ **Add**. Subdomain 은 비우고 Domain 은 `tosdesk.dev`(= `TOS_PUBLIC_HOSTNAME`),
Service type `HTTP`, URL `caddy:5080`. `caddy` 는 compose 서비스명이고,
cloudflared 와 같은 `tunnel-network` 에 있으므로 그대로 해석된다.

> SAFETY: 공개 호스트명은 **이 하나만** 둔다. 같은 터널에 호스트명을 더 얹거나
> WARP private network 라우트를 켜면 Access 없는 경로가 생긴다. 네트워크 분리
> 덕에 `dashboard:8001` 에 직접 닿지는 못하지만, 그런 경로도 Caddy 를 거쳐
> 무인증인 `/health` · `/docs` · `/openapi.json` 에는 닿는다.

## 3. Cloudflare Access (터널보다 먼저)

**Zero Trust → Access → Applications → Add an application → Self-hosted**.

- Application domain: `tosdesk.dev` — **경로 없이 호스트명 전체**.
- Policy: Action `Allow`, Include → `Emails` → `<operator email>`.
- 로그인 방법은 **One-time PIN** 하나면 된다.

> SAFETY: 경로를 좁혀 `/tos` 에만 걸지 않는다. 번들에는 빌드 시점에
> `NEXT_PUBLIC_API_KEY`(= 대시보드 API 키)가 박혀 있고, `/_next/*` 나 `/health` ·
> `/docs` 가 Access 밖에 남으면 그 키와 무인증 엔드포인트가 공개된다. Access 가
> 이 호스트명의 유일한 문지기다.

## 4. 기동

첫 기동은 **caddy 도 함께 재생성**해야 한다. caddy 가 새 `tunnel-network` 에
붙어야 cloudflared 가 `caddy:5080` 을 찾는다(이 변경 뒤 첫 `up -d` 는 프로파일과
무관하게 caddy 를 한 번 재생성한다). 이 저장소 규칙대로 `--no-deps`:

```bash
docker compose --env-file .env.paper --profile tunnel up -d --no-deps caddy cloudflared
docker compose --env-file .env.paper --profile tunnel logs -f cloudflared
```

caddy 재생성 동안 UI 가 몇 초 끊긴다(정상). 두 번째부터는 `cloudflared` 만 쓰면
된다. 로그에 `Registered tunnel connection` 이 네 줄 뜨면 연결된 것이다.

## 5. 검증 (쿠키 없는 셸에서)

```bash
for p in / /tos /_next/static/x /health /docs /openapi.json /api/tos/projection; do
  curl -s -o /dev/null -w "%{http_code} %{redirect_url}\n" https://tosdesk.dev$p
done
```

모든 줄이 `302` + `…cloudflareaccess.com/…` 이어야 한다. 한 줄이라도 오리진에서
온 `200`/`401` 이면 Access 가 그 경로를 덮지 못한 것이다 — 즉시 §6 으로 내리고
§3 을 고친다. 그 다음 브라우저로 `https://tosdesk.dev` → One-time PIN → `/tos`.

## 6. 롤백 · 고장

```bash
docker compose --env-file .env.paper --profile tunnel stop cloudflared   # 공개만 내린다
```

> ⛔ `docker compose down` 금지. 운영자 상주 스택(caddy · dashboard · ui)이 같이
> 죽는다. 터널만 내릴 때는 위의 `stop cloudflared`.

- 토큰이 비었거나 틀리면 컨테이너가 종료되고 `restart: unless-stopped` 때문에
  **계속 재시작한다**(로그: `Provided Tunnel token is not valid`). 기본 스택에는
  영향이 없다. 기다리지 말고 `stop cloudflared` → 토큰 수정 → 다시 §4.
- Access 세션이 만료되면 화면의 15초 폴링이 로그인 페이지로 리다이렉트되어
  「상태 조회 연결 오류」로 보인다. 새로고침해 다시 로그인하면 복구된다.
