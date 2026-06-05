# TLS Setup

This project uses Redis DB 1 for runtime streams/state and SQLite/Parquet files
for durable runtime and market-data storage. TLS guidance therefore applies to
networked services such as Redis, reverse proxies, and external APIs. SQLite and
Parquet are local files and do not require transport TLS.

## Redis TLS

Enable Redis TLS only when Redis is exposed across a network boundary. For
single-host compose usage, prefer private Docker networking and avoid exposing
Redis to the public interface.

Example env:

```bash
REDIS_URL=rediss://localhost:6379/1
REDIS_TLS_CERT_REQS=required
REDIS_CA_CERT=/etc/ssl/certs/redis-ca.crt
REDIS_CLIENT_CERT=/etc/ssl/certs/redis-client.crt
REDIS_CLIENT_KEY=/etc/ssl/private/redis-client.key
```

Verification:

```bash
redis-cli --tls \
  --cacert /etc/ssl/certs/redis-ca.crt \
  --cert /etc/ssl/certs/redis-client.crt \
  --key /etc/ssl/private/redis-client.key \
  -n 1 ping
```

Expected output:

```text
PONG
```

## Runtime Storage

Runtime persistence is file based:

- SQLite ledger: `data/runtime/<env>/runtime.db`
- Parquet market data: `data/market/.../*.parquet`

Protect these paths with filesystem permissions, disk encryption, and backups.
Do not solve local-file confidentiality with service TLS.

## Reverse Proxy

Dashboard/API exposure should terminate HTTPS at the reverse proxy. Keep API
services on the private Docker network or loopback interface when possible.

Minimum operator checks:

```bash
curl -fsS https://<host>/api/health
docker compose ps
redis-cli -n 1 ping
```

## Certificate Rotation

1. Install the new proxy/Redis certificates next to the existing files.
2. Reload the proxy or Redis service.
3. Run the health checks above.
4. Keep the previous certificates until dashboard/API and Redis checks pass.

## Security Checklist

- Redis binds only to a private interface or protected Docker network.
- Redis DB 1 is used consistently for runtime state.
- Dashboard/API public traffic is HTTPS.
- SQLite and Parquet directories have restrictive filesystem permissions.
- Secrets remain in env files or secret stores and are never committed.
