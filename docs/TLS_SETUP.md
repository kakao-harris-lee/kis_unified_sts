# TLS/SSL Setup Guide

## Overview

The KIS Unified Trading System supports TLS/SSL encryption for both Redis and ClickHouse database connections to secure data in transit. This guide covers how to enable and configure TLS for both databases.

**Security Benefits:**
- **Encrypted Data Transfer**: All trading data (positions, orders, market data, strategy signals) transmitted over encrypted channels
- **Password Protection**: Database passwords encrypted in transit, preventing network sniffing
- **Authentication**: Optional mutual TLS (mTLS) with client certificates for enhanced security
- **Compliance**: Meets security requirements for production trading systems

**Default Behavior:**
- TLS is **disabled by default** for backward compatibility
- Non-TLS connections continue to work without any configuration changes
- TLS must be explicitly enabled via environment variables

---

## Quick Start

### Enable TLS for Redis

```bash
# In your .env file
REDIS_TLS_ENABLED=true
REDIS_TLS_CERT_REQS=required
REDIS_TLS_CA_CERTS=/path/to/redis-ca.crt
```

### Enable TLS for ClickHouse

```bash
# In your .env file
CLICKHOUSE_SECURE=true
CLICKHOUSE_VERIFY_SSL=true
CLICKHOUSE_CA_CERT=/path/to/clickhouse-ca.crt
```

---

## Redis TLS Configuration

### Environment Variables

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `REDIS_TLS_ENABLED` | `true` / `false` | `false` | Enable TLS encryption (changes scheme to `rediss://`) |
| `REDIS_TLS_CERT_REQS` | `none` / `optional` / `required` | `required` | Certificate verification requirement |
| `REDIS_TLS_CA_CERTS` | file path | _(system CA)_ | Path to CA certificate bundle |

### Connection Scheme

When `REDIS_TLS_ENABLED=true`, the Redis URL scheme automatically changes:

```python
# TLS disabled (default)
redis://localhost:6379/1

# TLS enabled
rediss://localhost:6379/1  # Note the 'rediss://' scheme
```

### Certificate Verification Modes

#### Required (Recommended for Production)

```bash
REDIS_TLS_ENABLED=true
REDIS_TLS_CERT_REQS=required
REDIS_TLS_CA_CERTS=/etc/ssl/certs/redis-ca.crt
```

- Server certificate **must** be valid and signed by trusted CA
- Connection fails if certificate is invalid or expired
- **Most secure option**

#### Optional (Development/Testing)

```bash
REDIS_TLS_ENABLED=true
REDIS_TLS_CERT_REQS=optional
```

- Server certificate validated if provided
- Connection proceeds even if certificate is invalid
- Use only for testing/debugging

#### None (Not Recommended)

```bash
REDIS_TLS_ENABLED=true
REDIS_TLS_CERT_REQS=none
```

- No certificate verification performed
- Vulnerable to man-in-the-middle attacks
- Use only for local development with self-signed certificates

### Redis Server TLS Setup

#### 1. Generate Self-Signed Certificate (Development)

```bash
# Create directory for certificates
mkdir -p /etc/redis/ssl
cd /etc/redis/ssl

# Generate CA private key
openssl genrsa -out ca-key.pem 4096

# Generate CA certificate (valid for 10 years)
openssl req -new -x509 -days 3650 -key ca-key.pem -out ca-cert.pem \
  -subj "/CN=Redis CA/O=KIS Trading/C=KR"

# Generate server private key
openssl genrsa -out redis-server-key.pem 4096

# Generate server certificate signing request
openssl req -new -key redis-server-key.pem -out redis-server.csr \
  -subj "/CN=redis.local/O=KIS Trading/C=KR"

# Sign server certificate with CA
openssl x509 -req -days 3650 -in redis-server.csr \
  -CA ca-cert.pem -CAkey ca-key.pem -CAcreateserial \
  -out redis-server-cert.pem

# Set permissions
chmod 600 redis-server-key.pem ca-key.pem
chmod 644 redis-server-cert.pem ca-cert.pem
```

