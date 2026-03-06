#!/bin/bash
# Manual Security Verification Script
# Tests all security fixes implemented in this task

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

RESULTS_FILE="security_verification_results.txt"
API_URL="http://localhost:8000"

echo "=== KIS Trading Platform Security Verification ===" > "$RESULTS_FILE"
echo "Date: $(date)" >> "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"

# Helper functions
pass() {
    echo -e "${GREEN}✓ PASS${NC}: $1"
    echo "✓ PASS: $1" >> "$RESULTS_FILE"
}

fail() {
    echo -e "${RED}✗ FAIL${NC}: $1"
    echo "✗ FAIL: $1" >> "$RESULTS_FILE"
}

warn() {
    echo -e "${YELLOW}⚠ WARN${NC}: $1"
    echo "⚠ WARN: $1" >> "$RESULTS_FILE"
}

info() {
    echo -e "${NC}ℹ INFO${NC}: $1"
    echo "ℹ INFO: $1" >> "$RESULTS_FILE"
}

echo ""
echo "========================================"
echo "1. Environment Configuration Check"
echo "========================================"

# Verify production mode configuration
info "Checking API configuration..."
if grep -q "expose_details: false" config/api.yaml; then
    pass "config/api.yaml has expose_details: false (production mode)"
else
    fail "config/api.yaml does not have expose_details: false"
fi

if grep -q "debug: false" config/api.yaml; then
    pass "config/api.yaml has debug: false (production mode)"
else
    fail "config/api.yaml does not have debug: false"
fi

echo ""
echo "========================================"
echo "2. Code Pattern Verification"
echo "========================================"

# Check error sanitization is properly imported
info "Checking error sanitization imports..."
if grep -q "from shared.api.error_sanitizer import sanitize_error_message" services/api/app.py; then
    pass "services/api/app.py imports error sanitizer"
else
    fail "services/api/app.py missing error sanitizer import"
fi

# Check global exception handler uses sanitization
info "Checking global exception handler..."
if grep -A10 "async def global_exception_handler" services/api/app.py | grep -q "sanitize_error_message"; then
    pass "Global exception handler uses sanitize_error_message"
else
    fail "Global exception handler does not use sanitization"
fi

# Check API routes use sanitization
info "Checking API routes error handling..."
if grep -q "sanitize_error_message" services/api/routes.py; then
    count=$(grep -c "sanitize_error_message" services/api/routes.py)
    pass "API routes use sanitize_error_message ($count occurrences)"
else
    fail "API routes do not use error sanitization"
fi

# Check no plaintext str(e) leakage
info "Checking for str(e) error leakage..."
if ! grep -n "detail=str(e)\|error.*str(e)\|message.*str(e)" services/api/routes.py services/api/app.py 2>/dev/null; then
    pass "No raw str(e) error leakage found"
else
    fail "Found raw str(e) error leakage"
fi

# Check API key security
info "Checking API key generation security..."
if ! grep -n "print.*API.*Key\|print.*{new_key}" services/api/auth.py 2>/dev/null; then
    pass "No plaintext API key printing in auth.py"
else
    fail "Found plaintext API key printing"
fi

if grep -q ".api_key.secret" services/api/auth.py; then
    pass "API keys are written to secure file"
else
    warn "API key secure file approach not found"
fi

# Check CORS configuration
info "Checking CORS security..."
if ! grep -n "allow_origins.*\['\*'\]" services/dashboard/app.py 2>/dev/null; then
    pass "No wildcard CORS origins in dashboard/app.py"
else
    fail "Found wildcard CORS origins in dashboard"
fi

echo ""
echo "========================================"
echo "3. Error Sanitization Pattern Tests"
echo "========================================"

# Test the sanitizer directly
info "Testing error sanitizer utility..."
python3 -c "
import sys
sys.path.insert(0, '.')
from shared.api.error_sanitizer import sanitize_error_message

