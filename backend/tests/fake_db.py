"""In-memory stand-ins for SQLAlchemy sessions and Redis.

Just enough behavior for the query shapes our routes/tasks actually use
(filter_by / filter with ==/.in_() / join / order_by / first / all),
so integration tests can run the real handlers without Postgres.
"""

from collections import defaultdict

from sqlalchemy import inspect
from sqlalchemy.sql import operators

from app.db.base import Base

_REGISTRY: dict[str, type] = {}


def _registry() -> dict[str, type]:
    if not _REGISTRY:
        for mapper in Base.registry.mappers:
            _REGISTRY[mapper.class_.__tablename__] = mapper.class_
    return _REGISTRY


def _loose_eq(a, b) -> bool:
    return a == b or str(a) == str(b)


def _resolve(side, env):
    """Resolve one side of a binary expression to a Python value."""
    table = getattr(side, "table", None)
    if table is not None:  # a mapped column
        cls = _registry()[table.name]
        return getattr(env[cls], side.key)
    if hasattr(side, "effective_value"):  # BindParameter
        return side.effective_value
    return side.value


def _eval(expr, env) -> bool:
    if hasattr(expr, "clauses"):  # and_() lists
        return all(_eval(clause, env) for clause in expr.clauses)
    lval = _resolve(expr.left, env)
    if expr.operator is operators.in_op:
        return any(_loose_eq(lval, item) for item in _resolve(expr.right, env))
    if expr.operator is operators.eq:
        return _loose_eq(lval, _resolve(expr.right, env))
    raise NotImplementedError(f"FakeQuery does not support operator {expr.operator}")


class FakeQuery:
    """Rows are {model_class: instance} environments; `model` is the entity returned."""

    def __init__(self, db: "FakeDB", model: type, rows: list[dict]):
        self.db = db
        self.model = model
        self.rows = rows

    def filter_by(self, **kwargs):
        rows = [
            env
            for env in self.rows
            if all(_loose_eq(getattr(env[self.model], k), v) for k, v in kwargs.items())
        ]
        return FakeQuery(self.db, self.model, rows)

    def filter(self, *criteria):
        rows = [env for env in self.rows if all(_eval(c, env) for c in criteria)]
        return FakeQuery(self.db, self.model, rows)

    def join(self, target, onclause):
        rows = []
        for env in self.rows:
            for candidate in self.db.objects[target]:
                joined = {**env, target: candidate}
                if _eval(onclause, joined):
                    rows.append(joined)
        return FakeQuery(self.db, self.model, rows)

    def order_by(self, *clauses):
        rows = list(self.rows)
        for clause in reversed(clauses):
            column = getattr(clause, "element", clause)
            reverse = getattr(clause, "modifier", None) is operators.desc_op
            rows.sort(
                key=lambda env: getattr(env[self.model], column.key), reverse=reverse
            )
        return FakeQuery(self.db, self.model, rows)

    def first(self):
        return self.rows[0][self.model] if self.rows else None

    def all(self):
        return [env[self.model] for env in self.rows]

    def count(self):
        return len(self.rows)


class FakeDB:
    def __init__(self, *objects):
        self.objects: dict[type, list] = defaultdict(list)
        for obj in objects:
            self.add(obj)
        self.flush()

    def add(self, obj):
        self.objects[type(obj)].append(obj)

    def query(self, model):
        rows = [{model: obj} for obj in self.objects[model]]
        return FakeQuery(self, model, rows)

    def flush(self):
        """Apply python-side column defaults the way a real flush would."""
        for instances in self.objects.values():
            for obj in instances:
                for col in inspect(type(obj)).columns:
                    if getattr(obj, col.key, None) is None and col.default is not None:
                        default = col.default
                        if default.is_callable:
                            try:
                                value = default.arg(None)
                            except TypeError:
                                value = default.arg()
                        elif default.is_scalar:
                            value = default.arg
                        else:
                            continue
                        setattr(obj, col.key, value)

    def commit(self):
        self.flush()

    def rollback(self):
        pass

    def close(self):
        pass


class FakeRedis:
    """Implements the handful of commands CreditService uses, including
    a Python emulation of its reserve Lua script."""

    def __init__(self):
        self.store: dict[str, str] = {}

    def get(self, key):
        return self.store.get(key)

    def eval(self, script, numkeys, *args):
        keys, argv = args[:numkeys], args[numkeys:]
        reserved = int(self.store.get(keys[0]) or 0)
        amount, balance = int(argv[0]), int(argv[1])
        if balance - reserved < amount:
            return 0
        self.store[keys[0]] = str(reserved + amount)
        self.store[keys[1]] = str(amount)
        return 1

    def incrby(self, key, amount):
        self.store[key] = str(int(self.store.get(key) or 0) + amount)

    def decrby(self, key, amount):
        self.incrby(key, -amount)

    def delete(self, key):
        self.store.pop(key, None)