#### 2. Configure Redis Server

Edit `/etc/redis/redis.conf`:

```conf
# Enable TLS
tls-port 6379
port 0  # Disable non-TLS port

# Server certificate and key
tls-cert-file /etc/redis/ssl/redis-server-cert.pem
tls-key-file /etc/redis/ssl/redis-server-key.pem

# CA certificate for client verification (optional - for mTLS)
tls-ca-cert-file /etc/redis/ssl/ca-cert.pem

# Client certificate verification (optional)
tls-auth-clients no  # Set to 'yes' for mutual TLS

# Allowed TLS protocols
tls-protocols "TLSv1.2 TLSv1.3"

# Cipher suites (use strong ciphers only)
tls-ciphers TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256:TLS_AES_128_GCM_SHA256
tls-prefer-server-ciphers yes
```

#### 3. Restart Redis

```bash
sudo systemctl restart redis
```

### Docker Compose Configuration

```yaml
services:
  redis:
    image: redis:7-alpine
    command: >
      redis-server
      --tls-port 6379
      --port 0
      --tls-cert-file /etc/redis/ssl/redis-server-cert.pem
      --tls-key-file /etc/redis/ssl/redis-server-key.pem
      --tls-ca-cert-file /etc/redis/ssl/ca-cert.pem
      --tls-auth-clients no
    volumes:
      - ./ssl/redis:/etc/redis/ssl:ro
    ports:
      - "6379:6379"

  app:
    environment:
      REDIS_HOST: redis
      REDIS_PORT: 6379
      REDIS_TLS_ENABLED: "true"
      REDIS_TLS_CERT_REQS: required
      REDIS_TLS_CA_CERTS: /app/ssl/redis-ca.crt
    volumes:
      - ./ssl/ca-cert.pem:/app/ssl/redis-ca.crt:ro
```

### Testing Redis TLS

```bash
# Test with redis-cli
redis-cli --tls \
  --cert /etc/redis/ssl/redis-server-cert.pem \
  --key /etc/redis/ssl/redis-server-key.pem \
  --cacert /etc/redis/ssl/ca-cert.pem \
  PING

# Test with Python
python -c "
import os
os.environ['REDIS_TLS_ENABLED'] = 'true'
os.environ['REDIS_TLS_CA_CERTS'] = '/etc/redis/ssl/ca-cert.pem'
from shared.streaming.client import RedisClient
client = RedisClient._create_client()
print(client.ping())  # Should print: True
"
```

---

## ClickHouse TLS Configuration

### Environment Variables

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `CLICKHOUSE_SECURE` | `true` / `false` | `false` | Enable TLS encryption (HTTPS) |
| `CLICKHOUSE_VERIFY_SSL` | `true` / `false` | `true` | Verify server SSL certificate |
| `CLICKHOUSE_CA_CERT` | file path | _(system CA)_ | Path to CA certificate file |
| `CLICKHOUSE_CLIENT_CERT` | file path | _(none)_ | Path to client certificate (mTLS) |
| `CLICKHOUSE_CLIENT_KEY` | file path | _(none)_ | Path to client private key (mTLS) |

### Protocol Changes

When `CLICKHOUSE_SECURE=true`, the protocol automatically switches:

```python
# TLS disabled (default)
clickhouse://localhost:9000/default  # HTTP on port 8123

# TLS enabled
clickhouses://localhost:9440/default  # HTTPS on port 8443
```

### Configuration Examples

#### Basic TLS (System CA)

```bash
# Use system's trusted CA certificates
CLICKHOUSE_SECURE=true
CLICKHOUSE_VERIFY_SSL=true
```

#### TLS with Custom CA

```bash
# Use custom CA certificate
CLICKHOUSE_SECURE=true
CLICKHOUSE_VERIFY_SSL=true
CLICKHOUSE_CA_CERT=/etc/ssl/certs/clickhouse-ca.crt
```

