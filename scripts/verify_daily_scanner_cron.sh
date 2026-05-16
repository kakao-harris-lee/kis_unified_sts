#!/bin/bash
# Verification script for daily indicator scanner cron job
# Checks: (1) Crontab configuration at 08:50 KST, (2) Redis key population, (3) Data freshness
#
# Usage: ./scripts/verify_daily_scanner_cron.sh

set -e

echo "=========================================="
echo "Daily Indicator Scanner Verification"
echo "=========================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0
WARNINGS=0

# Check 1: Verify cron script exists
echo "✓ Check 1: Cron script files exist"
if [[ -f "scripts/cron/daily_indicator_scanner.sh" ]]; then
    echo -e "${GREEN}  ✓ scripts/cron/daily_indicator_scanner.sh exists${NC}"
else
    echo -e "${RED}  ✗ scripts/cron/daily_indicator_scanner.sh missing${NC}"
    ((ERRORS++))
fi

if [[ -f "scripts/daily_indicator_scanner.py" ]]; then
    echo -e "${GREEN}  ✓ scripts/daily_indicator_scanner.py exists${NC}"
else
    echo -e "${RED}  ✗ scripts/daily_indicator_scanner.py missing${NC}"
    ((ERRORS++))
fi

if [[ -x "scripts/cron/daily_indicator_scanner.sh" ]]; then
    echo -e "${GREEN}  ✓ daily_indicator_scanner.sh is executable${NC}"
else
    echo -e "${RED}  ✗ daily_indicator_scanner.sh is not executable${NC}"
    ((ERRORS++))
fi
echo ""

# Check 2: Verify crontab configuration
echo "✓ Check 2: Crontab configuration"
CRON_ENTRY=$(crontab -l 2>/dev/null | grep -v '^#' | grep daily_indicator_scanner || echo "")

if [[ -n "$CRON_ENTRY" ]]; then
    echo -e "${GREEN}  ✓ Cron job found:${NC}"
    echo "    $CRON_ENTRY"

    # Verify baseline and post-fusion refresh passes are scheduled.
    if echo "$CRON_ENTRY" | grep -q "^50 8"; then
        echo -e "${GREEN}  ✓ Baseline scan scheduled at 08:50${NC}"
    else
        echo -e "${YELLOW}  ⚠ Not scheduled at 08:50 (expected: 50 8 * * 1-5)${NC}"
        ((WARNINGS++))
    fi
    if echo "$CRON_ENTRY" | grep -q "^58 8"; then
        echo -e "${GREEN}  ✓ Dynamic candidate refresh scheduled at 08:58${NC}"
    else
        echo -e "${YELLOW}  ⚠ Not scheduled at 08:58 (expected: 58 8 * * 1-5)${NC}"
        ((WARNINGS++))
    fi

    # Verify it runs Mon-Fri
    if echo "$CRON_ENTRY" | grep -q "1-5"; then
        echo -e "${GREEN}  ✓ Runs Mon-Fri (correct)${NC}"
    else
        echo -e "${YELLOW}  ⚠ Does not specify Mon-Fri (expected: * * 1-5)${NC}"
        ((WARNINGS++))
    fi
else
    echo -e "${RED}  ✗ No cron job found for daily_indicator_scanner${NC}"
    echo -e "${YELLOW}  → Add to crontab with: crontab -e${NC}"
    echo -e "${YELLOW}  → Entries: 50 and 58 8 * * 1-5 $(pwd)/scripts/cron/daily_indicator_scanner.sh${NC}"
    ((ERRORS++))
fi
echo ""

# Check 3: Verify Redis connectivity
echo "✓ Check 3: Redis connectivity"
REDIS_HOST=${REDIS_HOST:-localhost}
REDIS_PORT=${REDIS_PORT:-6379}
REDIS_DB=1

if command -v redis-cli &> /dev/null; then
    if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" ping &> /dev/null; then
        echo -e "${GREEN}  ✓ Redis is accessible at ${REDIS_HOST}:${REDIS_PORT} (DB ${REDIS_DB})${NC}"
    else
        echo -e "${RED}  ✗ Redis not accessible at ${REDIS_HOST}:${REDIS_PORT}${NC}"
        echo -e "${YELLOW}  → Start Redis: docker-compose up -d redis${NC}"
        ((ERRORS++))
    fi
else
    echo -e "${RED}  ✗ redis-cli not found${NC}"
    echo -e "${YELLOW}  → Install redis-cli or use Docker${NC}"
    ((ERRORS++))
fi
echo ""

# Check 4: Verify Redis key exists and has data
echo "✓ Check 4: Redis key population"
REDIS_KEY="system:daily_indicators:latest"

