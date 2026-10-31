"""Recursive ICU structural parser, deliberately independent of regex extraction.

Supports nested plural/select/selectordinal, exact selectors, offsets, typed
arguments and Flutter's opt-in apostrophe escaping. It is a preflight checker,
not a replacement for Flutter's compiler (which accepts a narrower ICU subset).
"""
import re
from dataclasses import dataclass, field

class ICUError(ValueError):
    pass

@dataclass
class Message:
    arguments: dict = field(default_factory=dict)
    controls: list = field(default_factory=list)
    simple_spans: list = field(default_factory=list)
    literals: list = field(default_factory=list)

class Parser:
    def __init__(self, text, escaping=False):
        self.s, self.i, self.escaping = text, 0, escaping
        self.result = Message()

    def error(self, message):
        raise ICUError(f'{message} at character {self.i}')

    def ws(self):
        while self.i < len(self.s) and self.s[self.i].isspace(): self.i += 1

    def token(self, pattern):
        self.ws()
        match = re.match(pattern, self.s[self.i:])
        if not match: self.error('Expected identifier or selector')
        self.i += len(match[0])
        return match[0]

    def expect(self, value):
        self.ws()
        if not self.s.startswith(value, self.i): self.error(f'Expected {value!r}')
        self.i += len(value)

    def body(self, nested=False, depth=0):
        if depth > 60: self.error('ICU nesting exceeds safety limit')
        literal = []
        def flush():
            if literal: self.result.literals.append(''.join(literal)); literal.clear()
        while self.i < len(self.s):
            ch = self.s[self.i]
            if ch == "'" and self.escaping:
                self.i += 1
                if self.i < len(self.s) and self.s[self.i] == "'":
                    literal.append("'"); self.i += 1; continue
                closed = False
                while self.i < len(self.s):
                    if self.s[self.i] == "'":
                        self.i += 1
                        if self.i < len(self.s) and self.s[self.i] == "'":
                            literal.append("'"); self.i += 1; continue
                        closed = True; break
                    literal.append(self.s[self.i]); self.i += 1
                if not closed: self.error('Unclosed apostrophe escape')
                continue
            if ch == '}':
                if not nested: self.error('Unexpected closing brace')
                flush(); self.i += 1; return
            if ch != '{': literal.append(ch); self.i += 1; continue
            flush()
            start = self.i
            self.i += 1
            name = self.token(r'[A-Za-z_$][A-Za-z0-9_$]*')
            self.ws()
            if self.i >= len(self.s): self.error('Unclosed argument')
            kind = 'argument'
            if self.s[self.i] == '}':
                self.i += 1
                self.result.simple_spans.append((start, self.i, name))
            else:
                self.expect(',')
                kind = self.token(r'[A-Za-z]+')
                if kind not in {'plural','select','selectordinal','number','date','time'}:
                    self.error(f'Unsupported ICU argument type {kind!r}')
                if kind in {'plural','select','selectordinal'}:
                    self.expect(','); self.ws()
                    offset = 0
                    if self.s.startswith('offset:', self.i):
                        if kind == 'select': self.error('Select cannot have an offset')
                        self.i += 7; offset = int(self.token(r'\d+'))
                    selectors = []
                    # Store before recursion for stable traversal order.
                    control = {'name':name,'kind':kind,'selectors':selectors,'offset':offset}
                    self.result.controls.append(control)
                    while True:
                        self.ws()
                        if self.i >= len(self.s): self.error('Unclosed ICU control')
                        if self.s[self.i] == '}': self.i += 1; break
                        selector = self.token(r'=-?\d+(?:\.\d+)?|[A-Za-z_][A-Za-z0-9_]*')
                        if selector in selectors: self.error(f'Duplicate selector {selector}')
                        if kind != 'select' and selector not in {'zero','one','two','few','many','other'} and not selector.startswith('='):
                            self.error(f'Invalid plural selector {selector}')
                        selectors.append(selector)
                        self.expect('{'); self.body(True, depth+1)
                    if 'other' not in selectors: self.error('ICU control requires other branch')
                else:
                    self.ws()
                    if self.i < len(self.s) and self.s[self.i] == ',':
                        self.i += 1
                        while self.i < len(self.s) and self.s[self.i] != '}':
                            if self.s[self.i] == '{': self.error('Unexpected brace in format style')
                            self.i += 1
                    self.expect('}')
            existing = self.result.arguments.get(name)
            # {count} inside a plural is legal; a control determines its type.
            if existing and existing != kind and existing != 'argument' and kind != 'argument':
                self.error(f'Conflicting argument types for {name}')
            if not existing or kind != 'argument': self.result.arguments[name] = kind
        flush()
        if nested: self.error('Unclosed branch')


def parse(text, escaping=False):
    parser = Parser(text, escaping)
    parser.body()
    return parser.result


def compare(source, target):
    """Return placeholder evidence and control evidence. Locale categories differ."""
    placeholders, controls = [], []
    a, b = set(source.arguments), set(target.arguments)
    if a != b: placeholders.append(f'Missing placeholders: {sorted(a-b)}; extra placeholders: {sorted(b-a)}')
    for name in sorted(a & b):
        ak, bk = source.arguments[name], target.arguments[name]
        if ak != bk: controls.append(f'Argument {name}: source type {ak}, target type {bk}')
    # Never demand Russian few/many in Kazakh. Exact selectors and select labels
    # encode application semantics and should remain intact.
    def signature(c): return c['name'], c['kind']
    for sig in sorted({signature(c) for c in source.controls}):
        aa = [c for c in source.controls if signature(c) == sig]
        bb = [c for c in target.controls if signature(c) == sig]
        if len(aa) != len(bb):
            controls.append(f'Control {sig}: source occurrences {len(aa)}, target {len(bb)}'); continue
        for ac, bc in zip(aa, bb):
            required = set(ac['selectors']) if ac['kind'] == 'select' else {x for x in ac['selectors'] if x.startswith('=')}
            missing = required - set(bc['selectors'])
            if missing: controls.append(f'Control {sig}: missing semantic selectors {sorted(missing)}')
            if ac['offset'] != bc['offset']: controls.append(f'Control {sig}: offset changed')
    return placeholders, controls
