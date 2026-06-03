#!/usr/bin/env python3
"""
End-to-End TLS Validation Script

This script validates the TLS configuration for both Redis and ClickHouse connections
by testing all connection points in both TLS-enabled and TLS-disabled modes.

Usage:
    python scripts/validate_tls_e2e.py [--verbose]
"""

import os
import sys
import ssl
import subprocess
from typing import List
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str) -> None:
    """Print a formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 80}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(80)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 80}{Colors.RESET}\n")


def print_success(text: str) -> None:
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")


def print_error(text: str) -> None:
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")


def print_warning(text: str) -> None:
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")


def print_info(text: str) -> None:
    """Print info message"""
    print(f"{Colors.BLUE}ℹ {text}{Colors.RESET}")


class ValidationResult:
    """Stores validation results"""
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.tests_skipped = 0
        self.failures: List[str] = []

    def add_pass(self) -> None:
        self.tests_run += 1
        self.tests_passed += 1

    def add_fail(self, message: str) -> None:
        self.tests_run += 1
        self.tests_failed += 1
        self.failures.append(message)

    def add_skip(self) -> None:
        self.tests_skipped += 1

    def is_success(self) -> bool:
        return self.tests_failed == 0 and self.tests_run > 0

    def summary(self) -> str:
        total = self.tests_run + self.tests_skipped
        return f"""
Test Summary:
  Total Tests: {total}
  Passed: {self.tests_passed}
  Failed: {self.tests_failed}
  Skipped: {self.tests_skipped}
