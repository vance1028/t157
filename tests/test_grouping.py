"""分组编排模块测试。"""

import unittest

from event_cleaner.models import Enrollment
from event_cleaner.grouping import assign_groups, normalize_gender


def _mk(row_id, gender='男', preferred='', accessibility=False):
    return Enrollment(
        row_id=row_id, name=f'人{row_id}',
        id_number=f'ID{row_id:018d}', phone=f'138{row_id:08d}',
        gender=gender, preferred_group=preferred,
        accessibility=accessibility,
    )


class TestNormalizeGender(unittest.TestCase):
    def test_male_variants(self):
        for v in ['男', 'M', 'm', 'Male', 'male', ' 男 ']:
            self.assertEqual(normalize_gender(v), '男', f'{v} 应归一为男')

    def test_female_variants(self):
        for v in ['女', 'F', 'f', 'Female', 'female']:
            self.assertEqual(normalize_gender(v), '女', f'{v} 应归一为女')

    def test_unknown(self):
        self.assertEqual(normalize_gender(''), '未知')
        self.assertEqual(normalize_gender('其他'), '未知')


class TestAssignGroups(unittest.TestCase):
    def test_basic_all_assigned(self):
        recs = [_mk(i, gender='男') for i in range(1, 11)]
        result = assign_groups(recs, num_groups=2, max_per_group=10)
        self.assertEqual(result.total_groups, 2)
        self.assertEqual(result.total_members, 10)
        self.assertEqual(len(result.unassigned), 0)
        for g in result.groups:
            self.assertLessEqual(len(g.members), 10)

    def test_max_per_group_honored(self):
        recs = [_mk(i) for i in range(1, 11)]
        result = assign_groups(recs, num_groups=3, max_per_group=3)
        for g in result.groups:
            self.assertLessEqual(len(g.members), 3)
        self.assertGreater(len(result.unassigned), 0)

    def test_preferred_group_respected(self):
        g1, g2, g3 = 'A组', 'B组', 'C组'
        recs = [
            _mk(1, preferred=g1),
            _mk(2, preferred=g2),
            _mk(3, preferred=g3),
        ]
        result = assign_groups(
            recs, num_groups=3, max_per_group=10,
            group_names=[g1, g2, g3],
        )
        member_of_g1 = [m for g in result.groups if g.group_name == g1 for m in g.members]
        self.assertEqual(len(member_of_g1), 1)
        self.assertEqual(member_of_g1[0].row_id, 1)

    def test_accessibility_first(self):
        recs = [
            _mk(1, accessibility=False),
            _mk(2, accessibility=True),
            _mk(3, accessibility=False),
        ]
        result = assign_groups(recs, num_groups=1, max_per_group=2)
        self.assertEqual(len(result.unassigned), 1)
        assigned_ids = [m.row_id for m in result.groups[0].members]
        self.assertIn(2, assigned_ids, '无障碍需求应优先安排')

    def test_gender_balance(self):
        recs = []
        for i in range(1, 21):
            gender = '男' if i <= 10 else '女'
            recs.append(_mk(i, gender=gender))
        result = assign_groups(recs, num_groups=2, max_per_group=20)
        for g in result.groups:
            males = sum(1 for m in g.members if normalize_gender(m.gender) == '男')
            females = sum(1 for m in g.members if normalize_gender(m.gender) == '女')
            self.assertLessEqual(abs(males - females), 3, f'{g.group_name} 男女差距过大: {males} vs {females}')

    def test_deterministic_idempotent(self):
        recs = [_mk(i, gender=('男' if i % 2 else '女'), preferred=('A组' if i % 3 == 0 else ''))
                for i in range(1, 31)]
        names = ['A组', 'B组', 'C组']
        r1 = assign_groups(recs, num_groups=3, max_per_group=15, group_names=names)
        r2 = assign_groups(recs, num_groups=3, max_per_group=15, group_names=names)
        for ga, gb in zip(r1.groups, r2.groups):
            self.assertEqual([m.row_id for m in ga.members], [m.row_id for m in gb.members])
        self.assertEqual([m.row_id for m in r1.unassigned], [m.row_id for m in r2.unassigned])

    def test_stats_populated(self):
        recs = [
            _mk(1, gender='男'),
            _mk(2, gender='女'),
            _mk(3, gender='女', accessibility=True),
        ]
        result = assign_groups(recs, num_groups=1, max_per_group=10)
        stats = result.groups[0].stats
        self.assertEqual(stats['总人数'], 3)
        self.assertEqual(stats['男'], 1)
        self.assertEqual(stats['女'], 2)
        self.assertEqual(stats['无障碍需求'], 1)

    def test_invalid_params(self):
        with self.assertRaises(ValueError):
            assign_groups([], num_groups=0, max_per_group=5)
        with self.assertRaises(ValueError):
            assign_groups([], num_groups=2, max_per_group=0)
        with self.assertRaises(ValueError):
            assign_groups([], num_groups=2, max_per_group=5, group_names=['A'])

    def test_group_names_custom(self):
        names = ['红队', '蓝队']
        result = assign_groups([_mk(1), _mk(2)], num_groups=2, max_per_group=5, group_names=names)
        self.assertEqual([g.group_name for g in result.groups], names)

    def test_default_group_names(self):
        result = assign_groups([_mk(1)], num_groups=3, max_per_group=5)
        self.assertEqual([g.group_name for g in result.groups], ['第1组', '第2组', '第3组'])


if __name__ == '__main__':
    unittest.main()