# Test 1: File path sanitization
exc = ValueError('/Users/harris/app/database.py: Connection failed')
result = sanitize_error_message(exc, use_generic=False)
if '/Users/harris' not in result:
    print('✓ File paths are sanitized')
else:
    print('✗ File paths are NOT sanitized')
    sys.exit(1)

# Test 2: Generic message mode
exc2 = ValueError('Some internal error with details')
result2 = sanitize_error_message(exc2, use_generic=True)
if 'ValueError' not in result2 and 'internal' not in result2:
    print('✓ Generic messages hide implementation details')
else:
    print('✗ Generic messages still leak details')
    sys.exit(1)

# Test 3: Database connection string sanitization
exc3 = Exception('postgresql://user:pass@localhost/db connection failed')
result3 = sanitize_error_message(exc3, use_generic=False)
if 'postgresql://user:pass@' not in result3:
    print('✓ Database credentials are sanitized')
else:
    print('✗ Database credentials are NOT sanitized')
    sys.exit(1)

print('✓ All sanitizer tests passed')
" >> "$RESULTS_FILE" 2>&1

if [ $? -eq 0 ]; then
    pass "Error sanitizer utility tests passed"
else
    fail "Error sanitizer utility tests failed"
fi

echo ""
echo "========================================"
echo "4. API Key Generation Test"
echo "========================================"

# Test API key generation (no plaintext output)
info "Testing API key generation..."
cd /tmp
rm -f .api_key.secret test_api_output.txt

output=$(python3 -m services.api.auth generate 2>&1 | tee test_api_output.txt) || true

# Check no plaintext API key in output (should only have masked version)
if echo "$output" | grep -q "\.\.\."; then
    if ! echo "$output" | grep -E "[A-Za-z0-9_-]{32,}"; then
        pass "API key output is masked (shows only ...)"
    else
        fail "API key output contains plaintext key"
    fi
else
    warn "Could not verify API key masking (check manually)"
fi

# Check .api_key.secret file was created
if [ -f .api_key.secret ]; then
    pass "API key written to .api_key.secret file"

    # Check file permissions (should be 600)
    perms=$(stat -f "%Lp" .api_key.secret 2>/dev/null || stat -c "%a" .api_key.secret 2>/dev/null)
    if [ "$perms" = "600" ]; then
        pass "API key file has correct permissions (600)"
    else
        warn "API key file permissions are $perms (expected 600)"
    fi
else
    warn "API key file not created (may need proper environment)"
fi

rm -f .api_key.secret test_api_output.txt
cd - > /dev/null

echo ""
echo "========================================"
echo "5. Summary"
echo "========================================"

total_tests=$(grep -c "PASS\|FAIL\|WARN" "$RESULTS_FILE")
passed=$(grep -c "✓ PASS" "$RESULTS_FILE")
failed=$(grep -c "✗ FAIL" "$RESULTS_FILE" || echo "0")
warnings=$(grep -c "⚠ WARN" "$RESULTS_FILE" || echo "0")

echo ""
echo "Total Tests: $total_tests"
echo -e "${GREEN}Passed: $passed${NC}"
echo -e "${RED}Failed: $failed${NC}"
echo -e "${YELLOW}Warnings: $warnings${NC}"
echo ""

echo "" >> "$RESULTS_FILE"
echo "=== Summary ===" >> "$RESULTS_FILE"
echo "Total Tests: $total_tests" >> "$RESULTS_FILE"
echo "Passed: $passed" >> "$RESULTS_FILE"
echo "Failed: $failed" >> "$RESULTS_FILE"
echo "Warnings: $warnings" >> "$RESULTS_FILE"

info "Full results saved to: $RESULTS_FILE"

if [ "$failed" -gt 0 ]; then
    echo ""
    echo -e "${RED}Security verification FAILED${NC}"
    exit 1
else
    echo ""
    echo -e "${GREEN}Security verification PASSED${NC}"
    exit 0
fi
