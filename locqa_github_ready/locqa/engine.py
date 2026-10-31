import csv
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from .icu import parse, compare, ICUError

CODES = ('untranslated','same_as_source','placeholder_mismatch','plural_mismatch','glossary_violation','length_overflow','machine_translation_suspect','inconsistent_term','suffix_harmony','orthography','wrong_language')
BRANDS = {'grand mobile','grand coins','android','ios','discord','youtube','telegram','google','apple'}
ACTIONS = {'арендовать','купить','продать','закрыть','открыть','отмена','настройки','продолжить','назад','войти','выход','подтвердить','удалить','сохранить','помощь','получить','отправить'}
# Narrow, explicit lexical rules, not a claim to comprehensive Kazakh spelling.
SPELLINGS = {'салем':'сәлем','рахметт':'рақмет','сәлеметсізбе':'сәлеметсіз бе','отбасыныз':'отбасыңыз','тенге':'теңге','койылым':'қойылым','жүктелудеі':'жүктелуде'}
CALQUES = {'болып табылады': 'Consider a direct nominal predicate; this phrase may be formal but is not automatically incorrect.',
           'орынға ие': 'Possible calque of «имеет место»; verify the full sentence in context.'}
SUFFIX = re.compile(r'^[-‑–]?(?:ға|ге|қа|ке|да|де|та|те|дан|ден|тан|тен|нан|нен|ның|нің|дың|дің|тың|тің|мен|бен|пен|ны|ні|ды|ді|ты|ті)(?![\w])', re.I)
UZ = {'uchun','bilan','sizning','hisob','hisobingiz','sotib','olish','tugmasini','bosing','muvaffaqiyatli','bekor','qilish','o‘yin','oʻyin',"o'yin",'qaytish','ochish','yopish'}
RU = {'чтобы','нажмите','пожалуйста','вашего','вашей','успешно','недостаточно','получить','отправить','покупка','арендовать'}
KK = {'үшін','және','сіздің','басып','алыңыз','сатып','керек','сәтті','жоқ','бар','ойын','қайту','алу'}

def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def unique_object(pairs, strict=False):
    out = {}
    for k,v in pairs:
        if strict and k in out and k != '@@comment': raise ValueError(f'Duplicate JSON key: {k}')
        out[k] = v
    return out

def load_arb(path, strict=False):
    with open(path, encoding='utf-8-sig') as f: value = json.load(f, object_pairs_hook=lambda pairs: unique_object(pairs,strict))
    if not isinstance(value,dict): raise ValueError('ARB root must be an object')
    for k,v in value.items():
        if not k.startswith('@') and not isinstance(v,str): raise ValueError(f'ARB message {k!r} must be a string')
        if k.startswith('@') and not k.startswith('@@'):
            if not isinstance(v,dict): raise ValueError(f'ARB metadata {k!r} must be an object')
            if 'placeholders' in v and (not isinstance(v['placeholders'],dict) or any(not isinstance(m,dict) for m in v['placeholders'].values())): raise ValueError(f'ARB placeholder metadata {k!r} must map names to objects')
    return value

def duplicate_diagnostics(path):
    """Top-level duplicate ARB keys, before last-occurrence normalization."""
    with open(path,encoding='utf-8-sig') as f:
        pairs=json.load(f,object_pairs_hook=lambda items:items)
    if not isinstance(pairs,list): return []
    group=defaultdict(list)
    for key,value in pairs: group[key].append(value)
    return [{'key':key,'occurrences':len(values),'conflicting':any(v!=values[0] for v in values),'resolution':'last occurrence'} for key,values in group.items() if len(values)>1]

def norm(s): return unicodedata.normalize('NFC',s).casefold().strip()
def words(s): return re.findall(r"[^\W\d_]+(?:[‘ʻ'’][^\W\d_]+)*",norm(s), re.UNICODE)
def has_term(text, term):
    # Inflection-aware stem matching only for sufficiently long glossary terms.
    ending = r'(?:ға|ге|қа|ке|да|де|та|те|дан|ден|тан|тен|ның|нің|дың|дің|тың|тің|ны|ні|ды|ді|ты|ті|лар|лер|дар|дер|тар|тер|сы|сі|ы|і)?' if len(term) >= 4 else ''
    return re.search(r'(?<!\w)'+re.escape(norm(term))+ending+r'(?!\w)', norm(text)) is not None

