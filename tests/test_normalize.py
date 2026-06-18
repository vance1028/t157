"""归一化与校验模块测试。"""

import unittest

from event_cleaner.normalize import (
    normalize_phone, validate_phone,
    normalize_id, validate_id, compute_id_check_code,
)


class TestNormalizePhone(unittest.TestCase):
    def test_plain_phone(self):
        self.assertEqual(normalize_phone('13800138000'), '13800138000')

    def test_with_hyphens(self):
        self.assertEqual(normalize_phone('138-0013-8000'), '13800138000')

    def test_with_spaces(self):
        self.assertEqual(normalize_phone('138 0013 8000'), '13800138000')

    def test_fullwidth_digits(self):
        self.assertEqual(normalize_phone('１３８００１３８０００'), '13800138000')

    def test_mixed_noise(self):
        self.assertEqual(normalize_phone('（１３8）００１3-８000 '), '13800138000')

    def test_none_and_empty(self):
        self.assertEqual(normalize_phone(None), '')
        self.assertEqual(normalize_phone(''), '')


class TestValidatePhone(unittest.TestCase):
    def test_valid(self):
        ok, errs = validate_phone('13800138000')
        self.assertTrue(ok)
        self.assertEqual(errs, [])

    def test_valid_199_prefix(self):
        ok, _ = validate_phone('19900138000')
        self.assertTrue(ok)

    def test_empty(self):
        ok, errs = validate_phone('')
        self.assertFalse(ok)
        self.assertIn('空', errs[0])

    def test_too_short(self):
        ok, errs = validate_phone('1380013')
        self.assertFalse(ok)
        self.assertIn('长度', errs[0])

    def test_too_long(self):
        ok, errs = validate_phone('138001380000')
        self.assertFalse(ok)

    def test_contains_letter(self):
        ok, errs = validate_phone('1380013800A')
        self.assertFalse(ok)
        self.assertIn('数字', errs[0])

    def test_invalid_prefix(self):
        ok, errs = validate_phone('00000000000')
        self.assertFalse(ok)
        self.assertIn('号段', errs[0])

    def test_invalid_prefix_123(self):
        ok, errs = validate_phone('12300138000')
        self.assertFalse(ok)


class TestNormalizeId(unittest.TestCase):
    def test_plain_18(self):
        self.assertEqual(normalize_id('110101199001011234'), '110101199001011234')

    def test_lowercase_x_becomes_upper(self):
        self.assertEqual(normalize_id('11010119900101123x'), '11010119900101123X')

    def test_with_spaces(self):
        self.assertEqual(normalize_id('110101 19900101 1234'), '110101199001011234')

    def test_fullwidth(self):
        self.assertEqual(normalize_id('１１０１０１１９９００１０１１２３X'), '11010119900101123X')

    def test_mixed(self):
        self.assertEqual(
            normalize_id('１１０１０1-1990 0101_123x'),
            '11010119900101123X',
        )

    def test_none_and_empty(self):
        self.assertEqual(normalize_id(None), '')
        self.assertEqual(normalize_id(''), '')


class TestComputeIdCheckCode(unittest.TestCase):
    def test_known_case(self):
        self.assertEqual(compute_id_check_code('11010119900101123'), '7')
        self.assertEqual(compute_id_check_code('11010119900307221'), 'X')
        self.assertEqual(compute_id_check_code('44030119900101001'), '2')

    def test_invalid_input_len(self):
        with self.assertRaises(ValueError):
            compute_id_check_code('123')

    def test_invalid_input_non_digit(self):
        with self.assertRaises(ValueError):
            compute_id_check_code('1101011990010112X')


class TestValidateId(unittest.TestCase):
    def _valid_18(self, prefix17: str) -> str:
        return prefix17 + compute_id_check_code(prefix17)

    def test_valid_18(self):
        idn = self._valid_18('11010119900101123')
        ok, errs = validate_id(idn)
        self.assertTrue(ok, f'{idn} 应该合法，错误={errs}')
        self.assertEqual(errs, [])

    def test_valid_15(self):
        ok, errs = validate_id('110101900101123')
        self.assertTrue(ok)
        self.assertEqual(errs, [])

    def test_empty(self):
        ok, errs = validate_id('')
        self.assertFalse(ok)

    def test_wrong_length(self):
        ok, errs = validate_id('1234567890')
        self.assertFalse(ok)
        self.assertIn('长度', errs[0])

    def test_18_wrong_checksum(self):
        good = self._valid_18('11010119900101123')
        bad = good[:-1] + ('0' if good[-1] != '0' else '1')
        ok, errs = validate_id(bad)
        self.assertFalse(ok, f'{bad} 校验码应该错误')
        self.assertTrue(any('校验码' in e for e in errs))

    def test_18_non_digit_prefix(self):
        ok, errs = validate_id('11010119900101A23X')
        self.assertFalse(ok)
        self.assertTrue(any('前17位' in e for e in errs))

    def test_18_invalid_last_char(self):
        ok, errs = validate_id('11010119900101123Y')
        self.assertFalse(ok)

    def test_15_non_digit(self):
        ok, errs = validate_id('11010190010112X')
        self.assertFalse(ok)


if __name__ == '__main__':
    unittest.main()