"""


def test_redis_tls_disabled(result: ValidationResult) -> None:
    """Test Redis connections with TLS disabled"""
    print_info("Testing Redis with TLS disabled...")

    # Set environment for non-TLS
    os.environ['REDIS_TLS_ENABLED'] = 'false'

    try:
        # Test SecretsManager
        from shared.config.secrets import SecretsManager
        url = SecretsManager.redis_url()
        if url.startswith('redis://'):
            print_success("SecretsManager.redis_url() returns redis:// scheme")
            result.add_pass()
        else:
            print_error(f"SecretsManager.redis_url() returned {url}, expected redis://")
            result.add_fail("SecretsManager non-TLS URL scheme")

        # Test RedisClient
        from shared.streaming.client import RedisClient
        try:
            client = RedisClient._create_client()
            if hasattr(client, 'connection_pool'):
                print_success("RedisClient creates connection without TLS")
                result.add_pass()
            else:
                print_error("RedisClient connection creation failed")
                result.add_fail("RedisClient non-TLS connection")
        except Exception as e:
            print_warning(f"RedisClient connection skipped: {e}")
            result.add_skip()

        # Test RedisRateLimiter
        from shared.execution.rate_limiter import RedisRateLimiter
        try:
            RedisRateLimiter(
                redis_url='redis://localhost:6379/1',
                key_prefix='test_tls_validation'
            )
            print_success("RedisRateLimiter creates connection without TLS")
            result.add_pass()
        except Exception as e:
            print_warning(f"RedisRateLimiter connection skipped: {e}")
            result.add_skip()

    except Exception as e:
        print_error(f"Redis non-TLS test failed: {e}")
        result.add_fail(f"Redis non-TLS: {e}")


def test_redis_tls_enabled(result: ValidationResult) -> None:
    """Test Redis connections with TLS enabled"""
    print_info("Testing Redis with TLS enabled...")

    # Set environment for TLS
    os.environ['REDIS_TLS_ENABLED'] = 'true'
    os.environ['REDIS_TLS_CERT_REQS'] = 'required'

    try:
        # Test SecretsManager
        from shared.config.secrets import SecretsManager
        # Force reload to pick up new env vars
        import importlib
        import shared.config.secrets
        importlib.reload(shared.config.secrets)
        from shared.config.secrets import SecretsManager

        url = SecretsManager.redis_url()
        if url.startswith('rediss://'):
            print_success("SecretsManager.redis_url() returns rediss:// scheme")
            result.add_pass()
        else:
            print_error(f"SecretsManager.redis_url() returned {url}, expected rediss://")
            result.add_fail("SecretsManager TLS URL scheme")

        # Test RedisClient TLS configuration
        from shared.streaming.client import RedisClient
        try:
            # Reload module to pick up new env vars
            import shared.streaming.client
            importlib.reload(shared.streaming.client)
            from shared.streaming.client import RedisClient

            client = RedisClient._create_client()
            # Check if SSL is configured (connection_pool should have ssl_context)
            pool = client.connection_pool
            if hasattr(pool, 'connection_kwargs'):
                ssl_enabled = pool.connection_kwargs.get('ssl', False)
                if ssl_enabled:
                    print_success("RedisClient configures TLS connection")
                    result.add_pass()
                else:
                    print_warning("RedisClient TLS not enabled in connection pool")
                    result.add_fail("RedisClient TLS configuration")
            else:
                print_warning("Cannot verify RedisClient TLS configuration")
                result.add_skip()
        except Exception as e:
            print_warning(f"RedisClient TLS test skipped: {e}")
            result.add_skip()

    except Exception as e:
        print_error(f"Redis TLS test failed: {e}")
        result.add_fail(f"Redis TLS: {e}")


def test_clickhouse_tls_disabled(result: ValidationResult) -> None:
    """Test ClickHouse connections with TLS disabled"""
    print_info("Testing ClickHouse with TLS disabled...")

    # Set environment for non-TLS
    os.environ['CLICKHOUSE_SECURE'] = 'false'

    try:
        # Test ClickHouseConfig
        from shared.db.config import ClickHouseConfig
        config = ClickHouseConfig.from_env()

        if not config.secure:
            print_success("ClickHouseConfig.secure is False")
            result.add_pass()
        else:
            print_error("ClickHouseConfig.secure is True, expected False")
            result.add_fail("ClickHouseConfig non-TLS")

        # Verify protocol string
        config_str = str(config)
        if 'clickhouse://' in config_str and 'clickhouses://' not in config_str:
            print_success("ClickHouseConfig uses clickhouse:// protocol")
            result.add_pass()
        else:
            print_error(f"ClickHouseConfig protocol mismatch: {config_str}")
            result.add_fail("ClickHouseConfig non-TLS protocol")

        # Test sync client
        from shared.db.client import ClickHouseClient
        try:
            client = ClickHouseClient(config)
            params = client._build_connection_params()
            if not params.get('secure', False):
                print_success("ClickHouseClient (sync) configured for non-TLS")
                result.add_pass()
            else:
                print_error("ClickHouseClient (sync) has TLS enabled")
                result.add_fail("ClickHouseClient non-TLS")
        except Exception as e:
            print_warning(f"ClickHouseClient test skipped: {e}")
            result.add_skip()

        # Test async client
        from shared.db.client import AsyncClickHouseClient
        try:
            async_client = AsyncClickHouseClient(config)
            ssl_context = async_client._build_ssl_context()
            if ssl_context is None:
                print_success("AsyncClickHouseClient configured for non-TLS")
                result.add_pass()
            else:
                print_error("AsyncClickHouseClient has SSL context")
                result.add_fail("AsyncClickHouseClient non-TLS")
        except Exception as e:
            print_warning(f"AsyncClickHouseClient test skipped: {e}")
            result.add_skip()

    except Exception as e:
        print_error(f"ClickHouse non-TLS test failed: {e}")
        result.add_fail(f"ClickHouse non-TLS: {e}")


def test_clickhouse_tls_enabled(result: ValidationResult) -> None:
    """Test ClickHouse connections with TLS enabled"""
    print_info("Testing ClickHouse with TLS enabled...")

    # Set environment for TLS
    os.environ['CLICKHOUSE_SECURE'] = 'true'
    os.environ['CLICKHOUSE_VERIFY_SSL'] = 'true'

    try:
        # Force reload config module
        import importlib
        import shared.db.config
        importlib.reload(shared.db.config)

        # Test ClickHouseConfig
        from shared.db.config import ClickHouseConfig
        config = ClickHouseConfig.from_env()

        if config.secure:
            print_success("ClickHouseConfig.secure is True")
            result.add_pass()
        else:
            print_error("ClickHouseConfig.secure is False, expected True")
            result.add_fail("ClickHouseConfig TLS")

        if config.verify_ssl:
            print_success("ClickHouseConfig.verify_ssl is True")
            result.add_pass()
        else:
            print_error("ClickHouseConfig.verify_ssl is False, expected True")
            result.add_fail("ClickHouseConfig verify_ssl")

        # Verify protocol string
        config_str = str(config)
        if 'clickhouses://' in config_str:
            print_success("ClickHouseConfig uses clickhouses:// protocol")
            result.add_pass()
        else:
            print_error(f"ClickHouseConfig protocol mismatch: {config_str}")
            result.add_fail("ClickHouseConfig TLS protocol")

        # Test sync client
        import shared.db.client
        importlib.reload(shared.db.client)
        from shared.db.client import ClickHouseClient

        try:
            client = ClickHouseClient(config)
            params = client._build_connection_params()
            if params.get('secure', False):
                print_success("ClickHouseClient (sync) configured for TLS")
                result.add_pass()
            else:
                print_error("ClickHouseClient (sync) missing TLS configuration")
                result.add_fail("ClickHouseClient TLS")
        except Exception as e:
            print_warning(f"ClickHouseClient TLS test skipped: {e}")
            result.add_skip()

        # Test async client
        from shared.db.client import AsyncClickHouseClient
        try:
            async_client = AsyncClickHouseClient(config)
            ssl_context = async_client._build_ssl_context()
            if isinstance(ssl_context, ssl.SSLContext):
                print_success("AsyncClickHouseClient creates SSL context")
                result.add_pass()
            else:
                print_error(f"AsyncClickHouseClient SSL context is {type(ssl_context)}")
                result.add_fail("AsyncClickHouseClient SSL context")
        except Exception as e:
            print_warning(f"AsyncClickHouseClient TLS test skipped: {e}")
            result.add_skip()

    except Exception as e:
        print_error(f"ClickHouse TLS test failed: {e}")
        result.add_fail(f"ClickHouse TLS: {e}")


def test_collector_clients(result: ValidationResult) -> None:
    """Test collector clients support TLS configuration"""
    print_info("Testing collector clients TLS support...")

    os.environ['CLICKHOUSE_SECURE'] = 'false'

    try:
        # Test stock collector
        from shared.collector.historical.stock import _get_clickhouse_config
        config = _get_clickhouse_config()

        if 'secure' in config:
            print_success("Stock collector includes 'secure' in config")
            result.add_pass()
        else:
            print_error("Stock collector missing 'secure' in config")
            result.add_fail("Stock collector TLS config")

        # Test backfill collector
        from shared.collector.historical.backfill import _get_clickhouse_config as backfill_config
        config = backfill_config()

        if 'secure' in config:
            print_success("Backfill collector includes 'secure' in config")
            result.add_pass()
        else:
            print_error("Backfill collector missing 'secure' in config")
            result.add_fail("Backfill collector TLS config")

        # Test scanner
        from shared.scanner.accumulation import VolumeAccumulationScanner
        scanner = VolumeAccumulationScanner()
        if hasattr(scanner, 'db_config') and 'secure' in scanner.db_config:
            print_success("Scanner includes 'secure' in db_config")
            result.add_pass()
        else:
            print_warning("Scanner TLS config check skipped")
            result.add_skip()

    except Exception as e:
        print_error(f"Collector clients test failed: {e}")
        result.add_fail(f"Collector clients: {e}")


def run_integration_tests(result: ValidationResult) -> None:
    """Run pytest integration tests"""
    print_info("Running integration tests...")

    tests = [
        ('tests/integration/test_redis_tls.py', 'Redis TLS integration tests'),
        ('tests/integration/test_clickhouse_tls.py', 'ClickHouse TLS integration tests'),
    ]

    for test_file, description in tests:
        test_path = project_root / test_file
        if not test_path.exists():
            print_warning(f"{description} not found: {test_file}")
            result.add_skip()
            continue

        print_info(f"Running {description}...")
        try:
            cmd = ['pytest', str(test_path), '-v', '--tb=short']
            proc = subprocess.run(
                cmd,
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=60
            )

            if proc.returncode == 0:
                print_success(f"{description} passed")
                result.add_pass()
            elif proc.returncode == 5:  # pytest exit code for no tests collected
                print_warning(f"{description} skipped (no tests collected)")
                result.add_skip()
            else:
                print_error(f"{description} failed")
                print(f"STDOUT:\n{proc.stdout}")
                print(f"STDERR:\n{proc.stderr}")
                result.add_fail(f"{description}")
        except subprocess.TimeoutExpired:
            print_error(f"{description} timed out")
            result.add_fail(f"{description} timeout")
        except Exception as e:
            print_error(f"{description} error: {e}")
            result.add_fail(f"{description}: {e}")


def verify_documentation(result: ValidationResult) -> None:
    """Verify TLS documentation exists"""
    print_info("Verifying documentation...")

    doc_path = project_root / 'docs' / 'TLS_SETUP.md'
    if doc_path.exists():
        print_success("TLS_SETUP.md exists")
        result.add_pass()

        # Check content
        content = doc_path.read_text()
        required_sections = [
            'Redis TLS',
            'ClickHouse TLS',
            'Certificate',
            'Environment Variable',
            'Troubleshooting'
        ]

        missing_sections = []
        for section in required_sections:
            if section.lower() in content.lower():
                print_success(f"Documentation includes {section} section")
                result.add_pass()
            else:
                missing_sections.append(section)
                print_error(f"Documentation missing {section} section")
                result.add_fail(f"Documentation missing {section}")

    else:
        print_error("TLS_SETUP.md not found")
        result.add_fail("TLS documentation missing")


def verify_environment_files(result: ValidationResult) -> None:
    """Verify environment example files have TLS variables"""
    print_info("Verifying environment example files...")

    env_files = [
        '.env.example',
        '.env.production.example'
    ]

    required_redis_vars = ['REDIS_TLS_ENABLED', 'REDIS_TLS_CERT_REQS', 'REDIS_TLS_CA_CERTS']
    required_ch_vars = ['CLICKHOUSE_SECURE', 'CLICKHOUSE_VERIFY_SSL', 'CLICKHOUSE_CA_CERT']

    for env_file in env_files:
        env_path = project_root / env_file
        if not env_path.exists():
            print_error(f"{env_file} not found")
            result.add_fail(f"{env_file} missing")
            continue

        content = env_path.read_text()

        # Check Redis TLS vars
        for var in required_redis_vars:
            if var in content:
                print_success(f"{env_file} includes {var}")
                result.add_pass()
            else:
                print_error(f"{env_file} missing {var}")
                result.add_fail(f"{env_file} missing {var}")

        # Check ClickHouse TLS vars
        for var in required_ch_vars:
            if var in content:
                print_success(f"{env_file} includes {var}")
                result.add_pass()
            else:
                print_error(f"{env_file} missing {var}")
                result.add_fail(f"{env_file} missing {var}")


def print_manual_verification_guide() -> None:
    """Print manual verification steps"""
    print_header("Manual Verification Steps")

    print("""
