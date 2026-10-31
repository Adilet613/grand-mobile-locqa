"""Explicit ARB metadata/identifier migration for standard Flutter generation.

Renaming IDs requires caller updates; this is not a silent QA autofix.
"""
import re

def canonicalize(data):
    data=dict(data);migrations=[]
    for key in list(data):
        if not key.startswith('@') and key.endswith('@description'):
            message=key[:-len('@description')]
            if message not in data:raise ValueError(f'Orphan description: {key}')
            attrs=dict(data.get('@'+message,{}))
            if 'description' in attrs and attrs['description']!=data[key]:raise ValueError('Conflicting description '+key)
            attrs['description']=data.pop(key);data['@'+message]=attrs
            migrations.append({'from':key,'to':'@'+message+'.description','kind':'metadata_migration'})
    for key in list(data):
        if key.startswith('@'):continue
        if key[:1].isupper():
            new=key[0].lower()+key[1:]
            if new in data:raise ValueError('Resource alias collision '+new)
            data[new]=data.pop(key)
            if '@'+key in data:data['@'+new]=data.pop('@'+key)
            migrations.append({'from':key,'to':new,'kind':'resource_id_alias','requires_caller_update':True})
        elif not re.fullmatch(r'[a-z$][A-Za-z0-9_$]*',key):
            raise ValueError('Unsupported legacy resource ID '+key)
    return data,migrations

