import copy
import json
import tempfile
import unittest
from pathlib import Path
from locqa.icu import parse, compare, ICUError
from locqa.engine import check, glossary, load_arb, digest, CODES
from locqa.cli import main, safe_translation
from locqa.html_report import render

ROOT=Path(__file__).resolve().parents[1]
TERMS=glossary(ROOT/'tests/fixtures/glossary.csv')

def audit(src,tgt,config=None):return check(src,{'@@locale':'kk',**tgt},TERMS,config)
def types(src,tgt,config=None):return {i['issue_type'] for i in audit(src,tgt,config)}

class ICU(unittest.TestCase):
    def test_simple(self):self.assertEqual(set(parse('Сәлем, {name}!').arguments),{'name'})
    def test_nested(self):
        x=parse('{g, select, male{{n, plural, =0{none} one{{name}} other{{n} items}}} other{hello {name}}}')
        self.assertEqual(set(x.arguments),{'g','n','name'});self.assertEqual(len(x.controls),2)
    def test_number_date(self):self.assertEqual(parse('{x, number, currency} / {d, date, short}').arguments,{'x':'number','d':'date'})
    def test_offset(self):self.assertEqual(parse('{n, plural, offset:1 =0{none} other{{n}}}').controls[0]['offset'],1)
    def test_ordinal(self):self.assertEqual(parse('{n, selectordinal, one{1st} other{nth}}').arguments['n'],'selectordinal')
    def test_escaping(self):self.assertEqual(set(parse("'{fake}' {real} ''",True).arguments),{'real'})
    def test_apostrophe_default(self):self.assertIn('name',parse("Ойыншының '{name}' аты").arguments)
    def test_missing_other(self):
        with self.assertRaises(ICUError):parse('{n, plural, one{бір}}')
    def test_duplicate_selector(self):
        with self.assertRaises(ICUError):parse('{n, plural, other{a} other{b}}')
    def test_bad_selector(self):
        with self.assertRaises(ICUError):parse('{n, plural, bogus{a} other{b}}')
    def test_invalid_identifier(self):
        with self.assertRaises(ICUError):parse('{bad-name}')
    def test_unclosed(self):
        for s in ['{name','oops }','{n, plural, other{a}','{n, plural, other{a}']:
            with self.subTest(s=s),self.assertRaises(ICUError):parse(s)
    def test_ru_categories_not_required_in_kk(self):
        a=parse('{n, plural, one{one} few{few} many{many} other{other}}')
        b=parse('{n, plural, other{зат}}')
        self.assertEqual(compare(a,b),([],[]))
    def test_exact_branch_required(self):
        _,errors=compare(parse('{n, plural, =0{zero} other{other}}'),parse('{n, plural, other{зат}}'))
        self.assertTrue(errors)
    def test_select_label_required(self):
        self.assertTrue(compare(parse('{g, select, male{a} other{b}}'),parse('{g, select, other{b}}'))[1])
    def test_offset_change(self):
        self.assertTrue(compare(parse('{n, plural, offset:1 other{x}}'),parse('{n, plural, other{x}}'))[1])
    def test_nesting_limit(self):
        s='x'
        for _ in range(65):s='{g, select, other{'+s+'}}'
        with self.assertRaises(ICUError):parse(s)

