"""
SPAD Analyzer — Expressions XLSForm (relevant, constraint) évaluées sur un tableau de données

Un XLSForm exprime ses sauts de logique (« relevant ») et ses contraintes (« constraint ») dans un petit
langage XPath : ${age} >= 18 and selected(${profession}, 'medecin'). Ce module le lit et l'évalue d'un
coup sur toutes les lignes (colonnes pandas), pour retrouver dans les données les réponses qui violent
le formulaire.

Pris en charge : ${nom}, « . » (la réponse elle-même), nombres, textes, = != < <= > >=, and, or, not(),
+ - * div mod, selected(), count-selected(), string-length(), regex(), today(), if(), int(), number(),
coalesce(), once(). Toute autre fonction lève `Unsupported` : le contrôle correspondant est alors
ignoré et signalé, jamais deviné.
"""
import re

import numpy as np
import pandas as pd


class Unsupported(Exception):
    """Expression ou fonction que ce module ne sait pas évaluer."""


_TOKEN = re.compile(r"""
    (?P<space>\s+)
  | (?P<var>\$\{[^}]+\})
  | (?P<string>'[^']*'|"[^"]*")
  | (?P<number>\d+(?:\.\d+)?)
  | (?P<func>[A-Za-z_][A-Za-z0-9_\-:]*(?=\s*\())
  | (?P<op><=|>=|!=|=|<|>|\(|\)|,|\+|\*|-)
  | (?P<word>[A-Za-z_][A-Za-z0-9_\-]*)
  | (?P<dot>\.)
""", re.VERBOSE)


def tokenize(text):
    pos, out = 0, []
    text = str(text)
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m:
            raise Unsupported(f'caractère inattendu « {text[pos]} »')
        pos = m.end()
        kind = m.lastgroup
        if kind != 'space':
            out.append((kind, m.group()))
    return out


# ─── Valeurs : séries pandas ou scalaires ────────────────────────────────────

def _is_series(x):
    return isinstance(x, pd.Series)


def _num(x):
    return pd.to_numeric(x, errors='coerce') if _is_series(x) else pd.to_numeric(pd.Series([x]), errors='coerce').iloc[0]


def _text(x):
    return x.astype('string').str.strip() if _is_series(x) else str(x).strip()


def _date(x):
    return pd.to_datetime(x, errors='coerce', utc=True) if _is_series(x) else pd.to_datetime(x, errors='coerce', utc=True)


def _bool(x, index):
    if _is_series(x):
        return x.fillna(False).astype(bool)
    return pd.Series(bool(x), index=index)


def _both(a, b):
    return _is_series(a) or _is_series(b)


def _compare(op, a, b, index):
    """Comparaison XPath : nombres si les deux côtés le sont, sinon dates, sinon textes (une case vide ne vérifie jamais « < » ni « > »)."""
    if isinstance(a, pd.Timestamp) or isinstance(b, pd.Timestamp):
        left, right = _date(a), _date(b)
    else:
        left, right = _num(a), _num(b)
        usable = (left.notna().any() if _is_series(left) else pd.notna(left)) and (right.notna().any() if _is_series(right) else pd.notna(right))
        if not usable:
            left, right = _text(a), _text(b)
            if op not in ('=', '!='):
                dl, dr = _date(a), _date(b)
                if (dl.notna().any() if _is_series(dl) else pd.notna(dl)) and (dr.notna().any() if _is_series(dr) else pd.notna(dr)):
                    left, right = dl, dr
                else:
                    raise Unsupported('comparaison < ou > sur du texte')
    table = {'=': lambda x, y: x == y, '!=': lambda x, y: x != y, '<': lambda x, y: x < y, '<=': lambda x, y: x <= y,
             '>': lambda x, y: x > y, '>=': lambda x, y: x >= y}
    res = table[op](left, right)
    res = res.fillna(False).astype(bool) if _is_series(res) else bool(res)
    if op == '!=' and _is_series(a) and not isinstance(a, pd.Timestamp):          # « vide ≠ x » est vrai en XPath
        res = res | _text(a).isna() if _is_series(a) else res
    if not _is_series(res):
        return pd.Series(res, index=index)
    return res