def glossary(path):
    with open(path,encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if not {'ru','kk','en','comment on usage'} <= set(reader.fieldnames or []): raise ValueError('Glossary requires ru,kk,en,comment on usage columns')
        rows=list(reader)
    seen={}
    for row in rows:
        if not row['ru'].strip() or not row['kk'].strip(): raise ValueError('Empty glossary term')
        key=norm(row['ru'])
        if key in seen and seen[key] != row['kk']: raise ValueError(f'Conflicting glossary entry: {key}')
        seen[key]=row['kk']
    return rows

def protected(text, allow):
    clean = re.sub(r'<[^<>]+>|\{[A-Za-z_][A-Za-z0-9_]*\}', '', text).strip()
    if norm(clean) in BRANDS | set(map(norm,allow)): return True
    if not any(c.isalpha() for c in clean): return True
    if re.fullmatch(r'(?:https?://|www\.)\S+|[\w.+-]+@[\w.-]+\.[A-Za-z]+',clean): return True
    if re.fullmatch(r'[A-ZА-ЯЁ0-9_+./ -]{1,8}',clean): return True
    return False

def check(source, target, terms, config=None, escaping=False):
    config = config or {}
    locale = str(target.get('@@locale', config.get('locale','kk'))).split('_')[0].split('-')[0]
    issues=[]; groups=defaultdict(list)
    def add(key,code,severity,evidence,suggestion='',confidence=1.0):
        issues.append(dict(key=key,issue_type=code,severity=severity,source=source[key],target=target.get(key,''),evidence=evidence,suggestion=suggestion,confidence=confidence,reviewed_by_human=False))
    for key,src in source.items():
        if key.startswith('@'): continue
        tgt=target.get(key)
        if tgt is None or (not tgt.strip() and src.strip() and key not in config.get('allowed_blank_keys',[])):
            add(key,'untranslated','high','Target key is missing' if tgt is None else 'Target is blank while source is nonblank'); continue
        try: sa=parse(src,escaping)
        except ICUError as e: raise ValueError(f'Invalid SOURCE ICU at {key}: {e}') from e
        try: ta=parse(tgt,escaping)
        except ICUError as e:
            code='plural_mismatch' if re.search(r',\s*(plural|select|selectordinal)\s*,',tgt+src) else 'placeholder_mismatch'
            add(key,code,'high',f'Target ICU parse failed: {e}'); continue
        ph,ctrl=compare(sa,ta)
        if ph: add(key,'placeholder_mismatch','high','; '.join(ph))
        if ctrl: add(key,'plural_mismatch','high','; '.join(ctrl))
        # Protect non-ICU system tokens, HTML tags and printf placeholders too.
        token_re=r'<[^<>]+>|%(?:\d+\$)?[sdif]|\$[A-Za-z_][A-Za-z0-9_]*'
        st=sorted(re.findall(token_re,src)); tt=sorted(re.findall(token_re,tgt))
        if st!=tt and not ph: add(key,'placeholder_mismatch','high',f'Protected tokens changed: source={st!r}; target={tt!r}')
        src_literal=' '.join(sa.literals); literal=' '.join(ta.literals)
        sw,tw=words(src_literal),words(literal)
        same=norm(src)==norm(tgt)
        is_protected=protected(src,config.get('allow_identical',[]))
        if same and not is_protected and (len(sw)>=2 or norm(src) in ACTIONS):
            add(key,'same_as_source','high','NFC-normalized target equals source; contains translatable words and is not allowlisted',confidence=.99)
        if locale == 'kk':
            if not same:
                uw=set(tw)&UZ; rw=set(tw)&RU; kw=set(tw)&KK
                if len(uw)>=2 and not kw:
                    add(key,'wrong_language','high',f'Uzbek lexical anchors {sorted(uw)}; no Kazakh anchors; verify quoted text',confidence=.96)
                elif len(rw)>=2 and not kw and not re.search('[әғқңөұүһі]',norm(literal)):
                    add(key,'wrong_language','high',f'Russian lexical anchors {sorted(rw)}; no Kazakh anchors',confidence=.94)
            for start,end,name in ta.simple_spans:
                match=SUFFIX.match(tgt[end:])
                if match:
                    meta=source.get('@'+key,{}).get('placeholders',{}).get(name,{})
                    runtime=config.get('runtime_suffix_keys',[])
                    if key not in runtime:
                        add(key,'suffix_harmony','high',f'Fixed suffix {match[0]!r} follows dynamic {{{name}}}; metadata type={meta.get("type","unknown")}. Vowel harmony and final consonant cannot be guaranteed. Rephrase or implement runtime inflection.',confidence=.99)
                        break
            for bad,good in SPELLINGS.items():
                if re.search(r'(?<!\w)'+re.escape(bad)+r'(?!\w)',norm(literal)):
                    add(key,'orthography','medium',f'Explicit spelling rule matched {bad!r}; proposed form {good!r}',re.sub(r'(?<!\w)'+re.escape(bad)+r'(?!\w)',good,tgt,flags=re.I),.96); break
            if re.search(r'(?<=[А-Яа-яӘәҒғҚқҢңӨөҰұҮүҺһІі])[a-zA-Z]|[a-zA-Z](?=[А-Яа-яӘәҒғҚқҢңӨөҰұҮүҺһІі])',literal):
                add(key,'orthography','medium','Latin and Cyrillic letters occur inside the same word; inspect for homoglyphs or intentional mixed-script product names',confidence=.85)
            if config.get('include_style_candidates',False):
                for phrase,explanation in CALQUES.items():
                    if phrase in norm(literal): add(key,'machine_translation_suspect','low',f'Phrase {phrase!r}: {explanation}',confidence=.62); break
            # Hard MT detection is deliberately limited to a curated, context-bound rule.
            if 'иметь' in tw and 'место' in tw and re.search('[әғқңөұүһі]',norm(literal)):
                add(key,'machine_translation_suspect','medium','Russian predicate «иметь место» embedded in Kazakh text; check for an untranslated calque',confidence=.92)
            for term in terms:
                if not same and norm(src_literal)==norm(term['ru']) and not has_term(literal,term['kk']):
                    add(key,'glossary_violation','medium',f'Whole source label matches glossary {term["ru"]!r}; expected {term["kk"]!r}. Usage: {term["comment on usage"]}',term['kk'],.96)
        # UI budget is configurable per key; heuristic is labeled, never pixel certainty.
        md=source.get('@'+key,{})
        context=key+' '+str(md.get('description',''))
        budget=config.get('max_chars',{}).get(key)
        n,m=len(src),len(tgt)
        if budget is not None and m>budget:
            add(key,'length_overflow','high',f'{m} Unicode code points exceed configured limit {budget}; rendered width still requires Flutter UI verification',confidence=.98)
        elif budget is None and re.search(r'button|btn|tab|header|title',context,re.I) and 0<n<=24 and m>=n*1.6 and m-n>=8 and not sa.arguments and not ta.arguments:
            add(key,'length_overflow','medium',f'{m} Unicode code points versus {n} in source ({m/n:.2f}×); short UI context {context!r}; heuristic risk, not measured clipping',confidence=.80)
        if not same and not is_protected and len(sw)>0 and not sa.arguments and not ta.arguments:
            groups[norm(src)].append((key,norm(tgt),tgt))
    # Exact repeated source labels only: avoids assuming sentence-level sense equivalence.
    for src,items in groups.items():
        variants={v for _,v,_ in items}
        if len(variants)>1 and len(src.split())<=3:
            evidence='Same source label has target variants: '+repr({v:[k for k,x,_ in items if x==v] for v in sorted(variants)})+'; contextual alternatives need human adjudication'
            for k,_,_ in items:
                if not any(i['key']==k and i['issue_type']=='glossary_violation' for i in issues): add(k,'inconsistent_term','low',evidence,confidence=.78)
    rank={'high':0,'medium':1,'low':2}
    return sorted(issues,key=lambda x:(rank[x['severity']],x['key'],x['issue_type']))
