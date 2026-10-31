import pytest
from locqa.engine import check

@pytest.mark.parametrize('target', ['{name}-ға жіберілді','{name}-ге жіберілді','{name}ге жіберілді'])
def test_arbitrary_dynamic_name_cannot_have_fixed_suffix(target):
    rows=check({'x':'Отправлено {name}'},{'@@locale':'kk','x':target},[])
    assert 'suffix_harmony' in {r['issue_type'] for r in rows}

@pytest.mark.parametrize('target', ['Алушы: {name}. Жіберілді.','Айбекке жіберілді: {name}'])
def test_suffix_free_placeholder_is_not_flagged(target):
    rows=check({'x':'Отправлено {name}'},{'@@locale':'kk','x':target},[])
    assert 'suffix_harmony' not in {r['issue_type'] for r in rows}

def test_documented_runtime_inflection_can_be_exempted():
    rows=check({'x':'Отправлено {name}'},{'@@locale':'kk','x':'{name}-ға жіберілді'},[],{'runtime_suffix_keys':['x']})
    assert 'suffix_harmony' not in {r['issue_type'] for r in rows}