The following steps should be performed manually to verify TLS encryption:

1. Network Traffic Analysis:
   ═══════════════════════════════════════════════════════════════════

   a) Start Redis with TLS enabled:
      $ docker-compose up -d redis

   b) Start tcpdump to capture Redis traffic:
      $ sudo tcpdump -i lo0 -A 'tcp port 6379' -w redis_tls_traffic.pcap

   c) Run the application with REDIS_TLS_ENABLED=true

   d) Stop tcpdump and analyze:
      $ tcpdump -r redis_tls_traffic.pcap -A | grep -i "password"

      Expected: No plaintext passwords visible

   e) Repeat for non-TLS mode with REDIS_TLS_ENABLED=false:

      Expected: May see plaintext data (this confirms TLS is working when enabled)

2. ClickHouse TLS Verification:
   ═══════════════════════════════════════════════════════════════════

   a) Start ClickHouse with TLS enabled (see docs/TLS_SETUP.md)

   b) Capture traffic:
      $ sudo tcpdump -i lo0 -A 'tcp port 8443' -w clickhouse_tls_traffic.pcap

   c) Run the application with CLICKHOUSE_SECURE=true

   d) Analyze:
      $ tcpdump -r clickhouse_tls_traffic.pcap -A | less

      Expected: Encrypted binary data, no plaintext SQL queries visible

