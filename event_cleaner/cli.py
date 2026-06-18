"""命令行入口。"""

import argparse
import json
import sys
from typing import List, Optional

from .pipeline import run_pipeline, report_to_dict, report_to_human


def _parse_group_names(s: Optional[str]) -> Optional[List[str]]:
    if not s:
        return None
    return [x.strip() for x in s.split(',') if x.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='event-cleaner',
        description='活动报名数据清洗、去重、分组一条龙工具（纯本地离线）',
    )
    parser.add_argument('-i', '--input', required=True, help='报名 CSV 文件路径')
    parser.add_argument('-o', '--output-dir', default='./output', help='输出目录（默认 ./output）')
    parser.add_argument(
        '--keep', choices=['earliest', 'latest'], default='earliest',
        help='重复记录保留规则：earliest=最早一条，latest=最新一条（默认 earliest）',
    )
    parser.add_argument('--num-groups', type=int, default=5, help='分组数（默认 5）')
    parser.add_argument('--max-per-group', type=int, default=30, help='每组人数上限（默认 30）')
    parser.add_argument(
        '--group-names', type=str, default=None,
        help='自定义组名，逗号分隔，数量须等于 --num-groups',
    )
    parser.add_argument('--skip-grouping', action='store_true', help='只清洗去重，不做分组')
    parser.add_argument(
        '--format', choices=['text', 'json'], default='text',
        dest='report_format', help='控制台报告格式（默认 text）',
    )
    parser.add_argument('--dry-run', action='store_true', help='只出报告不写文件')
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    group_names = _parse_group_names(args.group_names)

    try:
        result = run_pipeline(
            input_path=args.input,
            output_dir=args.output_dir,
            keep=args.keep,
            num_groups=args.num_groups,
            max_per_group=args.max_per_group,
            group_names=group_names,
            skip_grouping=args.skip_grouping,
            dry_run=args.dry_run,
        )
    except FileNotFoundError as e:
        print(f'错误：找不到文件 {e}', file=sys.stderr)
        return 2
    except ValueError as e:
        print(f'参数错误：{e}', file=sys.stderr)
        return 2

    if args.report_format == 'json':
        print(json.dumps(report_to_dict(result), ensure_ascii=False, indent=2))
    else:
        print(report_to_human(result))

    return 0


if __name__ == '__main__':
    sys.exit(main())
