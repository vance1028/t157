"""CLI 与整体集成测试。"""

import csv
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout

from event_cleaner.pipeline import (
    read_csv, clean_records, run_pipeline,
    report_to_dict, report_to_human,
)
from event_cleaner.cli import main as cli_main
from event_cleaner.normalize import compute_id_check_code


SAMPLE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'samples')
SAMPLE_CSV = os.path.join(SAMPLE_DIR, 'sample_dirty.csv')


def _ensure_sample():
    if not os.path.exists(SAMPLE_CSV):
        from samples.generate_sample import generate_sample
        generate_sample(SAMPLE_CSV)


class TestReadAndClean(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_sample()

    def test_read_sample(self):
        recs = read_csv(SAMPLE_CSV)
        self.assertGreater(len(recs), 15)

    def test_clean_finds_invalid(self):
        recs = read_csv(SAMPLE_CSV)
        result = clean_records(recs)
        self.assertGreater(len(result.invalid_records), 0)
        inv_ids = [r.record.row_id for r in result.invalid_records]
        self.assertTrue(any(
            '校验码' in e or '长度' in e or '号段' in e
            for inv in result.invalid_records for e in inv.errors
        ))


class TestPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_sample()

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='evtest_')

    def tearDown(self):
        if os.path.isdir(self.tmpdir):
            shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_run_produces_files(self):
        result = run_pipeline(
            input_path=SAMPLE_CSV,
            output_dir=self.tmpdir,
            num_groups=3,
            max_per_group=20,
        )
        for fname in ['clean_list.csv', 'invalid_records.csv', 'grouping_result.csv',
                      'report.json', 'report.txt']:
            path = os.path.join(self.tmpdir, fname)
            self.assertTrue(os.path.exists(path), f'{fname} 应被生成')

        with open(os.path.join(self.tmpdir, 'report.json'), 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.assertIn('清洗', data)
        self.assertIn('去重', data)
        self.assertIn('分组', data)
        self.assertGreater(data['去重']['唯一人数'], 0)

    def test_dry_run_writes_nothing(self):
        out_before = set(os.listdir(self.tmpdir)) if os.path.exists(self.tmpdir) else set()
        run_pipeline(
            input_path=SAMPLE_CSV,
            output_dir=self.tmpdir,
            dry_run=True,
        )
        out_after = set(os.listdir(self.tmpdir))
        self.assertEqual(out_before, out_after, 'dry-run 不应写任何文件')

    def test_skip_grouping(self):
        result = run_pipeline(
            input_path=SAMPLE_CSV,
            output_dir=self.tmpdir,
            skip_grouping=True,
        )
        self.assertIsNone(result.grouping_result)
        grouping_csv = os.path.join(self.tmpdir, 'grouping_result.csv')
        self.assertFalse(os.path.exists(grouping_csv))
        with open(os.path.join(self.tmpdir, 'report.json'), 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.assertNotIn('分组', data)

    def test_idempotent_same_result(self):
        run_pipeline(input_path=SAMPLE_CSV, output_dir=self.tmpdir, num_groups=3, max_per_group=20)
        with open(os.path.join(self.tmpdir, 'report.json'), 'r', encoding='utf-8') as f:
            d1 = json.load(f)
        with open(os.path.join(self.tmpdir, 'clean_list.csv'), 'r', encoding='utf-8-sig') as f:
            c1 = f.read()
        with open(os.path.join(self.tmpdir, 'grouping_result.csv'), 'r', encoding='utf-8-sig') as f:
            g1 = f.read()

        shutil.rmtree(self.tmpdir)
        os.makedirs(self.tmpdir)

        run_pipeline(input_path=SAMPLE_CSV, output_dir=self.tmpdir, num_groups=3, max_per_group=20)
        with open(os.path.join(self.tmpdir, 'report.json'), 'r', encoding='utf-8') as f:
            d2 = json.load(f)
        with open(os.path.join(self.tmpdir, 'clean_list.csv'), 'r', encoding='utf-8-sig') as f:
            c2 = f.read()
        with open(os.path.join(self.tmpdir, 'grouping_result.csv'), 'r', encoding='utf-8-sig') as f:
            g2 = f.read()

        self.assertEqual(d1, d2)
        self.assertEqual(c1, c2)
        self.assertEqual(g1, g2)

    def test_reports_sane(self):
        result = run_pipeline(input_path=SAMPLE_CSV, output_dir=self.tmpdir, dry_run=True)
        d = report_to_dict(result)
        self.assertIsInstance(d, dict)
        text = report_to_human(result)
        self.assertIn('清洗报告', text)
        self.assertIn('去重报告', text)
        self.assertIn('分组结果', text)


class TestCLI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_sample()

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='evcli_')

    def tearDown(self):
        if os.path.isdir(self.tmpdir):
            shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_cli_text_output(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli_main([
                '-i', SAMPLE_CSV,
                '-o', self.tmpdir,
                '--dry-run',
                '--format', 'text',
                '--num-groups', '3',
                '--max-per-group', '20',
            ])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn('清洗报告', out)
        self.assertIn('去重报告', out)

    def test_cli_json_output(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli_main([
                '-i', SAMPLE_CSV,
                '-o', self.tmpdir,
                '--dry-run',
                '--format', 'json',
            ])
        self.assertEqual(code, 0)
        data = json.loads(buf.getvalue())
        self.assertIn('清洗', data)

    def test_cli_missing_input(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli_main(['-i', os.path.join(self.tmpdir, 'no_such.csv')])
        self.assertNotEqual(code, 0)

    def test_cli_keep_latest(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli_main([
                '-i', SAMPLE_CSV,
                '-o', self.tmpdir,
                '--keep', 'latest',
                '--dry-run',
                '--skip-grouping',
            ])
        self.assertEqual(code, 0)


if __name__ == '__main__':
    unittest.main()
