"""A small in-memory stand-in for the Supabase client, enough for route tests. Not used by the app."""
import copy


class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, db, table):
        self.db, self.table, self.filters, self.op, self.payload = db, table, [], "select", None
        self._order, self._limit, self._neg = None, None, False

    # filters
    def _f(self, fn):
        neg, self._neg = self._neg, False
        self.filters.append((lambda r: not fn(r)) if neg else fn)
        return self

    def eq(self, k, v):
        return self._f(lambda r: r.get(k) == v)

    def in_(self, k, vals):
        vals = list(vals)
        return self._f(lambda r: r.get(k) in vals)

    def is_(self, k, v):
        return self._f(lambda r: r.get(k) is None if v == "null" else r.get(k) is v)

    def gte(self, k, v):
        return self._f(lambda r: r.get(k) is not None and str(r.get(k)) >= str(v))

    @property
    def not_(self):
        self._neg = True
        return self

    def order(self, k, desc=False):
        self._order = (k, desc)
        return self

    def limit(self, n):
        self._limit = (0, n)
        return self

    def range(self, a, b):
        self._limit = (a, b - a + 1)
        return self

    def select(self, *a, **k):
        return self

    # writes
    def insert(self, rows, **k):
        self.op, self.payload = "insert", rows
        return self

    def upsert(self, rows, on_conflict=None, ignore_duplicates=False, **k):
        self.op, self.payload = "upsert", rows
        self._conflict, self._ignore = (on_conflict.split(",") if on_conflict else None), ignore_duplicates
        return self

    def lt(self, k, v):
        return self._f(lambda r: r.get(k) is not None and str(r.get(k)) < str(v))

    def update(self, changes):
        self.op, self.payload = "update", changes
        return self

    def delete(self):
        self.op = "delete"
        return self

    def execute(self):
        if self.table in self.db.missing:
            raise RuntimeError(f'relation "{self.table}" does not exist')
        rows = self.db.tables.setdefault(self.table, [])
        if self.op in ("insert", "upsert"):
            new = self.payload if isinstance(self.payload, list) else [self.payload]
            out = []
            conflict = getattr(self, "_conflict", None) if self.op == "upsert" else None
            for r in new:
                r = copy.deepcopy(r)
                if conflict:   # like Postgres ON CONFLICT: update the existing row, or skip it with ignore_duplicates
                    hit = next((x for x in rows if all(x.get(c) == r.get(c) for c in conflict)), None)
                    if hit is not None:
                        if not self._ignore:
                            hit.update(r)
                            out.append(copy.deepcopy(hit))
                        continue
                for col, val in self.db.defaults.get(self.table, {}).items():
                    r.setdefault(col, val() if callable(val) else val)
                if "id" not in r:
                    self.db.seq += 1
                    r["id"] = self.db.seq
                rows.append(r)
                out.append(copy.deepcopy(r))
            return _Result(out)
        hit = [r for r in rows if all(f(r) for f in self.filters)]
        if self.op == "update":
            for r in hit:
                r.update(copy.deepcopy(self.payload))
            return _Result(copy.deepcopy(hit))
        if self.op == "delete":
            self.db.tables[self.table] = [r for r in rows if r not in hit]
            return _Result(hit)
        if self._order:
            k, desc = self._order
            hit = sorted(hit, key=lambda r: (r.get(k) is None, r.get(k) or ""), reverse=desc)
        if self._limit:
            a, n = self._limit
            hit = hit[a:a + n]
        return _Result(copy.deepcopy(hit))


class FakeDB:
    def __init__(self, tables=None, missing=(), defaults=None):
        self.tables = copy.deepcopy(tables or {})
        self.missing = set(missing)
        self.defaults = defaults or {}
        self.seq = 1000

    def table(self, name):
        return _Query(self, name)