class Evaluator:
    def __init__(self, tokens, resolve, self_value, index):
        self.t, self.i = tokens, 0
        self.resolve, self.self_value, self.index = resolve, self_value, index

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def take(self, value=None):
        tok = self.peek()
        if value is not None and tok[1] != value:
            raise Unsupported(f'« {value} » attendu')
        self.i += 1
        return tok

    def parse(self):
        value = self.p_or()
        if self.i < len(self.t):
            raise Unsupported(f"reste d'expression : « {self.t[self.i][1]} »")
        return value

    def p_or(self):
        a = self.p_and()
        while self.peek() == ('word', 'or'):
            self.take()
            b = self.p_and()
            a = _bool(a, self.index) | _bool(b, self.index)
        return a

    def p_and(self):
        a = self.p_cmp()
        while self.peek() == ('word', 'and'):
            self.take()
            b = self.p_cmp()
            a = _bool(a, self.index) & _bool(b, self.index)
        return a

    def p_cmp(self):
        a = self.p_add()
        while self.peek()[0] == 'op' and self.peek()[1] in ('=', '!=', '<', '<=', '>', '>='):
            op = self.take()[1]
            b = self.p_add()
            a = _compare(op, a, b, self.index)
        return a

    def p_add(self):
        a = self.p_mul()
        while self.peek()[0] == 'op' and self.peek()[1] in ('+', '-'):
            op = self.take()[1]
            b = self.p_mul()
            a = (_num(a) + _num(b)) if op == '+' else (_num(a) - _num(b))
        return a

    def p_mul(self):
        a = self.p_unary()
        while self.peek() in (('op', '*'), ('word', 'div'), ('word', 'mod')):
            op = self.take()[1]
            b = self.p_unary()
            a = _num(a) * _num(b) if op == '*' else (_num(a) / _num(b) if op == 'div' else _num(a) % _num(b))
        return a

    def p_unary(self):
        if self.peek() == ('op', '-'):
            self.take()
            return -_num(self.p_unary())
        return self.p_primary()

    def p_primary(self):
        kind, value = self.take()
        if kind == 'var':
            series = self.resolve(value[2:-1].strip())
            if series is None:
                raise Unsupported(f'question « {value[2:-1]} » absente des données')
            return series
        if kind == 'dot':
            return self.self_value
        if kind == 'number':
            return float(value)
        if kind == 'string':
            return value[1:-1]
        if kind == 'op' and value == '(':
            inner = self.p_or()
            self.take(')')
            return inner
        if kind == 'func':
            self.take('(')
            args = []
            if self.peek() != ('op', ')'):
                args.append(self.p_or())
                while self.peek() == ('op', ','):
                    self.take()
                    args.append(self.p_or())
            self.take(')')
            return self.call(value, args)
        raise Unsupported(f"« {value} » inattendu")

    def call(self, name, a):
        idx = self.index
        if name == 'not':
            return ~_bool(a[0], idx)
        if name == 'selected':
            token = str(a[1])
            return _text(a[0]).fillna('').str.split().map(lambda toks: token in toks).astype(bool)
        if name == 'count-selected':
            return _text(a[0]).fillna('').str.split().map(len).astype(float)
        if name == 'string-length':
            return _text(a[0]).fillna('').str.len().astype(float) if _is_series(a[0]) else float(len(str(a[0])))
        if name == 'regex':
            pattern = re.compile(str(a[1]))
            return _text(a[0]).fillna('').map(lambda v: bool(pattern.search(v))).astype(bool)
        if name == 'today' or name == 'now':
            return pd.Timestamp.now(tz='UTC').normalize() if name == 'today' else pd.Timestamp.now(tz='UTC')
        if name in ('int', 'number'):
            return np.floor(_num(a[0])) if name == 'int' else _num(a[0])
        if name == 'if':
            cond = _bool(a[0], idx)
            yes = a[1] if _is_series(a[1]) else pd.Series(a[1], index=idx)
            no = a[2] if _is_series(a[2]) else pd.Series(a[2], index=idx)
            return yes.where(cond, no)
        if name == 'coalesce':
            first, second = a[0], a[1]
            return first.where(_text(first).notna() & (_text(first) != ''), second) if _is_series(first) else first
        if name == 'once':
            return a[0]
        raise Unsupported(f'fonction « {name}() » non prise en charge')


def evaluate(expression, resolve, index, self_value=None):
    """Évalue `expression` sur toutes les lignes (`index`) ; `resolve(nom)` renvoie la série d'une question ou None.
    Renvoie une série booléenne. Lève Unsupported si l'expression sort de ce qui est géré."""
    tokens = tokenize(expression)
    value = Evaluator(tokens, resolve, self_value, index).parse()
    return _bool(value, index)
