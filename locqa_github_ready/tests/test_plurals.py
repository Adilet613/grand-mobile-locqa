"""Pytest-native ICU regressions; no production text or partner datasets."""
import pytest
from locqa.icu import parse, compare, ICUError

@pytest.mark.parametrize('message', [
    '{n, plural, other{{n} зат}}',
    '{n, plural, =0{Жоқ} one{Бір} other{{n} зат}}',
    '{g, select, male{{n, plural, other{{n} зат}}} other{Басқа}}',
    '{n, selectordinal, one{бірінші} other{басқа}}',
])
def test_valid_icu(message):
    assert parse(message).controls

@pytest.mark.parametrize('message', [
    '{n, plural, one{Бір}}',
    '{n, plural, other{a} other{b}}',
    '{n, plural, wrong{a} other{b}}',
    '{n, plural, other{a}',
])
def test_invalid_icu_is_rejected(message):
    with pytest.raises(ICUError): parse(message)

def test_ru_plural_categories_are_not_mechanically_required_in_kazakh():
    assert compare(parse('{n, plural, one{one} few{few} many{many} other{other}}'),
                   parse('{n, plural, other{зат}}')) == ([], [])

def test_numeric_semantic_branch_is_protected():
    assert compare(parse('{n, plural, =0{none} other{some}}'),
                   parse('{n, plural, other{зат}}'))[1]
