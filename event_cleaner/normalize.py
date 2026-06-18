"""手机号与证件号的归一化和校验。

纯逻辑模块，不依赖文件读写或CLI。
"""

import re
from typing import List, Tuple


_FULL_WIDTH_MAP = {
    '０': '0', '１': '1', '２': '2', '３': '3', '４': '4',
    '５': '5', '６': '6', '７': '7', '８': '8', '９': '9',
    '－': '-', '（': '(', '）': ')', '　': ' ',
    'ａ': 'a', 'ｂ': 'b', 'ｃ': 'c', 'ｄ': 'd', 'ｅ': 'e',
    'ｆ': 'f', 'ｇ': 'g', 'ｈ': 'h', 'ｉ': 'i', 'ｊ': 'j',
    'ｋ': 'k', 'ｌ': 'l', 'ｍ': 'm', 'ｎ': 'n', 'ｏ': 'o',
    'ｐ': 'p', 'ｑ': 'q', 'ｒ': 'r', 'ｓ': 's', 'ｔ': 't',
    'ｕ': 'u', 'ｖ': 'v', 'ｗ': 'w', 'ｘ': 'x', 'ｙ': 'y',
    'ｚ': 'z',
    'Ａ': 'A', 'Ｂ': 'B', 'Ｃ': 'C', 'Ｄ': 'D', 'Ｅ': 'E',
    'Ｆ': 'F', 'Ｇ': 'G', 'Ｈ': 'H', 'Ｉ': 'I', 'Ｊ': 'J',
    'Ｋ': 'K', 'Ｌ': 'L', 'Ｍ': 'M', 'Ｎ': 'N', 'Ｏ': 'O',
    'Ｐ': 'P', 'Ｑ': 'Q', 'Ｒ': 'R', 'Ｓ': 'S', 'Ｔ': 'T',
    'Ｕ': 'U', 'Ｖ': 'V', 'Ｗ': 'W', 'Ｘ': 'X', 'Ｙ': 'Y',
    'Ｚ': 'Z',
}

_VALID_MOBILE_PREFIXES = {
    '130', '131', '132', '133', '134', '135', '136', '137', '138', '139',
    '150', '151', '152', '153', '155', '156', '157', '158', '159',
    '170', '171', '172', '173', '175', '176', '177', '178',
    '180', '181', '182', '183', '184', '185', '186', '187', '188', '189',
    '190', '191', '192', '193', '195', '196', '197', '198', '199',
    '145', '147', '149',
    '162', '165', '166', '167',
}

_ID_WEIGHTS = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
_ID_CHECK_CODES = ['1', '0', 'X', '9', '8', '7', '6', '5', '4', '3', '2']


def _fullwidth_to_halfwidth(text: str) -> str:
    """全角字符转半角。"""
    if not text:
        return text
    return ''.join(_FULL_WIDTH_MAP.get(ch, ch) for ch in text)


def _strip_noise(text: str) -> str:
    """去掉空格、连字符、括号等干扰字符。"""
    if not text:
        return text
    return re.sub(r'[\s\-()（）＿_/\\、]', '', text)


def normalize_phone(raw: str) -> str:
    """手机号归一化。

    处理：全角→半角、去掉空格/连字符等、统一为数字串。
    """
    if raw is None:
        return ''
    result = str(raw)
    result = _fullwidth_to_halfwidth(result)
    result = _strip_noise(result)
    return result.strip()


def validate_phone(phone: str) -> Tuple[bool, List[str]]:
    """手机号校验。

    规则：
    - 11 位纯数字
    - 号段在允许范围内
    """
    errors: List[str] = []
    if not phone:
        errors.append('手机号为空')
        return False, errors
    if len(phone) != 11:
        errors.append(f'手机号长度应为11位，实际{len(phone)}位')
        return False, errors
    if not phone.isdigit():
        errors.append('手机号必须全为数字')
        return False, errors
    prefix = phone[:3]
    if prefix not in _VALID_MOBILE_PREFIXES:
        errors.append(f'手机号号段{prefix}不合法')
        return False, errors
    return True, errors


def normalize_id(raw: str) -> str:
    """身份证号归一化。

    处理：全角→半角、去掉空格/连字符等、字母统一为大写。
    """
    if raw is None:
        return ''
    result = str(raw)
    result = _fullwidth_to_halfwidth(result)
    result = _strip_noise(result)
    return result.strip().upper()


def _validate_id_check_code(id_number: str) -> bool:
    """18 位身份证校验码验证。"""
    if len(id_number) != 18:
        return False
    try:
        total = 0
        for i in range(17):
            total += int(id_number[i]) * _ID_WEIGHTS[i]
        expected = _ID_CHECK_CODES[total % 11]
        return id_number[17] == expected
    except (ValueError, IndexError):
        return False


def _validate_15bit_id(id_number: str) -> bool:
    """15 位老身份证校验（仅检查是否全数字）。"""
    if len(id_number) != 15:
        return False
    return id_number.isdigit()


def validate_id(id_number: str) -> Tuple[bool, List[str]]:
    """身份证号校验。

    支持 18 位和 15 位。18 位需验证校验码。
    """
    errors: List[str] = []
    if not id_number:
        errors.append('证件号为空')
        return False, errors

    if len(id_number) != 18 and len(id_number) != 15:
        errors.append(f'证件号长度应为15或18位，实际{len(id_number)}位')
        return False, errors

    if len(id_number) == 18:
        prefix17 = id_number[:17]
        if not prefix17.isdigit():
            errors.append('18位证件号前17位必须全为数字')
            return False, errors
        last = id_number[17]
        if not (last.isdigit() or last == 'X'):
            errors.append('18位证件号最后一位必须是数字或X')
            return False, errors
        if not _validate_id_check_code(id_number):
            errors.append('证件号校验码错误')
            return False, errors
    else:
        if not _validate_15bit_id(id_number):
            errors.append('15位证件号必须全为数字')
            return False, errors

    return True, errors


def compute_id_check_code(id17: str) -> str:
    """根据前17位计算身份证校验码。"""
    if len(id17) != 17 or not id17.isdigit():
        raise ValueError('必须提供17位纯数字')
    total = sum(int(id17[i]) * _ID_WEIGHTS[i] for i in range(17))
    return _ID_CHECK_CODES[total % 11]
