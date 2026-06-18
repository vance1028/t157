"""CSV 读写与整体处理流水线。"""

import csv
import json
import os
from typing import List, Dict, Any, Optional

from .models import (
    Enrollment, InvalidRecord, CleanResult,
    DedupReport, GroupingResult, ProcessResult,
)
from .normalize import normalize_phone, validate_phone, normalize_id, validate_id
from .deduplication import dedup_records, get_unique_records
from .grouping import assign_groups, normalize_gender


CSV_COLUMNS = [
    '姓名', '证件号', '手机号', '性别', '想去的分组', '报名时间', '无障碍需求',
]


def _parse_bool(v: str) -> bool:
    if not v:
        return False
    s = str(v).strip().lower()
    return s in ('1', 'y', 'yes', 'true', '是', '对', '有')


def read_csv(path: str) -> List[Enrollment]:
    """读取报名 CSV。"""
    records: List[Enrollment] = []
    with open(path, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):
            raw = dict(row)
            name = (row.get('姓名') or '').strip()
            id_raw = row.get('证件号') or ''
            phone_raw = row.get('手机号') or ''
            gender = (row.get('性别') or '').strip()
            preferred = (row.get('想去的分组') or '').strip()
            signup = (row.get('报名时间') or '').strip()
            acc = _parse_bool(row.get('无障碍需求') or '')

            id_norm = normalize_id(id_raw)
            phone_norm = normalize_phone(phone_raw)

            rec = Enrollment(
                row_id=i,
                name=name,
                id_number=id_norm,
                phone=phone_norm,
                gender=gender,
                preferred_group=preferred,
                signup_time=signup,
                accessibility=acc,
                raw_data=raw,
            )
            records.append(rec)
    return records


def clean_records(records: List[Enrollment]) -> CleanResult:
    """执行清洗：校验手机号和证件号。"""
    valid: List[Enrollment] = []
    invalid: List[InvalidRecord] = []

    for rec in records:
        errors: List[str] = []
        ok_id, id_errs = validate_id(rec.id_number)
        rec.valid_id = ok_id
        rec.id_errors = id_errs
        errors.extend(id_errs)

        ok_phone, phone_errs = validate_phone(rec.phone)
        rec.valid_phone = ok_phone
        rec.phone_errors = phone_errs
        errors.extend(phone_errs)

        if errors:
            invalid.append(InvalidRecord(record=rec, errors=errors))
        else:
            valid.append(rec)

    return CleanResult(valid_records=valid, invalid_records=invalid)


def write_clean_csv(records: List[Enrollment], path: str):
    """写出清洗去重后的名单 CSV。"""
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            '行号', '姓名', '证件号', '手机号', '性别',
            '想去的分组', '报名时间', '无障碍需求',
        ])
        for rec in records:
            writer.writerow([
                rec.row_id,
                rec.name,
                rec.id_number,
                rec.phone,
                rec.gender,
                rec.preferred_group,
                rec.signup_time,
                '是' if rec.accessibility else '',
            ])


def write_invalid_csv(invalid: List[InvalidRecord], path: str):
    """写出不合法数据清单。"""
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['原行号', '姓名', '证件号', '手机号', '错误信息'])
        for inv in invalid:
            r = inv.record
            writer.writerow([
                r.row_id,
                r.name,
                r.id_number,
                r.phone,
                '; '.join(inv.errors),
            ])


def write_groups_csv(grouping: GroupingResult, path: str):
    """写出分组结果。"""
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['组别', '姓名', '证件号', '手机号', '性别', '意向组', '无障碍'])
        for g in grouping.groups:
            for m in g.members:
                writer.writerow([
                    g.group_name,
                    m.name,
                    m.id_number,
                    m.phone,
                    normalize_gender(m.gender),
                    m.preferred_group,
                    '是' if m.accessibility else '',
                ])
        for m in grouping.unassigned:
            writer.writerow([
                '未分配',
                m.name,
                m.id_number,
                m.phone,
                normalize_gender(m.gender),
                m.preferred_group,
                '是' if m.accessibility else '',
            ])