if command -v redis-cli &> /dev/null && redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" ping &> /dev/null; then
    KEY_EXISTS=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" EXISTS "$REDIS_KEY")

    if [[ "$KEY_EXISTS" == "1" ]]; then
        echo -e "${GREEN}  ✓ Redis key '${REDIS_KEY}' exists${NC}"

        # Get the data and parse metadata
        DATA=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" GET "$REDIS_KEY")

        # Extract computed_at timestamp (requires jq)
        if command -v jq &> /dev/null; then
            COMPUTED_AT=$(echo "$DATA" | jq -r '.computed_at' 2>/dev/null || echo "")
            SYMBOL_COUNT=$(echo "$DATA" | jq -r '.symbol_count' 2>/dev/null || echo "")

            if [[ -n "$COMPUTED_AT" ]] && [[ "$COMPUTED_AT" != "null" ]]; then
                echo -e "${GREEN}  ✓ Last computed at: ${COMPUTED_AT}${NC}"

                # Check if data is fresh (within 24 hours)
                COMPUTED_TS=$(date -j -f "%Y-%m-%dT%H:%M:%S" "${COMPUTED_AT:0:19}" "+%s" 2>/dev/null || echo "0")
                NOW_TS=$(date "+%s")
                AGE_HOURS=$(( (NOW_TS - COMPUTED_TS) / 3600 ))

                if [[ $AGE_HOURS -lt 24 ]]; then
                    echo -e "${GREEN}  ✓ Data is fresh (${AGE_HOURS} hours old)${NC}"
                else
                    echo -e "${YELLOW}  ⚠ Data is stale (${AGE_HOURS} hours old, expected < 24)${NC}"
                    ((WARNINGS++))
                fi
            fi

            if [[ -n "$SYMBOL_COUNT" ]] && [[ "$SYMBOL_COUNT" != "null" ]]; then
                echo -e "${GREEN}  ✓ Symbol count: ${SYMBOL_COUNT}${NC}"

                if [[ $SYMBOL_COUNT -ge 20 ]]; then
                    echo -e "${GREEN}  ✓ Sufficient symbols (≥20)${NC}"
                else
                    echo -e "${YELLOW}  ⚠ Low symbol count (${SYMBOL_COUNT}, expected ≥20)${NC}"
                    ((WARNINGS++))
                fi
            fi
        else
            echo -e "${YELLOW}  ⚠ jq not found, cannot parse metadata (install with: brew install jq)${NC}"
            echo "  Data preview (first 200 chars):"
            echo "  $(echo "$DATA" | head -c 200)..."
        fi

        # Check TTL
        TTL=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" TTL "$REDIS_KEY")
        if [[ $TTL -gt 0 ]]; then
            TTL_HOURS=$(( TTL / 3600 ))
            echo -e "${GREEN}  ✓ TTL: ${TTL_HOURS} hours (expires in ${TTL}s)${NC}"
        elif [[ $TTL -eq -1 ]]; then
            echo -e "${YELLOW}  ⚠ Key has no expiration (expected 24h TTL)${NC}"
            ((WARNINGS++))
        fi

    else
        echo -e "${RED}  ✗ Redis key '${REDIS_KEY}' does not exist${NC}"
        echo -e "${YELLOW}  → Run scanner manually: python scripts/daily_indicator_scanner.py${NC}"
        ((ERRORS++))
    fi
else
    echo -e "${YELLOW}  ⚠ Skipping (Redis not accessible)${NC}"
fi
echo ""

# Check 5: Verify scanner can run manually
echo "✓ Check 5: Manual scanner execution test"
if [[ -f ".venv/bin/activate" ]]; then
    echo -e "${GREEN}  ✓ Python virtual environment exists${NC}"

    # Try a dry-run syntax check
    if source .venv/bin/activate && python -m py_compile scripts/daily_indicator_scanner.py 2>/dev/null; then
        echo -e "${GREEN}  ✓ Scanner script syntax is valid${NC}"
    else
        echo -e "${RED}  ✗ Scanner script has syntax errors${NC}"
        ((ERRORS++))
    fi
else
    echo -e "${YELLOW}  ⚠ Virtual environment not found at .venv${NC}"
    echo -e "${YELLOW}  → Create with: python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt${NC}"
    ((WARNINGS++))
fi
echo ""

# Check 6: Verify environment variables
echo "✓ Check 6: Environment configuration"
if [[ -f ".env" ]]; then
    echo -e "${GREEN}  ✓ .env file exists${NC}"

    # Check for required vars (don't print values for security)
    REQUIRED_VARS=("CLICKHOUSE_HOST" "REDIS_HOST" "REDIS_PORT")
    for VAR in "${REQUIRED_VARS[@]}"; do
        if grep -q "^${VAR}=" .env 2>/dev/null; then
            echo -e "${GREEN}  ✓ ${VAR} is configured${NC}"
        else
            echo -e "${YELLOW}  ⚠ ${VAR} not found in .env${NC}"
            ((WARNINGS++))
        fi
    done
else
    echo -e "${YELLOW}  ⚠ .env file not found${NC}"
    echo -e "${YELLOW}  → Copy from template: cp .env.example .env${NC}"
    ((WARNINGS++))
fi
echo ""

# Summary
echo "=========================================="
echo "Verification Summary"
echo "=========================================="

if [[ $ERRORS -eq 0 ]] && [[ $WARNINGS -eq 0 ]]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo ""
    echo "Daily indicator scanner is properly configured and running."
    exit 0
elif [[ $ERRORS -eq 0 ]]; then
    echo -e "${YELLOW}⚠ ${WARNINGS} warning(s) found${NC}"
    echo ""
    echo "Scanner is configured but has minor issues. Review warnings above."
    exit 0
else
    echo -e "${RED}✗ ${ERRORS} error(s), ${WARNINGS} warning(s) found${NC}"
    echo ""
    echo "Scanner setup is incomplete. Fix errors above before proceeding."
    exit 1
fi
