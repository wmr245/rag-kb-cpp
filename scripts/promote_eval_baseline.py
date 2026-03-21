#!/usr/bin/env python3
import argparse
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / 'eval' / 'reports'
BASELINE_DIR = ROOT / 'eval' / 'baselines'


def load_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def find_latest_report(suite_id: str) -> Path:
    candidates = sorted(REPORT_DIR.glob(f'{suite_id}-*.json'))
    if not candidates:
        raise FileNotFoundError(f'no reports found for suite: {suite_id}')
    return candidates[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description='Promote an evaluation report to the suite baseline alias')
    parser.add_argument('--suite', required=True, choices=['small', 'medium', 'large', 'longlite', 'xlarge'])
    parser.add_argument('--report', help='specific report path to promote')
    args = parser.parse_args()

    report_path = Path(args.report).expanduser().resolve() if args.report else find_latest_report(args.suite)
    if not report_path.exists():
        raise FileNotFoundError(f'report not found: {report_path}')

    report = load_report(report_path)
    suite_id = report.get('suiteId')
    if suite_id != args.suite:
        raise ValueError(f'suite mismatch: expected {args.suite}, got {suite_id}')

    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    target = BASELINE_DIR / f'{args.suite}.json'
    shutil.copyfile(report_path, target)
    print(f'[baseline] {target}')
    print(f'[source] {report_path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