class Detection(unittest.TestCase):
    def test_all_eleven(self):
        src={'missing':'Здравствуйте','same':'Купить','ph':'Привет {name}','plural':'{n, plural, other{{n} машин}}','term':'семья','rent_button':'Арендовать','mt':'Это имеет место','cons1':'Дверь','cons2':'Дверь','suffix':'Отправлено {name}','typo':'Привет','wrong':'Купить автомобиль'}
        tgt={'same':'Купить','ph':'Сәлем {player}','plural':'{n, plural, one{бір}}','term':'жанұя','rent_button':'Жалға алу үшін осы жерді басыңыз','mt':'Бұл иметь место қазір','cons1':'Есік','cons2':'Қақпа','suffix':'{name}-ға жіберілді','typo':'салем','wrong':'Avtomobil sotib olish uchun bosing'}
        self.assertEqual(types(src,tgt),set(CODES))
    def test_clean(self):
        src={'buy_button':'Купить','family':'семья','name':'Игрок: {name}','plural':'{n, plural, one{{n} автомобиль} few{{n} автомобиля} other{{n} автомобилей}}'}
        tgt={'buy_button':'Сатып алу','family':'Отбасы','name':'Ойыншы: {name}','plural':'{n, plural, other{{n} көлік}}'}
        self.assertEqual(audit(src,tgt),[])
    def test_legitimate_matches(self):
        for text in ['Grand Mobile','Grand Coins','123','<nick>','FPS','ГК','VIP','Android','https://example.org','20%','{name}']:
            with self.subTest(text=text):self.assertNotIn('same_as_source',types({'x':text},{'x':text}))
    def test_name_allowlist(self):self.assertNotIn('same_as_source',types({'x':'Алматы қаласы'},{'x':'Алматы қаласы'},{'allow_identical':['Алматы қаласы']}))
    def test_no_absence_of_kazakh_letter_heuristic(self):self.assertNotIn('wrong_language',types({'x':'Сумма'},{'x':'Сома'}))
    def test_no_suffix_on_literal(self):self.assertNotIn('suffix_harmony',types({'x':'Привет'},{'x':'Айбекке сәлем'}))
    def test_suffix_no_hyphen(self):self.assertIn('suffix_harmony',types({'x':'Игрок {name}'},{'x':'{name}ге сәлем'}))
    def test_runtime_exception(self):self.assertNotIn('suffix_harmony',types({'x':'Игрок {name}'},{'x':'{name}-ге сәлем'},{'runtime_suffix_keys':['x']}))
    def test_suffix_escaped_not_dynamic(self):self.assertNotIn('suffix_harmony',{i['issue_type'] for i in check({'x':'Слово'},{'x':"'{name}'-ға"},TERMS,{},True)})
    def test_metadata_ignored(self):self.assertEqual(audit({'@@locale':'ru','@x':{'description':'Привет'},'x':'Привет'},{'x':'Сәлем'}),[])
    def test_glossary_sentences_abstain(self):self.assertNotIn('glossary_violation',types({'x':'Ваша семья получила награду'},{'x':'Сыйақы берілді'}))
    def test_configured_length(self):self.assertIn('length_overflow',types({'x':'OK'},{'x':'Жақсы'},{'max_chars':{'x':3}}))
    def test_long_body_not_ui(self):self.assertNotIn('length_overflow',types({'body':'Текст'},{'body':'Бұл мәтіннің қазақ тіліндегі ұзақ нұсқасы'}))
    def test_style_opt_in(self):
        self.assertNotIn('machine_translation_suspect',types({'x':'Это дом'},{'x':'Бұл үй болып табылады'}))
        self.assertIn('machine_translation_suspect',types({'x':'Это дом'},{'x':'Бұл үй болып табылады'},{'include_style_candidates':True}))
    def test_uz_target_no_kk_rules(self):self.assertNotIn('wrong_language',{i['issue_type'] for i in check({'x':'Купить машину'},{'@@locale':'uz','x':'Sotib olish uchun bosing'},TERMS)})
    def test_system_tokens(self):self.assertIn('placeholder_mismatch',types({'x':'Привет <nick>'},{'x':'Сәлем <name>'}))
    def test_schema(self):
        for i in audit({'x':'Купить'},{'x':'Купить'}):
            self.assertEqual(set(i),{'key','issue_type','severity','source','target','evidence','suggestion','confidence','reviewed_by_human'})
            self.assertFalse(i['reviewed_by_human']);self.assertGreaterEqual(i['confidence'],0);self.assertLessEqual(i['confidence'],1)
    def test_no_duplicate_same_type(self):
        issues=audit({'x':'{a} {b}'},{'x':'{c} {d}'})
        self.assertEqual(len({(i['key'],i['issue_type']) for i in issues}),len(issues))