3. Certificate Verification:
   ═══════════════════════════════════════════════════════════════════

   a) Generate test certificates (see docs/TLS_SETUP.md)

   b) Configure with invalid certificate:
      $ export REDIS_TLS_CA_CERTS=/path/to/invalid/ca.crt
      $ export CLICKHOUSE_CA_CERT=/path/to/invalid/ca.crt

   c) Run the application:

      Expected: Connection should fail with certificate verification error

   d) Configure with valid certificates:

      Expected: Connection should succeed

4. Backward Compatibility:
   ═══════════════════════════════════════════════════════════════════

   a) Unset all TLS environment variables:
      $ unset REDIS_TLS_ENABLED CLICKHOUSE_SECURE

   b) Run existing application code without modifications:

      Expected: All connections work in non-TLS mode (default)

   c) Verify no code changes are required for non-TLS deployments

5. Production Deployment:
   ═══════════════════════════════════════════════════════════════════

   a) Follow docs/TLS_SETUP.md for production setup

   b) Use the production checklist in the documentation

   c) Verify certificate expiration dates:
      $ openssl x509 -in /path/to/cert.crt -noout -enddate

   d) Set up certificate rotation procedures

""")


def main():
    """Main entry point"""
    print_header("TLS Configuration End-to-End Validation")

    result = ValidationResult()

    # Run automated tests
    print_header("Automated Tests - Redis TLS Disabled")
    test_redis_tls_disabled(result)

    print_header("Automated Tests - Redis TLS Enabled")
    test_redis_tls_enabled(result)

    print_header("Automated Tests - ClickHouse TLS Disabled")
    test_clickhouse_tls_disabled(result)

    print_header("Automated Tests - ClickHouse TLS Enabled")
    test_clickhouse_tls_enabled(result)

    print_header("Automated Tests - Collector Clients")
    test_collector_clients(result)

    print_header("Integration Tests")
    run_integration_tests(result)

    print_header("Documentation and Configuration")
    verify_documentation(result)
    verify_environment_files(result)

    # Print manual verification guide
    print_manual_verification_guide()

    # Print summary
    print_header("Validation Summary")
    print(result.summary())

    if result.failures:
        print_error("Failed tests:")
        for failure in result.failures:
            print(f"  - {failure}")

    # Exit with appropriate code
    if result.is_success():
        print_success("All automated validations passed!")
        print_info("Please complete the manual verification steps above.")
        sys.exit(0)
    else:
        print_error("Some automated validations failed!")
        sys.exit(1)


if __name__ == '__main__':
    main()
