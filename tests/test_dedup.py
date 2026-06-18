"""同一人识别与归并模块测试。"""

import unittest

from event_cleaner.models import Enrollment
from event_cleaner.deduplication import dedup_records, get_unique_records
from event_cleaner.normalize import compute_id_check_code


def _mk(id_num, phone, row_id=1, name='', signup='', valid_id=True, valid_phone=True, gender='', preferred=''):
    return Enrollment(
        row_id=row_id, name=name, id_number=id_num, phone=phone,
        gender=gender, preferred_group=preferred, signup_time=signup,
        valid_id=valid_id, valid_phone=valid_phone,
    )


class TestDedup(unittest.TestCase):
    def test_no_duplicates(self):
        id_a = '11010119900101123' + compute_id_check_code('11010119900101123')
        id_b = '11010119900101124' + compute_id_check_code('11010119900101124')
        recs = [
            _mk(id_a, '13800138001', row_id=1, name='A'),
            _mk(id_b, '13800138002', row_id=2, name='B'),
        ]
        report = dedup_records(recs)
        self.assertEqual(report.total_input, 2)
        self.assertEqual(report.total_unique, 2)
        self.assertEqual(report.total_duplicates, 0)
        self.assertEqual(len(report.groups), 2)

    def test_same_id_merged(self):
        id_x = '11010119900101123' + compute_id_check_code('11010119900101123')
        recs = [
            _mk(id_x, '13800138001', row_id=1, name='张三', signup='2025-06-01'),
            _mk(id_x, '13800138001', row_id=2, name='张 三', signup='2025-06-02'),
            _mk(id_x, '13900139000', row_id=3, name='张叁', signup='2025-06-03'),
        ]
        report = dedup_records(recs, keep='earliest')
        self.assertEqual(report.total_unique, 1)
        self.assertEqual(report.total_duplicates, 2)
        self.assertEqual(len(report.groups[0].records), 3)
        self.assertIn('证件号相同', report.groups[0].basis)
        self.assertEqual(report.groups[0].kept.row_id, 1)

    def test_keep_latest(self):
        id_x = '11010119900101123' + compute_id_check_code('11010119900101123')
        recs = [
            _mk(id_x, '13800138001', row_id=1, name='早', signup='2025-06-01'),
            _mk(id_x, '13800138001', row_id=2, name='晚', signup='2025-06-05'),
            _mk(id_x, '13800138001', row_id=3, name='中', signup='2025-06-03'),
        ]
        report = dedup_records(recs, keep='latest')
        self.assertEqual(report.groups[0].kept.row_id, 2)
        self.assertEqual(report.groups[0].kept.name, '晚')

    def test_same_phone_one_missing_id_merged(self):
        id_x = '11010119900101123' + compute_id_check_code('11010119900101123')
        recs = [
            _mk(id_x, '13800138001', row_id=1, name='有证', signup='2025-06-01'),
            _mk('', '13800138001', row_id=2, name='无证', signup='2025-06-02', valid_id=False),
        ]
        report = dedup_records(recs)
        self.assertEqual(report.total_unique, 1)
        self.assertIn('手机号相同', report.groups[0].basis)

    def test_same_phone_but_both_have_different_ids_not_merged(self):
        id_a = '11010119900101123' + compute_id_check_code('11010119900101123')
        id_b = '11010119900101124' + compute_id_check_code('11010119900101124')
        recs = [
            _mk(id_a, '13800138001', row_id=1, name='A'),
            _mk(id_b, '13800138001', row_id=2, name='B'),
        ]
        report = dedup_records(recs)
        self.assertEqual(report.total_unique, 2, '不同证件号即使手机相同也不能误并')

    def test_transitive_merge_via_phone_bridge(self):
        id_x = '11010119900101123' + compute_id_check_code('11010119900101123')
        recs = [
            _mk(id_x, '13800138001', row_id=1, name='主'),
            _mk('', '13800138001', row_id=2, name='桥', valid_id=False),
            _mk('', '13800138001', row_id=3, name='附', valid_id=False),
        ]
        report = dedup_records(recs)
        self.assertEqual(report.total_unique, 1)
        self.assertEqual(len(report.groups[0].records), 3)

    def test_merge_fills_missing_fields(self):
        id_x = '11010119900101123' + compute_id_check_code('11010119900101123')
        recs = [
            _mk(id_x, '13800138001', row_id=1, name='', gender='', signup='2025-06-01'),
            _mk(id_x, '13800138001', row_id=2, name='补名', gender='男', signup='2025-06-02', preferred='第1组'),
        ]
        report = dedup_records(recs, keep='earliest')
        kept = report.groups[0].kept
        self.assertEqual(kept.name, '补名')
        self.assertEqual(kept.gender, '男')

    def test_get_unique_records(self):
        id_a = '11010119900101123' + compute_id_check_code('11010119900101123')
        id_b = '11010119900101124' + compute_id_check_code('11010119900101124')
        recs = [
            _mk(id_a, '13800138001', row_id=1),
            _mk(id_a, '13800138001', row_id=2),
            _mk(id_b, '13800138002', row_id=3),
        ]
        report = dedup_records(recs)
        unique = get_unique_records(report)
        self.assertEqual(len(unique), 2)

    def test_invalid_keep_param(self):
        with self.assertRaises(ValueError):
            dedup_records([], keep='nonsense')

    def test_empty_input(self):
        report = dedup_records([])
        self.assertEqual(report.total_input, 0)
        self.assertEqual(report.total_unique, 0)


if __name__ == '__main__':
    unittest.main()