class Workflow(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.d=Path(self.tmp.name)
        self.src=self.d/'intl_ru.arb';self.tgt=self.d/'intl_kk.arb';self.rev=self.d/'reviews.json';self.out=self.d/'intl_kk_fixed.arb'
        self.put(self.src,{'@@locale':'ru','x':'Игрок: {name}','@x':{'description':'player name','placeholders':{'name':{'type':'String'}}}})
        self.put(self.tgt,{'@@locale':'kk','x':'Ойыншы {name}','@x':{'description':'preserve me'}})
    def put(self,path,obj):path.write_text(json.dumps(obj,ensure_ascii=False),encoding='utf-8')
    def manifest(self,text='Ойыншы: {name}'):
        return {'version':1,'source_sha256':digest(self.src),'target_sha256':digest(self.tgt),'entries':[{'key':'x','source':'Игрок: {name}','original':'Ойыншы {name}','translation':text,'reviewed_by_human':True,'reviewer':'TEST HUMAN ATTESTATION — synthetic only','reviewed_at':'2026-10-31T10:00:00Z'}]}
    def run_apply(self,m):
        self.put(self.rev,m)
        return main(['apply','--source',str(self.src),'--target',str(self.tgt),'--reviews',str(self.rev),'--out',str(self.out)])
    def test_apply_roundtrip(self):
        self.assertEqual(self.run_apply(self.manifest()),0)
        x=load_arb(self.out);self.assertEqual(x['x'],'Ойыншы: {name}');self.assertTrue(x['@x']['reviewed_by_human']);self.assertEqual(x['@x']['description'],'preserve me')
        self.assertEqual(read(self.out.with_suffix('.audit.json'))['changed_strings'],1)
    def test_no_human_rejected(self):
        m=self.manifest();m['entries'][0]['reviewed_by_human']=False
        self.assertEqual(self.run_apply(m),2);self.assertFalse(self.out.exists())
    def test_stale_rejected(self):
        m=self.manifest();self.tgt.write_text(self.tgt.read_text()+' ')
        self.assertEqual(self.run_apply(m),2);self.assertFalse(self.out.exists())
    def test_broken_placeholder_rejected(self):self.assertEqual(self.run_apply(self.manifest('Ойыншы')),2)
    def test_duplicate_approval_rejected(self):
        m=self.manifest();m['entries']*=2;self.assertEqual(self.run_apply(m),2)
    def test_original_text_mismatch_rejected(self):
        m=self.manifest();m['entries'][0]['original']='stale';self.assertEqual(self.run_apply(m),2)
    def test_empty_reviews_preserve_strings(self):
        m=self.manifest();m['entries']=[];self.assertEqual(self.run_apply(m),0)
        self.assertEqual(load_arb(self.out),load_arb(self.tgt))
    def test_input_never_overwritten(self):
        before=self.src.read_bytes()
        self.assertEqual(main(['check','--source',str(self.src),'--target',str(self.tgt),'--glossary',str(ROOT/'tests/fixtures/glossary.csv'),'--out',str(self.src)]),2)
        self.assertEqual(before,self.src.read_bytes())
    def test_check_cli(self):
        report=self.d/'report.json'
        self.assertEqual(main(['check','--source',str(self.src),'--target',str(self.tgt),'--glossary',str(ROOT/'tests/fixtures/glossary.csv'),'--out',str(report)]),0)
        self.assertTrue(report.with_suffix('.html').exists());self.assertEqual(read(report),[])
    def test_duplicate_json_rejected(self):
        self.tgt.write_text('{"x":"a","x":"b"}')
        with self.assertRaises(ValueError):load_arb(self.tgt,strict=True)
    def test_invalid_placeholder_metadata_rejected(self):
        self.put(self.src,{'x':'{name}','@x':{'placeholders':[]}})
        with self.assertRaises(ValueError):load_arb(self.src)
    def test_duplicate_last_occurrence_and_diagnostics(self):
        from locqa.engine import duplicate_diagnostics
        self.tgt.write_text('{"@@comment":"a","x":"one","@@comment":"b","x":"two"}')
        self.assertEqual(load_arb(self.tgt)['x'],'two')
        self.assertEqual(len(duplicate_diagnostics(self.tgt)),2)
        self.assertTrue(duplicate_diagnostics(self.tgt)[1]['conflicting'])
    def test_configured_blank_fragment_is_not_missing(self):
        rows=audit({'prefix':'Показатель '},{'prefix':''},{'allowed_blank_keys':['prefix']})
        self.assertNotIn('untranslated',{i['issue_type'] for i in rows})
    def test_nonstring_arb_rejected(self):
        self.put(self.tgt,{'x':42})
        with self.assertRaises(ValueError):load_arb(self.tgt)
    def test_source_invalid_even_when_target_missing(self):
        self.put(self.src,{'x':'{broken'});self.put(self.tgt,{})
        self.assertEqual(main(['check','--source',str(self.src),'--target',str(self.tgt),'--glossary',str(ROOT/'tests/fixtures/glossary.csv'),'--out',str(self.d/'r.json')]),2)
    def test_html_injection(self):
        html=render([{'key':'</script><img onerror=alert(1)>','issue_type':'untranslated'}],'a','b',1)
        self.assertNotIn('</script><img',html);self.assertIn('\\u003c/script\\u003e',html)
    def test_safe_translation_system_token(self):
        with self.assertRaises(ValueError):safe_translation('Привет <nick>','Сәлем')
    def test_extra_icu_invalid_rejected(self):
        x=load_arb(self.tgt);x['extra']='{broken';self.put(self.tgt,x)
        self.assertEqual(self.run_apply(self.manifest()),2)

def read(path):return json.loads(Path(path).read_text())

class LLMIntegration(unittest.TestCase):
    def test_proposals_are_unreviewed_and_structurally_gated(self):
        from unittest.mock import patch
        import io
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);s=d/'ru.arb';t=d/'kk.arb';o=d/'proposals.json'
            s.write_text(json.dumps({'x':'Отправлено {name}'}));t.write_text(json.dumps({'x':'{name}-ға жіберілді'}))
            response={'choices':[{'message':{'content':json.dumps({'proposals':{'x':'Алушы: {name}. Жіберілді.','intruder':'bad'}})}}],'usage':{'prompt_tokens':100,'completion_tokens':20}}
            with patch.dict('os.environ',{'LOCQA_API_KEY':'TEST-NOT-A-REAL-KEY'}),patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(response).encode())) as call:
                code=main(['propose','--source',str(s),'--target',str(t),'--glossary',str(ROOT/'tests/fixtures/glossary.csv'),'--model','test-model','--out',str(o),'--input-usd-per-million','1','--output-usd-per-million','2'])
                self.assertEqual(code,0);self.assertEqual(call.call_count,1)
                obj=read(o);self.assertEqual(set(obj['proposals']),{'x'});self.assertIn('intruder',obj['rejected']);self.assertFalse(obj['reviewed_by_human']);self.assertAlmostEqual(obj['api_cost_usd'],.00014)
                self.assertEqual(json.loads(t.read_text())['x'],'{name}-ға жіберілді')
    def test_structurally_unsafe_llm_suggestion_rejected(self):
        with self.assertRaises(ValueError):safe_translation('{n, plural, =0{none} other{{n}}}','{n, plural, other{{n}}}')

class Evaluation(unittest.TestCase):
    def test_seed_truth_does_not_claim_precision(self):
        from evaluate import evaluate
        result=evaluate([{'key':'a','issue_type':'untranslated'},{'key':'b','issue_type':'orthography'}],[{'key':'a','issue_type':'untranslated'}])
        self.assertEqual(result['recall'],1);self.assertIsNone(result['precision'])
    def test_type_matters(self):
        from evaluate import evaluate
        result=evaluate([{'key':'a','issue_type':'orthography'}],[{'key':'a','issue_type':'untranslated'}],True)
        self.assertEqual(result['recall'],0);self.assertEqual(result['precision'],0)
    def test_empty_denominators(self):
        from evaluate import evaluate
        self.assertIsNone(evaluate([],[],True)['recall'])

if __name__=='__main__':unittest.main()
