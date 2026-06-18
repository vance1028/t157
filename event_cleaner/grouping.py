"""分组编排模块。

约束：
- 每组人数上限
- 性别尽量均衡
- 尽量满足分组意向
- 无障碍等特殊需求优先安排
- 结果确定（幂等），对同一输入多次运行结果一致
"""

from typing import List, Dict, Optional, Any, Tuple
from collections import defaultdict

from .models import Enrollment, GroupAssignment, GroupingResult


NORMALIZE_GENDER_MAP = {
    '男': '男', 'M': '男', 'm': '男', 'Male': '男', 'male': '男',
    '女': '女', 'F': '女', 'f': '女', 'Female': '女', 'female': '女',
}


def normalize_gender(g: str) -> str:
    """性别归一化。"""
    if not g:
        return '未知'
    return NORMALIZE_GENDER_MAP.get(g.strip(), '未知')


def _build_groups(num_groups: int, group_names: Optional[List[str]] = None) -> List[GroupAssignment]:
    names = group_names or [f'第{i + 1}组' for i in range(num_groups)]
    result: List[GroupAssignment] = []
    for nm in names:
        result.append(GroupAssignment(group_name=nm, members=[], stats={}))
    return result


def _update_stats(group: GroupAssignment):
    total = len(group.members)
    male = sum(1 for m in group.members if normalize_gender(m.gender) == '男')
    female = sum(1 for m in group.members if normalize_gender(m.gender) == '女')
    unknown = total - male - female
    accessibility = sum(1 for m in group.members if m.accessibility)
    group.stats = {
        '总人数': total,
        '男': male,
        '女': female,
        '性别未知': unknown,
        '无障碍需求': accessibility,
    }


def _gender_score(group: GroupAssignment, gender: str) -> float:
    """加入某性别后，该组的性别均衡得分（越低越均衡越优先）。"""
    stats = group.stats
    male = stats.get('男', 0)
    female = stats.get('女', 0)
    total = male + female
    if total == 0:
        return 0.0
    if gender == '男':
        male += 1
    elif gender == '女':
        female += 1
    total += 1
    if total == 0:
        return 0.0
    ratio = male / total
    return abs(ratio - 0.5)


def _pick_best_group(
    groups: List[GroupAssignment],
    preferred: str,
    max_per_group: int,
    gender: str,
) -> Optional[int]:
    """为一个人选择最合适的组。

    优先意向组；意向组满员或不满意向则挑人数最少、性别最均衡的。
    返回组索引，None 表示全都满了。
    """
    available = [i for i, g in enumerate(groups) if len(g.members) < max_per_group]
    if not available:
        return None

    if preferred:
        for i in available:
            if groups[i].group_name == preferred:
                return i

    min_size = min(len(groups[i].members) for i in available)
    candidates = [i for i in available if len(groups[i].members) - min_size <= 1]

    def sort_key(i: int) -> Tuple[float, int, str]:
        g = groups[i]
        return (
            _gender_score(g, gender),
            len(g.members),
            g.group_name,
        )

    available_sorted = sorted(candidates, key=sort_key)
    return available_sorted[0]


def assign_groups(
    records: List[Enrollment],
    num_groups: int,
    max_per_group: int,
    group_names: Optional[List[str]] = None,
) -> GroupingResult:
    """执行分组编排。

    Args:
        records: 去重后的报名记录
        num_groups: 组数
        max_per_group: 每组人数上限
        group_names: 可选的组名列表

    Returns:
        GroupingResult
    """
    if num_groups <= 0:
        raise ValueError('num_groups 必须 > 0')
    if max_per_group <= 0:
        raise ValueError('max_per_group 必须 > 0')
    if group_names and len(group_names) != num_groups:
        raise ValueError('group_names 长度必须等于 num_groups')

    groups = _build_groups(num_groups, group_names)
    for g in groups:
        _update_stats(g)

    sorted_recs = sorted(
        records,
        key=lambda r: (
            0 if r.accessibility else 1,
            0 if r.preferred_group else 1,
            r.row_id,
        ),
    )

    unassigned: List[Enrollment] = []

    for rec in sorted_recs:
        gender = normalize_gender(rec.gender)
        idx = _pick_best_group(groups, rec.preferred_group, max_per_group, gender)
        if idx is None:
            unassigned.append(rec)
        else:
            groups[idx].members.append(rec)
            _update_stats(groups[idx])

    for g in groups:
        g.members.sort(key=lambda r: r.row_id)

    total_members = sum(len(g.members) for g in groups)

    return GroupingResult(
        groups=groups,
        unassigned=unassigned,
        total_members=total_members,
        total_groups=len(groups),
    )
