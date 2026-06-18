"""数据模型定义。"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class Enrollment:
    """单条报名记录。"""
    row_id: int
    name: str = ""
    id_number: str = ""
    phone: str = ""
    gender: str = ""
    preferred_group: str = ""
    signup_time: str = ""
    accessibility: bool = False
    raw_data: Dict[str, str] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        return self.valid_id and self.valid_phone

    valid_id: bool = True
    valid_phone: bool = True
    id_errors: List[str] = field(default_factory=list)
    phone_errors: List[str] = field(default_factory=list)


@dataclass
class DedupGroup:
    """被判为同一人的一组记录。"""
    records: List[Enrollment]
    kept: Enrollment
    basis: str
    merged_fields: Dict[str, str] = field(default_factory=dict)


@dataclass
class DedupReport:
    """去重报告。"""
    total_input: int
    total_unique: int
    total_duplicates: int
    groups: List[DedupGroup]


@dataclass
class InvalidRecord:
    """不合法的记录。"""
    record: Enrollment
    errors: List[str]


@dataclass
class CleanResult:
    """清洗结果。"""
    valid_records: List[Enrollment]
    invalid_records: List[InvalidRecord]


@dataclass
class GroupAssignment:
    """单个分组结果。"""
    group_name: str
    members: List[Enrollment]
    stats: Dict[str, Any]


@dataclass
class GroupingResult:
    """分组编排结果。"""
    groups: List[GroupAssignment]
    unassigned: List[Enrollment]
    total_members: int
    total_groups: int


@dataclass
class ProcessResult:
    """完整处理结果。"""
    clean_result: CleanResult
    dedup_result: DedupReport
    grouping_result: Optional[GroupingResult]
