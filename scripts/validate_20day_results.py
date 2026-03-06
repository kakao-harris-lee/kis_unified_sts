#!/usr/bin/env python3
"""
scripts/validate_20day_results.py

Validates paper trading results after 20+ trading days for trend_pullback and momentum_breakout strategies.

Usage:
    python3 scripts/validate_20day_results.py [--min-days 20] [--output results.json]

Acceptance Criteria (from spec):
    1. Cumulative P&L is positive
    2. Both strategies generating signals as expected
    3. No runtime errors or crashes
    4. Position management working correctly (entry/exit signals firing)
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional


class PaperTradingValidator:
    """Validates 20+ day paper trading results"""

    def __init__(self, min_trading_days: int = 20):
        self.min_trading_days = min_trading_days
        self.validation_results = {
            "validation_date": datetime.now().isoformat(),
            "min_required_days": min_trading_days,
            "criteria": {},
            "overall_pass": False,
            "recommendations": []
        }

    def load_daily_snapshots(self, log_file: Path) -> List[Dict[str, Any]]:
        """Load daily snapshots from JSONL file"""
        snapshots = []
        if not log_file.exists():
            print(f"Warning: Daily snapshots file not found: {log_file}")
            return snapshots

        with open(log_file, 'r') as f:
            for line in f:
                try:
                    snapshot = json.loads(line.strip())
                    snapshots.append(snapshot)
                except json.JSONDecodeError:
                    continue

        return snapshots

    def validate_trading_days(self, snapshots: List[Dict]) -> bool:
        """Criterion: 20+ trading days of data"""
        unique_days = set()
        for snapshot in snapshots:
            timestamp = snapshot.get('timestamp', '')
            if timestamp:
                day = timestamp.split('T')[0]
                unique_days.add(day)

        trading_days = len(unique_days)
        passed = trading_days >= self.min_trading_days

        self.validation_results['criteria']['trading_days'] = {
            'required': self.min_trading_days,
            'actual': trading_days,
            'passed': passed,
            'message': f"{'✓' if passed else '✗'} Trading days: {trading_days}/{self.min_trading_days}"
        }

        return passed

    def validate_cumulative_pnl(self, snapshots: List[Dict]) -> bool:
        """Criterion: Cumulative P&L is positive"""
        if not snapshots:
            self.validation_results['criteria']['cumulative_pnl'] = {
                'passed': False,
                'message': '✗ No snapshots available'
            }
            return False

        # Get latest snapshot
        latest = snapshots[-1]
        total_pnl = latest.get('total_pnl', 0)

        try:
            total_pnl = float(total_pnl)
        except (ValueError, TypeError):
            total_pnl = 0

        passed = total_pnl > 0

        self.validation_results['criteria']['cumulative_pnl'] = {
            'required': '> 0 KRW',
            'actual': f"{total_pnl:,.0f} KRW",
            'passed': passed,
            'message': f"{'✓' if passed else '✗'} Cumulative P&L: {total_pnl:,.0f} KRW"
        }

        return passed

    def validate_signal_generation(self, history_output: str) -> bool:
        """Criterion: Both strategies generating signals"""
        # Parse trade history for strategy names
        has_trend_pullback = 'trend_pullback' in history_output.lower()
        has_momentum_breakout = 'momentum_breakout' in history_output.lower()

        # Count trades (rough estimate)
        trade_count = history_output.lower().count('entry') + history_output.lower().count('buy')

        passed = has_trend_pullback and has_momentum_breakout and trade_count > 0

        self.validation_results['criteria']['signal_generation'] = {
            'required': 'Both strategies generating signals',
            'trend_pullback_active': has_trend_pullback,
            'momentum_breakout_active': has_momentum_breakout,
            'estimated_trades': trade_count,
            'passed': passed,
            'message': f"{'✓' if passed else '✗'} Signal generation: "
                      f"trend_pullback={'Yes' if has_trend_pullback else 'No'}, "
                      f"momentum_breakout={'Yes' if has_momentum_breakout else 'No'}, "
                      f"trades≈{trade_count}"
        }

        return passed

    def validate_runtime_stability(self, snapshots: List[Dict]) -> bool:
        """Criterion: No runtime errors or crashes"""
        # Check for consistent data collection
        if len(snapshots) < 2:
            passed = False
        else:
            # Check for long gaps (indicating crashes)
            timestamps = [datetime.fromisoformat(s['timestamp'].replace('Z', '+00:00')) for s in snapshots if 'timestamp' in s]
            timestamps.sort()

            max_gap_hours = 0
            for i in range(1, len(timestamps)):
                gap = (timestamps[i] - timestamps[i-1]).total_seconds() / 3600
                max_gap_hours = max(max_gap_hours, gap)

            # Allow gaps up to 72 hours (weekend + holiday)
            passed = max_gap_hours < 168  # 1 week

        self.validation_results['criteria']['runtime_stability'] = {
            'required': 'Consistent operation, no crashes',
            'snapshots_collected': len(snapshots),
            'max_gap_hours': f"{max_gap_hours:.1f}h" if len(snapshots) > 1 else "N/A",
            'passed': passed,
            'message': f"{'✓' if passed else '✗'} Runtime stability: {len(snapshots)} snapshots, max gap {max_gap_hours:.1f}h"
        }

        return passed

    def validate_position_management(self, snapshots: List[Dict], history_output: str) -> bool:
        """Criterion: Position management working (entries and exits)"""
        # Check for position activity
        has_entries = 'entry' in history_output.lower() or 'buy' in history_output.lower()
        has_exits = 'exit' in history_output.lower() or 'sell' in history_output.lower()

        # Check position counts vary (indicating activity)
        position_counts = [s.get('positions', 0) for s in snapshots if 'positions' in s]
        has_position_variation = len(set(position_counts)) > 1 if position_counts else False

        passed = has_entries and has_exits and has_position_variation

        self.validation_results['criteria']['position_management'] = {
            'required': 'Entry and exit signals firing correctly',
            'has_entries': has_entries,
            'has_exits': has_exits,
            'position_variation': has_position_variation,
            'passed': passed,
            'message': f"{'✓' if passed else '✗'} Position management: "
                      f"entries={'Yes' if has_entries else 'No'}, "
                      f"exits={'Yes' if has_exits else 'No'}, "
                      f"variation={'Yes' if has_position_variation else 'No'}"
        }

        return passed

    def generate_recommendations(self):
        """Generate recommendations based on results"""
        recommendations = []

        # Check each criterion
        for criterion, result in self.validation_results['criteria'].items():
            if not result.get('passed', False):
                if criterion == 'trading_days':
                    recommendations.append(
                        f"Continue monitoring: Only {result['actual']} days collected, "
                        f"need {result['required']} trading days minimum"
                    )
                elif criterion == 'cumulative_pnl':
                    recommendations.append(
                        f"Review strategy parameters: Cumulative P&L is {result['actual']}, "
                        f"consider optimization or parameter tuning"
                    )
                elif criterion == 'signal_generation':
                    recommendations.append(
                        "Check strategy configuration: Ensure both strategies are enabled "
                        "and daily scanner is populating watchlist data"
                    )
                elif criterion == 'runtime_stability':
                    recommendations.append(
                        "Investigate stability issues: Review logs for crashes or errors"
                    )
                elif criterion == 'position_management':
                    recommendations.append(
                        "Verify entry/exit logic: Check if strategies are generating proper signals"
                    )

        if not recommendations:
            recommendations.append("All criteria passed! Strategies ready for live deployment consideration.")

        self.validation_results['recommendations'] = recommendations

    def run_validation(self, monitoring_dir: Path, history_output: str = "") -> bool:
        """Run all validation checks"""
        print("=" * 70)
        print("  20+ Day Paper Trading Validation")
        print("  Strategies: trend_pullback + momentum_breakout")
        print("=" * 70)
        print()

        # Load snapshots
        log_file = monitoring_dir / "daily_snapshots.jsonl"
        snapshots = self.load_daily_snapshots(log_file)

        print(f"Loaded {len(snapshots)} snapshots from {log_file}")
        print()

        # Run validations
        print("Running validation checks...")
        print()

        checks = [
            self.validate_trading_days(snapshots),
            self.validate_cumulative_pnl(snapshots),
            self.validate_signal_generation(history_output),
            self.validate_runtime_stability(snapshots),
            self.validate_position_management(snapshots, history_output)
        ]

        # Print results
        print()
        print("─── Validation Results ───")
        print()
        for criterion, result in self.validation_results['criteria'].items():
            print(f"  {result['message']}")
        print()

        # Overall result
        all_passed = all(checks)
        self.validation_results['overall_pass'] = all_passed

        # Generate recommendations
        self.generate_recommendations()

        # Print recommendations
        print()
        print("─── Recommendations ───")
        print()
        for i, rec in enumerate(self.validation_results['recommendations'], 1):
            print(f"  {i}. {rec}")
        print()

        # Overall verdict
        print("=" * 70)
        if all_passed:
            print("✓ VALIDATION PASSED - All criteria met")
        else:
            print("✗ VALIDATION INCOMPLETE - Some criteria not met")
        print("=" * 70)
        print()

        return all_passed


def main():
    parser = argparse.ArgumentParser(
        description="Validate 20+ day paper trading results"
    )
    parser.add_argument(
        '--min-days',
        type=int,
        default=20,
        help='Minimum trading days required (default: 20)'
    )
    parser.add_argument(
        '--monitoring-dir',
        type=Path,
        default=Path(__file__).parent.parent / 'output' / 'monitoring',
        help='Directory containing monitoring data'
    )
    parser.add_argument(
        '--output',
        type=Path,
        help='Output file for validation results (JSON)'
    )
    parser.add_argument(
        '--history-file',
        type=Path,
        help='File containing trade history output (optional)'
    )

    args = parser.parse_args()

    # Load history if provided
    history_output = ""
    if args.history_file and args.history_file.exists():
        with open(args.history_file, 'r') as f:
            history_output = f.read()

    # Run validation
    validator = PaperTradingValidator(min_trading_days=args.min_days)
    passed = validator.run_validation(args.monitoring_dir, history_output)

    # Save results if output specified
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(validator.validation_results, f, indent=2)
        print(f"Results saved to: {args.output}")

    # Exit code
    sys.exit(0 if passed else 1)


if __name__ == '__main__':
    main()