def report_to_dict(result: ProcessResult) -> Dict[str, Any]:
    """把完整处理结果转成可序列化的 dict。"""
    clean = result.clean_result
    dedup = result.dedup_result
    grouping = result.grouping_result

    groups_rep = []
    for g in dedup.groups:
        groups_rep.append({
            '保留行号': g.kept.row_id,
            '保留姓名': g.kept.name,
            '保留证件号': g.kept.id_number,
            '保留手机号': g.kept.phone,
            '归并依据': g.basis,
            '归并补充字段': g.merged_fields,
            '涉及记录行号': [r.row_id for r in g.records],
        })

    invalid_rep = []
    for inv in clean.invalid_records:
        invalid_rep.append({
            '原行号': inv.record.row_id,
            '姓名': inv.record.name,
            '证件号': inv.record.id_number,
            '手机号': inv.record.phone,
            '错误': inv.errors,
        })

    output: Dict[str, Any] = {
        '清洗': {
            '输入总数': len(clean.valid_records) + len(clean.invalid_records),
            '有效记录数': len(clean.valid_records),
            '不合法记录数': len(clean.invalid_records),
            '不合法清单': invalid_rep,
        },
        '去重': {
            '输入清洗后数': dedup.total_input,
            '唯一人数': dedup.total_unique,
            '合并掉重复': dedup.total_duplicates,
            '归并组详情': groups_rep,
        },
    }

    if grouping:
        grp_rep = []
        for g in grouping.groups:
            grp_rep.append({
                '组名': g.group_name,
                '人数': g.stats.get('总人数', 0),
                '男': g.stats.get('男', 0),
                '女': g.stats.get('女', 0),
                '性别未知': g.stats.get('性别未知', 0),
                '无障碍': g.stats.get('无障碍需求', 0),
                '成员行号': [m.row_id for m in g.members],
            })
        output['分组'] = {
            '组数': grouping.total_groups,
            '已分配人数': grouping.total_members,
            '未分配人数': len(grouping.unassigned),
            '未分配行号': [m.row_id for m in grouping.unassigned],
            '各组详情': grp_rep,
        }

    return output


def report_to_human(result: ProcessResult) -> str:
    """生成人类可读的报告文本。"""
    lines: List[str] = []
    data = report_to_dict(result)

    c = data['清洗']
    lines.append('=' * 60)
    lines.append('【清洗报告】')
    lines.append(f"  输入总数: {c['输入总数']}")
    lines.append(f"  有效记录: {c['有效记录数']}")
    lines.append(f"  不合法记录: {c['不合法记录数']}")
    if c['不合法清单']:
        lines.append('  不合法明细:')
        for inv in c['不合法清单']:
            lines.append(
                f"    行{inv['原行号']} 姓名={inv['姓名']} "
                f"证件={inv['证件号']} 手机={inv['手机号']} "
                f"错误=[{'; '.join(inv['错误'])}]"
            )

    d = data['去重']
    lines.append('')
    lines.append('=' * 60)
    lines.append('【去重报告】')
    lines.append(f"  清洗后输入: {d['输入清洗后数']}")
    lines.append(f"  唯一人数: {d['唯一人数']}")
    lines.append(f"  合并掉重复: {d['合并掉重复']}")
    if d['归并组详情']:
        lines.append('  归并明细:')
        for g in d['归并组详情']:
            lines.append(
                f"    保留行{g['保留行号']}({g['保留姓名']}) "
                f"依据=[{g['归并依据']}] "
                f"涉及行号={g['涉及记录行号']}"
            )
            if g['归并补充字段']:
                lines.append(f"      补充字段: {g['归并补充字段']}")

    if '分组' in data:
        gr = data['分组']
        lines.append('')
        lines.append('=' * 60)
        lines.append('【分组结果】')
        lines.append(f"  组数: {gr['组数']}")
        lines.append(f"  已分配: {gr['已分配人数']}")
        lines.append(f"  未分配: {gr['未分配人数']}")
        for gg in gr['各组详情']:
            lines.append(
                f"  {gg['组名']}: {gg['人数']}人 "
                f"(男{gg['男']} 女{gg['女']} 未知{gg['性别未知']} "
                f"无障碍{gg['无障碍']})"
            )
    lines.append('=' * 60)
    return '\n'.join(lines)


def run_pipeline(
    input_path: str,
    output_dir: str,
    keep: str = 'earliest',
    num_groups: int = 5,
    max_per_group: int = 30,
    group_names: Optional[List[str]] = None,
    skip_grouping: bool = False,
    dry_run: bool = False,
) -> ProcessResult:
    """执行完整流水线。"""
    records = read_csv(input_path)
    clean = clean_records(records)
    dedup = dedup_records(clean.valid_records, keep=keep)
    unique_records = get_unique_records(dedup)
    unique_records.sort(key=lambda r: r.row_id)

    grouping = None
    if not skip_grouping:
        grouping = assign_groups(
            unique_records,
            num_groups=num_groups,
            max_per_group=max_per_group,
            group_names=group_names,
        )

    result = ProcessResult(
        clean_result=clean,
        dedup_result=dedup,
        grouping_result=grouping,
    )

    if not dry_run:
        os.makedirs(output_dir, exist_ok=True)
        write_clean_csv(unique_records, os.path.join(output_dir, 'clean_list.csv'))
        write_invalid_csv(clean.invalid_records, os.path.join(output_dir, 'invalid_records.csv'))
        if grouping:
            write_groups_csv(grouping, os.path.join(output_dir, 'grouping_result.csv'))
        with open(os.path.join(output_dir, 'report.json'), 'w', encoding='utf-8') as f:
            json.dump(report_to_dict(result), f, ensure_ascii=False, indent=2)
        with open(os.path.join(output_dir, 'report.txt'), 'w', encoding='utf-8') as f:
            f.write(report_to_human(result))

    return result