#### Mutual TLS (mTLS)

```bash
# Client certificate authentication
CLICKHOUSE_SECURE=true
CLICKHOUSE_VERIFY_SSL=true
CLICKHOUSE_CA_CERT=/etc/ssl/certs/clickhouse-ca.crt
CLICKHOUSE_CLIENT_CERT=/etc/ssl/certs/clickhouse-client.crt
CLICKHOUSE_CLIENT_KEY=/etc/ssl/private/clickhouse-client.key
```

#### Development (Skip Verification)

```bash
# WARNING: Not secure - for testing only
CLICKHOUSE_SECURE=true
CLICKHOUSE_VERIFY_SSL=false
```

### ClickHouse Server TLS Setup

#### 1. Generate Certificates (Development)

```bash
# Create directory for certificates
mkdir -p /etc/clickhouse-server/ssl
cd /etc/clickhouse-server/ssl

# Generate CA private key
openssl genrsa -out ca-key.pem 4096

# Generate CA certificate
openssl req -new -x509 -days 3650 -key ca-key.pem -out ca-cert.pem \
  -subj "/CN=ClickHouse CA/O=KIS Trading/C=KR"

# Generate server private key
openssl genrsa -out server-key.pem 4096

# Generate server CSR
openssl req -new -key server-key.pem -out server.csr \
  -subj "/CN=clickhouse.local/O=KIS Trading/C=KR"

# Create server certificate extensions file
cat > server-ext.cnf << EOF
subjectAltName = DNS:clickhouse.local,DNS:localhost,IP:127.0.0.1
EOF

# Sign server certificate
openssl x509 -req -days 3650 -in server.csr \
  -CA ca-cert.pem -CAkey ca-key.pem -CAcreateserial \
  -out server-cert.pem -extfile server-ext.cnf

# Set permissions
chown clickhouse:clickhouse *.pem
chmod 600 server-key.pem ca-key.pem
chmod 644 server-cert.pem ca-cert.pem
```

#### 2. Configure ClickHouse Server

Edit `/etc/clickhouse-server/config.xml`:

```xml
<clickhouse>
    <!-- HTTPS interface -->
    <https_port>8443</https_port>

    <!-- Disable HTTP if you want HTTPS-only -->
    <!-- <http_port remove="1"/> -->

    <openSSL>
        <server>
            <!-- Server certificate -->
            <certificateFile>/etc/clickhouse-server/ssl/server-cert.pem</certificateFile>
            <privateKeyFile>/etc/clickhouse-server/ssl/server-key.pem</privateKeyFile>

            <!-- CA certificate for client verification (optional - for mTLS) -->
            <caConfig>/etc/clickhouse-server/ssl/ca-cert.pem</caConfig>

            <!-- Verify client certificates (optional - for mTLS) -->
            <verificationMode>none</verificationMode>  <!-- or 'relaxed', 'strict' -->

            <!-- Disable SSL v2/v3, use TLS only -->
            <disableProtocols>sslv2,sslv3</disableProtocols>

            <!-- Prefer server cipher order -->
            <preferServerCiphers>true</preferServerCiphers>

            <!-- Strong cipher suites only -->
            <cipherList>HIGH:!aNULL:!MD5:!3DES:!CAMELLIA:!AES128</cipherList>

            <!-- Cache SSL sessions -->
            <cacheSessions>true</cacheSessions>
            <sessionIdContext>clickhouse</sessionIdContext>
            <sessionTimeout>3600</sessionTimeout>
        </server>

        <!-- Client SSL settings (for distributed queries) -->
        <client>
            <caConfig>/etc/clickhouse-server/ssl/ca-cert.pem</caConfig>
            <verificationMode>relaxed</verificationMode>
        </client>
    </openSSL>
</clickhouse>
```

#### 3. Restart ClickHouse

```bash
sudo systemctl restart clickhouse-server
```

### Docker Compose Configuration

