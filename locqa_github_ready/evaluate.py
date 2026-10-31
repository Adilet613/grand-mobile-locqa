"""Evaluate independently supplied (key, issue_type) labels. Never invent truth.

python evaluate.py --report report.json --truth independently_labeled.json
Truth: [{"key":"x","issue_type":"untranslated"}, ...]
Use exhaustive truth for precision; a seed-only truth file cannot establish FP.
"""
import argparse
import json
from pathlib import Path

def pairs(rows):return {(r['key'],r['issue_type']) for r in rows}
def ratio(a,b):return a/b if b else None

def evaluate(predicted,truth,exhaustive=False):
    p,t=pairs(predicted),pairs(truth)
    result={'predicted_pairs':len(p),'labeled_error_pairs':len(t),'matched_pairs':len(p&t),'recall':ratio(len(p&t),len(t)),'precision':ratio(len(p&t),len(p)) if exhaustive else None,'precision_note':'Computed against exhaustive independently adjudicated truth' if exhaustive else 'Unknown: seed-only truth cannot identify false positives','by_type':{}}
    for code in sorted({c for _,c in p|t}):
        a={x for x in p if x[1]==code};b={x for x in t if x[1]==code}
        result['by_type'][code]={'predicted':len(a),'truth':len(b),'tp':len(a&b),'recall':ratio(len(a&b),len(b)),'precision':ratio(len(a&b),len(a)) if exhaustive else None}
    return result

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--report',required=True);a.add_argument('--truth',required=True);a.add_argument('--exhaustive-truth',action='store_true');a.add_argument('--out');args=a.parse_args()
    result=evaluate(json.loads(Path(args.report).read_text()),json.loads(Path(args.truth).read_text()),args.exhaustive_truth)
    text=json.dumps(result,indent=2)
    if args.out:Path(args.out).write_text(text+'\n')
    print(text)
