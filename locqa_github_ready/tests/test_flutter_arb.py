import pytest
from locqa.flutter_arb import canonicalize

def test_legacy_description_becomes_metadata_without_changing_translation():
    data={'item':'Зат','item@description':'Developer note','@item':{'reviewed_by_human':False}}
    fixed,moves=canonicalize(data)
    assert fixed['item']=='Зат'
    assert fixed['@item']=={'description':'Developer note','reviewed_by_human':False}
    assert 'item@description' not in fixed
    assert data['item@description']=='Developer note'
    assert moves[0]['kind']=='metadata_migration'

def test_uppercase_alias_is_explicit_and_moves_metadata():
    fixed,moves=canonicalize({'Help':'Көмек','@Help':{'description':'hint'}})
    assert fixed=={'help':'Көмек','@help':{'description':'hint'}}
    assert moves[0]['requires_caller_update'] is True

@pytest.mark.parametrize('data',[
    {'Help':'A','help':'B'},
    {'item@description':'orphan'},
    {'item':'A','item@description':'X','@item':{'description':'Y'}},
    {'bad-key':'A'},
    {'_private':'A'},
    {'1number':'A'},
])
def test_unsafe_or_ambiguous_normalization_is_rejected(data):
    with pytest.raises(ValueError): canonicalize(data)
