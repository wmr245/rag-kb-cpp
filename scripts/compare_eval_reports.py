#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

from run_eval import build_comparison, format_comparison_lines, load_report


def main() -> int:
    parser = argparse.ArgumentParser(description='Compare two evaluation reports')
    parser.add_argument('--baseline', required=True, help='baseline report path')
    parser.add_argument('--current', required=True, help='current report path')
    parser.add_argument('--report-out', help='optional output path for compare JSON')
    parser.add_argument('--fail-on-regression', action='store_true', help='return non-zero if regressions are found')
    args = parser.parse_args()

    baseline = load_report(args.baseline)
    current = load_report(args.current)
    baseline['_reportPath'] = str(Path(args.baseline).expanduser().resolve())
    current['_reportPath'] = str(Path(args.current).expanduser().resolve())

    comparison = build_comparison(current, baseline)
    for line in format_comparison_lines(comparison):
        print(line)

    if args.report_out:
        report_path = Path(args.report_out).expanduser().resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'[compare-report] {report_path}')

    if args.fail_on_regression and comparison.get('regressionCount', 0) > 0:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
