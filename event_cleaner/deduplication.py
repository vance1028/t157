"""同一人识别与归并。

策略：
- 证件号是强标识：有相同有效证件号的一定是同一人
- 手机号是弱标识：仅在一方缺失证件号时用来辅助匹配
- 通过并查集处理传递性关系
- 保留规则可配置：keep="earliest" 保留最早报名，keep="latest" 保留最新
"""

from typing import List, Dict, Optional

from .models import Enrollment, DedupGroup, DedupReport


class _UnionFind:
    """并查集，用于处理传递性的同人归并。"""

    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x: int, y: int):
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self.rank[rx] < self.rank[ry]:
            self.parent[rx] = ry
        elif self.rank[rx] > self.rank[ry]:
            self.parent[ry] = rx
        else:
            self.parent[ry] = rx
            self.rank[rx] += 1


def _sort_key_earliest(rec: Enrollment):
    """按最早报名排序的键。"""
    return (rec.signup_time or '9999', rec.row_id)


def _sort_key_latest(rec: Enrollment):
    """按最新报名排序的键。"""
    return ('' if not rec.signup_time else ''.join(
        c for c in rec.signup_time if c.isdigit() or c in '-:.T '
    ) or '0000', rec.row_id)


def _pick_kept(records: List[Enrollment], keep: str) -> Enrollment:
    """按保留规则挑一条主记录。"""
    if keep == 'latest':
        sorted_recs = sorted(records, key=_sort_key_latest, reverse=True)
    else:
        sorted_recs = sorted(records, key=_sort_key_earliest)
    return sorted_recs[0]


def _merge_fields(records: List[Enrollment], kept: Enrollment) -> Dict[str, str]:
    """归并字段：保留主记录，缺失字段从其他记录补充。"""
    merged: Dict[str, str] = {}

    fields = ['name', 'gender', 'preferred_group']
    for f in fields:
        val = getattr(kept, f)
        if not val:
            for r in records:
                if r is kept:
                    continue
                candidate = getattr(r, f)
                if candidate:
                    merged[f] = candidate
                    break
    return merged


def dedup_records(records: List[Enrollment], keep: str = 'earliest') -> DedupReport:
    """去重归并。

    Args:
        records: 已清洗过的报名记录
        keep: 'earliest' 保留最早一条；'latest' 保留最新一条

    Returns:
        DedupReport 包含归并信息
    """
    if keep not in ('earliest', 'latest'):
        raise ValueError(f"keep 必须是 'earliest' 或 'latest'，得到 {keep}")

    n = len(records)
    if n == 0:
        return DedupReport(total_input=0, total_unique=0, total_duplicates=0, groups=[])

    uf = _UnionFind(n)

    id_to_idx: Dict[str, List[int]] = {}
    phone_to_idx: Dict[str, List[int]] = {}

    for i, rec in enumerate(records):
        if rec.id_number and rec.valid_id:
            id_to_idx.setdefault(rec.id_number, []).append(i)
        if rec.phone and rec.valid_phone:
            phone_to_idx.setdefault(rec.phone, []).append(i)

    union_pairs: List[tuple] = []
    union_basis: Dict[tuple, str] = {}

    for id_num, idxs in id_to_idx.items():
        for j in range(1, len(idxs)):
            a, b = idxs[0], idxs[j]
            key = (min(a, b), max(a, b))
            union_pairs.append(key)
            union_basis[key] = f'证件号相同: {id_num}'

    for phone, idxs in phone_to_idx.items():
        if len(idxs) < 2:
            continue
        for j in range(len(idxs)):
            for k in range(j + 1, len(idxs)):
                a, b = idxs[j], idxs[k]
                rec_a = records[a]
                rec_b = records[b]
                if rec_a.id_number and rec_a.valid_id and rec_b.id_number and rec_b.valid_id:
                    continue
                key = (min(a, b), max(a, b))
                union_pairs.append(key)
                if key not in union_basis:
                    reason_parts = [f'手机号相同: {phone}']
                    missing = []
                    if not (rec_a.id_number and rec_a.valid_id):
                        missing.append(f'第{rec_a.row_id}行无有效证件号')
                    if not (rec_b.id_number and rec_b.valid_id):
                        missing.append(f'第{rec_b.row_id}行无有效证件号')
                    if missing:
                        reason_parts.append('(' + ', '.join(missing) + ')')
                    union_basis[key] = ' '.join(reason_parts)

    for a, b in union_pairs:
        uf.union(a, b)

    root_to_members: Dict[int, List[int]] = {}
    root_to_basis: Dict[int, List[str]] = {}
    for i in range(n):
        root = uf.find(i)
        root_to_members.setdefault(root, []).append(i)

    for (a, b), basis in union_basis.items():
        root = uf.find(a)
        root_to_basis.setdefault(root, [])
        if basis not in root_to_basis[root]:
            root_to_basis[root].append(basis)

    groups: List[DedupGroup] = []
    total_unique = len(root_to_members)
    total_duplicates = n - total_unique

    for root, members in root_to_members.items():
        member_recs = [records[i] for i in members]
        member_recs_sorted = sorted(member_recs, key=lambda r: r.row_id)
        kept = _pick_kept(member_recs_sorted, keep)
        basis_list = root_to_basis.get(root, [])
        basis = '; '.join(basis_list) if basis_list else '单条记录无重复'
        merged = _merge_fields(member_recs_sorted, kept)

        if merged:
            for f, v in merged.items():
                setattr(kept, f, v)

        groups.append(DedupGroup(
            records=member_recs_sorted,
            kept=kept,
            basis=basis,
            merged_fields=merged,
        ))

    groups.sort(key=lambda g: g.kept.row_id)

    return DedupReport(
        total_input=n,
        total_unique=total_unique,
        total_duplicates=total_duplicates,
        groups=groups,
    )


def get_unique_records(report: DedupReport) -> List[Enrollment]:
    """从去重报告中取出去重后的唯一记录列表。"""
    return [g.kept for g in report.groups]