```yaml
services:
  clickhouse:
    image: clickhouse/clickhouse-server:latest
    environment:
      CLICKHOUSE_SSL_ENABLED: "true"
    volumes:
      - ./ssl/clickhouse/server-cert.pem:/etc/clickhouse-server/ssl/server-cert.pem:ro
      - ./ssl/clickhouse/server-key.pem:/etc/clickhouse-server/ssl/server-key.pem:ro
      - ./ssl/clickhouse/ca-cert.pem:/etc/clickhouse-server/ssl/ca-cert.pem:ro
      - ./clickhouse-config.xml:/etc/clickhouse-server/config.d/ssl.xml:ro
    ports:
      - "8443:8443"  # HTTPS
      - "9440:9440"  # Native TLS

  app:
    environment:
      CLICKHOUSE_HOST: clickhouse
      CLICKHOUSE_PORT: 8443
      CLICKHOUSE_SECURE: "true"
      CLICKHOUSE_VERIFY_SSL: "true"
      CLICKHOUSE_CA_CERT: /app/ssl/clickhouse-ca.crt
    volumes:
      - ./ssl/clickhouse/ca-cert.pem:/app/ssl/clickhouse-ca.crt:ro
```

### Testing ClickHouse TLS

```bash
# Test with clickhouse-client
clickhouse-client --host localhost --port 9440 --secure \
  --user default --password '' \
  --query "SELECT 1"

# Test with curl
curl https://localhost:8443 \
  --cacert /etc/clickhouse-server/ssl/ca-cert.pem \
  --user default: \
  --data "SELECT 1"

# Test with Python
python -c "
import os
os.environ['CLICKHOUSE_SECURE'] = 'true'
os.environ['CLICKHOUSE_VERIFY_SSL'] = 'true'
os.environ['CLICKHOUSE_CA_CERT'] = '/etc/clickhouse-server/ssl/ca-cert.pem'
from shared.db.config import ClickHouseConfig
from shared.db.client import ClickHouseClient
config = ClickHouseConfig.from_env()
client = ClickHouseClient(config)
result = client.execute('SELECT 1')
print(result)  # Should print: [(1,)]
"
```

---

## Environment Variable Configuration

### Development (.env.example)

```bash
# Redis TLS - Disabled for local development
REDIS_TLS_ENABLED=false
REDIS_TLS_CERT_REQS=required
REDIS_TLS_CA_CERTS=

# ClickHouse TLS - Disabled for local development
CLICKHOUSE_SECURE=false
CLICKHOUSE_VERIFY_SSL=true
CLICKHOUSE_CA_CERT=
```

### Production (.env.production.example)

```bash
# Redis TLS - Enabled with strong verification
REDIS_TLS_ENABLED=true
REDIS_TLS_CERT_REQS=required
REDIS_TLS_CA_CERTS=/etc/ssl/certs/redis-ca.crt

# ClickHouse TLS - Enabled with mutual TLS
CLICKHOUSE_SECURE=true
CLICKHOUSE_VERIFY_SSL=true
CLICKHOUSE_CA_CERT=/etc/ssl/certs/clickhouse-ca.crt
CLICKHOUSE_CLIENT_CERT=/etc/ssl/certs/clickhouse-client.crt
CLICKHOUSE_CLIENT_KEY=/etc/ssl/private/clickhouse-client.key
```

---

## Production Deployment Checklist

### Pre-Deployment

- [ ] **Generate Production Certificates**: Use proper CA-signed certificates (Let's Encrypt, corporate CA, etc.)
- [ ] **Secure Private Keys**: Restrict file permissions (`chmod 600`) and ownership
- [ ] **Test Certificate Validity**: Verify expiration dates and chain of trust
- [ ] **Document Certificate Locations**: Maintain inventory of all certificate paths
- [ ] **Backup Certificates**: Store encrypted backups of certificates and keys

### TLS Configuration

- [ ] **Enable TLS for Redis**: Set `REDIS_TLS_ENABLED=true`
- [ ] **Enable TLS for ClickHouse**: Set `CLICKHOUSE_SECURE=true`
- [ ] **Require Certificate Verification**: `REDIS_TLS_CERT_REQS=required`, `CLICKHOUSE_VERIFY_SSL=true`
- [ ] **Configure CA Certificates**: Point to trusted CA bundle
- [ ] **Consider Mutual TLS**: Add client certificates for enhanced security

### Testing

- [ ] **Test Redis Connection**: Verify encrypted connection with `redis-cli --tls`
- [ ] **Test ClickHouse Connection**: Verify HTTPS connection with `curl` or `clickhouse-client --secure`
- [ ] **Verify Application Startup**: Check logs for successful TLS handshake
- [ ] **Test Certificate Rotation**: Practice certificate renewal process
- [ ] **Monitor Performance**: Measure TLS overhead (typically <5% CPU impact)

### Security Validation

- [ ] **Network Traffic Analysis**: Use `tcpdump` or Wireshark to verify encrypted traffic
- [ ] **No Plaintext Credentials**: Confirm passwords not visible in packet captures
- [ ] **Certificate Validation**: Ensure invalid certificates are rejected
- [ ] **Strong Ciphers Only**: Verify weak ciphers are disabled (SSLv2, SSLv3, RC4, MD5)
- [ ] **Regular Security Audits**: Schedule periodic reviews of TLS configuration

### Monitoring

- [ ] **Certificate Expiration Alerts**: Set up monitoring 30 days before expiration
- [ ] **Connection Error Tracking**: Monitor TLS handshake failures
- [ ] **Performance Metrics**: Track connection latency with TLS enabled
- [ ] **Log TLS Events**: Enable debug logging for TLS during initial rollout

---

## Troubleshooting

### Common Issues

#### Redis: "Connection refused" Error

```
redis.exceptions.ConnectionError: Error connecting to localhost:6379
```

**Solutions:**
1. Check Redis server is running with TLS enabled:
   ```bash
   redis-cli --tls --cacert /path/to/ca-cert.pem PING
   ```

2. Verify TLS port is correct (default: 6379)

3. Check firewall rules allow TLS connections

4. Verify environment variables are loaded:
   ```python
   import os
   print(os.environ.get('REDIS_TLS_ENABLED'))  # Should print: true
   ```

#### Redis: "Certificate verify failed" Error

```
ssl.SSLCertVerificationError: certificate verify failed
```

**Solutions:**
1. Check CA certificate path is correct:
   ```bash
   ls -l $REDIS_TLS_CA_CERTS
   ```

2. Verify CA certificate matches server certificate:
   ```bash
   openssl verify -CAfile ca-cert.pem redis-server-cert.pem
   ```

3. For development, temporarily set `REDIS_TLS_CERT_REQS=optional` to bypass validation

4. Check certificate expiration:
   ```bash
   openssl x509 -in redis-server-cert.pem -noout -dates
   ```

#### ClickHouse: "SSL routines" Error

```
clickhouse_driver.errors.NetworkError: Code: 210. SSL routines:error:1408F10B
```

**Solutions:**
1. Verify ClickHouse server has HTTPS enabled:
   ```bash
   curl -v https://localhost:8443 --cacert /path/to/ca-cert.pem
   ```

2. Check SSL configuration in `/etc/clickhouse-server/config.xml`

3. Ensure certificate files are readable by ClickHouse user:
   ```bash
   sudo -u clickhouse cat /etc/clickhouse-server/ssl/server-cert.pem
   ```

4. For development, set `CLICKHOUSE_VERIFY_SSL=false` to bypass validation

#### ClickHouse: "Hostname mismatch" Error

```
ssl.SSLError: hostname 'localhost' doesn't match certificate
```

**Solutions:**
1. Add Subject Alternative Name (SAN) to certificate:
   ```bash
   # Create ext file
   echo "subjectAltName = DNS:localhost,IP:127.0.0.1" > san.ext

   # Regenerate certificate with SAN
   openssl x509 -req -in server.csr -CA ca-cert.pem -CAkey ca-key.pem \
     -out server-cert.pem -days 3650 -extfile san.ext
   ```

2. Use correct hostname matching certificate CN/SAN

3. For development, disable verification with `CLICKHOUSE_VERIFY_SSL=false`

#### Docker: Certificate Permission Denied

```
Error: Permission denied reading certificate file
```

**Solutions:**
1. Fix file permissions before mounting:
   ```bash
   chmod 644 ca-cert.pem server-cert.pem
   chmod 600 server-key.pem
   ```

2. Mount as read-only in Docker Compose:
   ```yaml
   volumes:
     - ./ssl/ca-cert.pem:/etc/ssl/certs/ca-cert.pem:ro
   ```

3. Check Docker user has read access to mounted files

### Debug Logging

Enable debug logging to troubleshoot TLS issues:

```bash
# Python logging
export LOG_LEVEL=DEBUG

# Redis client debug
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from shared.streaming.client import RedisClient
client = RedisClient._create_client()
print(client.ping())
"

# ClickHouse client debug
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from shared.db.client import ClickHouseClient
from shared.db.config import ClickHouseConfig
config = ClickHouseConfig.from_env()
client = ClickHouseClient(config)
print(client.execute('SELECT 1'))
"
```

### Network Traffic Analysis

Verify encryption is working:

```bash
# Capture Redis traffic (should be encrypted)
sudo tcpdump -i lo -A 'port 6379' | grep -i password

# Capture ClickHouse traffic (should be encrypted)
sudo tcpdump -i lo -A 'port 8443' | grep -i password

# If passwords are visible in plain text, TLS is NOT working!
```

---

## Certificate Management

### Certificate Rotation

#### Redis Certificate Rotation

```bash
# 1. Generate new certificates (keep old ones temporarily)
openssl genrsa -out redis-server-key-new.pem 4096
openssl req -new -key redis-server-key-new.pem -out redis-server-new.csr \
  -subj "/CN=redis.local/O=KIS Trading/C=KR"
openssl x509 -req -days 3650 -in redis-server-new.csr \
  -CA ca-cert.pem -CAkey ca-key.pem \
  -out redis-server-cert-new.pem

# 2. Update Redis configuration
sudo cp redis-server-cert-new.pem /etc/redis/ssl/redis-server-cert.pem
sudo cp redis-server-key-new.pem /etc/redis/ssl/redis-server-key.pem

# 3. Reload Redis (no downtime)
sudo systemctl reload redis

# 4. Verify new certificate
redis-cli --tls --cacert ca-cert.pem PING

# 5. Remove old certificates
rm redis-server-cert-old.pem redis-server-key-old.pem
```

#### ClickHouse Certificate Rotation

```bash
# 1. Generate new certificates
# (same process as Redis)

# 2. Update ClickHouse configuration files
sudo cp server-cert-new.pem /etc/clickhouse-server/ssl/server-cert.pem
sudo cp server-key-new.pem /etc/clickhouse-server/ssl/server-key.pem

# 3. Reload ClickHouse (graceful reload)
sudo systemctl reload clickhouse-server

# 4. Verify new certificate
clickhouse-client --host localhost --port 9440 --secure --query "SELECT 1"
```

### Certificate Expiration Monitoring

Create a monitoring script:

```bash
#!/bin/bash
# check-cert-expiration.sh

# Redis certificate
REDIS_CERT="/etc/redis/ssl/redis-server-cert.pem"
REDIS_DAYS=$(( ($(date -d "$(openssl x509 -in $REDIS_CERT -noout -enddate | cut -d= -f2)" +%s) - $(date +%s)) / 86400 ))

# ClickHouse certificate
CH_CERT="/etc/clickhouse-server/ssl/server-cert.pem"
CH_DAYS=$(( ($(date -d "$(openssl x509 -in $CH_CERT -noout -enddate | cut -d= -f2)" +%s) - $(date +%s)) / 86400 ))

# Alert if expiring within 30 days
if [ $REDIS_DAYS -lt 30 ]; then
    echo "WARNING: Redis certificate expires in $REDIS_DAYS days"
fi

if [ $CH_DAYS -lt 30 ]; then
    echo "WARNING: ClickHouse certificate expires in $CH_DAYS days"
fi

# Add to crontab
# 0 8 * * * /path/to/check-cert-expiration.sh | mail -s "Certificate Expiration Check" admin@example.com
```

---

## Performance Considerations

### TLS Overhead

**Expected Impact:**
- **CPU**: 2-5% increase for TLS encryption/decryption
- **Latency**: 1-3ms additional latency per connection (initial handshake)
- **Throughput**: Minimal impact on bulk operations (<1%)
- **Memory**: ~100KB per TLS connection

### Optimization Tips

1. **Connection Pooling**: Reuse connections to amortize TLS handshake cost
   - Redis: RedisClient already uses connection pooling
   - ClickHouse: Connection pool configured automatically

2. **Session Resumption**: Enable TLS session caching
   ```bash
   # Redis config
   tls-session-caching yes
   tls-session-cache-size 20480
   tls-session-cache-timeout 300
   ```

3. **Hardware Acceleration**: Use AES-NI CPU instructions
   ```bash
   # Check if AES-NI is available
   grep -o aes /proc/cpuinfo
   ```

4. **Strong but Fast Ciphers**: Prefer ChaCha20-Poly1305 or AES-GCM
   ```bash
   # Redis config
   tls-ciphers TLS_CHACHA20_POLY1305_SHA256:TLS_AES_128_GCM_SHA256
   ```

---

## Security Best Practices

### General Guidelines

1. **Use Strong Key Sizes**: Minimum 2048-bit RSA, prefer 4096-bit
2. **Disable Weak Protocols**: No SSLv2, SSLv3, TLS 1.0, TLS 1.1
3. **Enable Perfect Forward Secrecy**: Use ECDHE cipher suites
4. **Regular Certificate Rotation**: Rotate certificates annually
5. **Monitor for Vulnerabilities**: Subscribe to security advisories for Redis/ClickHouse
6. **Restrict Private Key Access**: Use `chmod 600` and limit user access
7. **Separate Environments**: Use different certificates for dev/staging/production
8. **Audit TLS Configuration**: Use tools like `testssl.sh` or `nmap --script ssl-enum-ciphers`

### Production Hardening

```bash
# Redis production configuration
tls-port 6379
port 0  # Disable non-TLS completely
tls-auth-clients yes  # Require client certificates
tls-protocols "TLSv1.3"  # TLS 1.3 only
tls-ciphers TLS_AES_256_GCM_SHA384  # Strongest cipher only
tls-prefer-server-ciphers yes

# ClickHouse production configuration
<verificationMode>strict</verificationMode>  # Require valid client certs
<disableProtocols>sslv2,sslv3,tlsv1,tlsv1_1</disableProtocols>  # TLS 1.2+ only
<cipherList>ECDHE+AESGCM:ECDHE+CHACHA20</cipherList>  # PFS-enabled ciphers
```

---

## Additional Resources

### Documentation

- **Redis TLS**: https://redis.io/docs/manual/security/encryption/
- **ClickHouse TLS**: https://clickhouse.com/docs/en/guides/sre/configuring-ssl
- **OpenSSL**: https://www.openssl.org/docs/

### Tools

- **testssl.sh**: TLS/SSL configuration testing tool
- **Let's Encrypt**: Free automated certificate authority
- **cfssl**: CloudFlare's PKI/TLS toolkit
- **Vault**: HashiCorp's secrets management (for certificate automation)

### Support

For issues related to TLS setup:
1. Check the troubleshooting section above
2. Review application logs with `LOG_LEVEL=DEBUG`
3. Test connections manually with `redis-cli --tls` or `clickhouse-client --secure`
4. Verify certificates with `openssl verify` and `openssl x509 -text`

---

**Last Updated**: 2026-03-07
**Version**: 1.0.0
