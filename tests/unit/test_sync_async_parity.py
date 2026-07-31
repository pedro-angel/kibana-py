"""Guard: the sync and async client trees must stay in lockstep -- API *and* logic.

Hundreds of methods are hand-duplicated across ``kibana/_sync`` and
``kibana/_async`` (there is no unasync-style generator). These tests lock the two
trees together so drift fails CI immediately:

- **names** -- every public method / property / classmethod present on one tree's
  client must exist on its twin, in *both* directions.
- **signatures** -- matching methods must have identical parameter shape (name,
  kind, default), ignoring annotations (async legitimately differs there).
- **bodies** -- matching method *bodies* must be identical after normalizing away
  the KNOWN-mechanical sync/async differences. This is what catches a bugfix that
  landed in one tree but not the other -- the drift a name/signature check alone
  cannot see. A small, explicit allowlist covers the few methods that legitimately
  diverge at the sync/async I/O boundary.

The body normalizer encodes exactly two intentional divergences, both documented
in the code it checks:
  1. Mechanical async->sync: ``async def``->``def``, ``await x``->``x``,
     ``async for``/``async with``, the ``Async`` class-name prefix, ``_async``
     module paths, and the ``__aenter__``/``__aexit__``/``aclose`` dunders.
  2. Space validation: async cannot validate a space inside a sync helper, so it
     awaits ``self._maybe_validate_space(space, validate)`` separately and then
     calls ``self._build_space_path(base, space)``; sync folds it into
     ``self._build_space_path(base, space, validate_spaces=validate)``. The
     normalizer canonicalizes both to ``_build_space_path(base, space, validate)``
     -- threading the async call's validate argument in rather than discarding it,
     so a drift in *which* space/flag is validated (or async skipping validation
     while sync keeps it) still fails.

     The fold is narrow on purpose (#75): it applies only to a genuinely
     ``await``-ed call standing immediately before the ``_build_space_path`` call
     for the same space. A dropped ``await``, a build-then-validate order, a
     detached check, or a check on a different space are NOT folded and fail as
     drift -- which is what keeps the format-first convention (#74) CI-enforced
     rather than conventional. ``test_normalizer_surfaces_broken_space_validation``
     pins each of those four cases against the normalizer itself.

Anything the normalizer does NOT fold is treated as real drift and fails -- unless
listed in ``_BODY_DRIFT_ALLOWLIST`` with a reason.
"""

import ast
import importlib
import inspect
import pkgutil
import re
import textwrap

import pytest

import kibana._async.client as async_mod
import kibana._sync.client as sync_mod
from kibana import AsyncKibana, Kibana


# --------------------------------------------------------------------------- #
# Client-pair discovery (bidirectional, whole-tree)
# --------------------------------------------------------------------------- #
def _client_classes(pkg) -> dict[str, type]:
    """``{class_name: class}`` for every ``*Client`` class *defined* anywhere in
    the client package.

    Walks the submodules rather than ``dir(pkg)`` so sub-sub-clients that are not
    re-exported at the package level (e.g. ``RulesClient``, ``BackfillClient``,
    ``NamespaceClient``, reached as ``client.alerting.rule``) are still guarded.
    ``cls.__module__ == module`` keeps re-exports from being counted twice.
    """
    found: dict[str, type] = {}
    # walk_packages (not iter_modules) recurses into any future sub-packages.
    for info in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
        mod = importlib.import_module(info.name)
        for cname, cobj in inspect.getmembers(mod, inspect.isclass):
            if cobj.__module__ == info.name and cname.endswith("Client"):
                found[cname] = cobj
    return found


def _client_pairs():
    """(name, sync_cls, async_cls) for the top-level clients and every sub-client.

    Sub-clients follow the ``X`` / ``AsyncX`` convention. Discovery runs in BOTH
    directions so neither tree can hide a client the other lacks.
    """
    pairs = [("Kibana", Kibana, AsyncKibana)]

    # Top-level space-scoped client -- defined in __init__ (not a walked
    # submodule) and its name does not end in "Client", so pair it explicitly.
    ssk = getattr(sync_mod, "SpaceScopedKibana", None)
    assk = getattr(async_mod, "AsyncSpaceScopedKibana", None)
    assert (ssk is None) == (
        assk is None
    ), "SpaceScopedKibana / AsyncSpaceScopedKibana present in only one tree"
    if ssk is not None:
        pairs.append(("SpaceScopedKibana", ssk, assk))

    sync_clients = _client_classes(sync_mod)  # {FooClient: cls}
    async_clients = _client_classes(async_mod)  # {AsyncFooClient: cls}
    async_bare = {
        name[len("Async") :]: cls
        for name, cls in async_clients.items()
        if name.startswith("Async")
    }
    for name in sorted(sync_clients):
        assert "Async" + name in async_clients, f"sync {name} has no Async{name} twin"
    for name in sorted(async_bare):
        assert name in sync_clients, f"async Async{name} has no {name} twin"
    for name in sorted(set(sync_clients) & set(async_bare)):
        pairs.append((name, sync_clients[name], async_bare[name]))
    return pairs


_PAIRS = _client_pairs()
_IDS = [name for name, _, _ in _PAIRS]


# --------------------------------------------------------------------------- #
# Member discovery
# --------------------------------------------------------------------------- #
def _public_names(cls) -> set[str]:
    """Public methods, properties, classmethods and staticmethods.

    Uses ``getattr_static`` so descriptors are inspected, not invoked. Broader
    than ``inspect.isfunction`` (which silently ignores @property/@classmethod).
    """
    names = set()
    for name in dir(cls):
        if name.startswith("_"):
            continue
        try:
            attr = inspect.getattr_static(cls, name)
        except AttributeError:
            continue
        if isinstance(
            attr, (property, classmethod, staticmethod)
        ) or inspect.isfunction(attr):
            names.add(name)
    return names


def _underlying_func(cls, name):
    """The plain function backing a member, for signature/body comparison.

    Unwraps classmethod/staticmethod and properties (their getter). Returns
    ``None`` only when there is no comparable function (e.g. a setter-only
    property) -- existence is still covered by name parity.
    """
    attr = inspect.getattr_static(cls, name)
    if isinstance(attr, (classmethod, staticmethod)):
        return attr.__func__
    if isinstance(attr, property):
        return attr.fget  # compare the getter (a drifting accessor was unguarded)
    if inspect.isfunction(attr):
        return attr
    return None


def _norm_default(value):
    # The DEFAULT sentinel is a distinct DefaultType instance in each tree, so
    # compare it by kind rather than identity.
    return "<DEFAULT>" if type(value).__name__ == "DefaultType" else value


def _param_shape(func):
    return [
        (p.name, p.kind, _norm_default(p.default))
        for p in inspect.signature(func).parameters.values()
    ]


# --------------------------------------------------------------------------- #
# Body normalization
# --------------------------------------------------------------------------- #
_ASYNC_RENAMES = {
    "__aenter__": "__enter__",
    "__aexit__": "__exit__",
    "__aiter__": "__iter__",
    "__anext__": "__next__",
    "aclose": "close",
    "_async": "_sync",  # module-path segment, e.g. kibana._async.client
}


# Set on the ``ast.Expr`` node of a genuinely awaited ``_maybe_validate_space``
# statement while the Await is still visible (see visit_AsyncFunctionDef).
_AWAITED_VALIDATE = "_parity_awaited_validate"


def _canon_ident(name: str) -> str:
    """Canonicalize an async identifier/attribute to its sync spelling.

    Applied to AST Name/Attribute nodes ONLY (never to string constants), so a
    genuine string-value drift that happens to contain ``async``/``Async`` is not
    masked. Handles ``Async``/``_Async`` prefixes and the async dunders.
    """
    if name in _ASYNC_RENAMES:
        return _ASYNC_RENAMES[name]
    return re.sub(r"(^|_)Async(?=[A-Z])", r"\1", name)  # AsyncFoo/_AsyncFoo -> Foo/_Foo


class _Normalize(ast.NodeTransformer):
    """Rewrite an async method body into its sync-equivalent canonical form.

    Folds ONLY the mechanical + documented-structural async<->sync differences, so
    any *other* difference (a real bug in one tree) survives and fails the check.
    """

    @staticmethod
    def _is_self_attr(func, attr) -> bool:
        return (
            isinstance(func, ast.Attribute)
            and func.attr == attr
            and isinstance(func.value, ast.Name)
            and func.value.id == "self"
        )

    @classmethod
    def _is_self_call(cls, value, attr) -> bool:
        return isinstance(value, ast.Call) and cls._is_self_attr(value.func, attr)

    @classmethod
    def _is_validate_stmt(cls, stmt) -> bool:
        """``self._maybe_validate_space(...)`` as a statement -- awaited or not."""
        return isinstance(stmt, ast.Expr) and cls._is_self_call(
            stmt.value, "_maybe_validate_space"
        )

    @classmethod
    def _guarded_build_call(cls, validate_stmt, following):
        """The ``_build_space_path`` call in ``following`` that ``validate_stmt`` guards.

        ``None`` unless ``following`` holds exactly one ``self._build_space_path``
        call *for the same space* the validate statement checked. That pairing is
        the whole justification for folding the statement away: only a check that
        immediately precedes -- and covers -- the path being built is equivalent
        to sync doing both inside ``_build_space_path``.
        """
        if following is None or not validate_stmt.value.args:
            return None
        calls = [
            sub
            for sub in ast.walk(following)
            if isinstance(sub, ast.Call)
            and cls._is_self_attr(sub.func, "_build_space_path")
        ]
        if len(calls) != 1 or len(calls[0].args) < 2:
            return None
        validated_space = ast.dump(validate_stmt.value.args[0])
        if ast.dump(calls[0].args[1]) != validated_space:
            return None
        return calls[0]

    def _clean_body(self, node):
        body = list(node.body)
        # Drop the docstring (async examples legitimately say ``await ...``).
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body = body[1:]
        # Space validation: async awaits
        # ``self._maybe_validate_space(space, validate)`` immediately before
        # ``self._build_space_path(base, space)``; sync folds both into
        # ``self._build_space_path(base, space, validate_spaces=validate)``.
        # Canonicalize the async form to the sync form WITHOUT discarding the
        # ``validate`` argument: drop the _maybe_validate_space statement but
        # thread its validate arg into the _build_space_path call it guards. So a
        # drift in which space/flag is validated -- or async omitting validation
        # while sync keeps it -- still surfaces as a body mismatch.
        #
        # The fold is deliberately narrow (#75): it applies ONLY to a genuinely
        # awaited call sitting immediately before the build call for the same
        # space. A forgotten ``await`` (the PR #60 bug: validation silently never
        # runs), a validate-after-build order (#74), a check drifting away from
        # the call it guards, or a check on a different space all leave the
        # statement in place -- so the async body keeps a statement sync does not
        # have and the parity assertion fails, which is the point.
        kept = []
        for index, stmt in enumerate(body):
            if not self._is_validate_stmt(stmt):
                kept.append(stmt)
                continue
            following = body[index + 1] if index + 1 < len(body) else None
            build_call = self._guarded_build_call(stmt, following)
            if not getattr(stmt, _AWAITED_VALIDATE, False) or build_call is None:
                kept.append(stmt)  # not the sanctioned pattern -- let it surface
                continue
            if (
                len(stmt.value.args) >= 2
                and len(build_call.args) == 2
                and not any(k.arg == "validate_spaces" for k in build_call.keywords)
            ):
                build_call.args = build_call.args + [stmt.value.args[1]]
        node.body = kept
        return node

    def visit_AsyncFunctionDef(self, node):
        # Mark real ``await self._maybe_validate_space(...)`` statements BEFORE
        # generic_visit unwraps the Await: afterwards an awaited call and a
        # forgotten-await call are the same tree, and only one of them validates.
        for stmt in node.body:
            if (
                isinstance(stmt, ast.Expr)
                and isinstance(stmt.value, ast.Await)
                and self._is_self_call(stmt.value.value, "_maybe_validate_space")
            ):
                setattr(stmt, _AWAITED_VALIDATE, True)
        sync = ast.FunctionDef(
            name=node.name,
            args=node.args,
            body=node.body,
            decorator_list=[],
            returns=None,
            type_comment=None,
        )
        self.generic_visit(sync)
        return self._clean_body(sync)

    def visit_FunctionDef(self, node):
        node.decorator_list = []
        node.returns = None
        self.generic_visit(node)
        return self._clean_body(node)

    def visit_Await(self, node):
        self.generic_visit(node)
        return node.value

    def visit_AsyncFor(self, node):
        loop = ast.For(
            target=node.target,
            iter=node.iter,
            body=node.body,
            orelse=node.orelse,
            type_comment=None,
        )
        self.generic_visit(loop)
        return loop

    def visit_AsyncWith(self, node):
        block = ast.With(items=node.items, body=node.body, type_comment=None)
        self.generic_visit(block)
        return block

    def visit_Name(self, node):
        node.id = _canon_ident(node.id)
        return node

    def visit_Attribute(self, node):
        self.generic_visit(node)
        node.attr = _canon_ident(node.attr)
        return node

    def visit_arg(self, node):
        node.annotation = None  # annotations legitimately differ between trees
        return node

    def visit_AnnAssign(self, node):
        self.generic_visit(node)
        if node.value is None:
            return None  # bare ``x: T`` -- annotation only, no runtime effect
        return ast.Assign(targets=[node.target], value=node.value, type_comment=None)

    def visit_Call(self, node):
        self.generic_visit(node)
        if self._is_self_attr(node.func, "_build_space_path"):
            # Canonicalize sync's ``validate_spaces`` keyword -> positional 3rd arg
            # so it lines up with the async form (threaded positionally in
            # _clean_body). Positional 3-arg calls are already canonical; anything
            # else is left untouched so real drift surfaces.
            kw = next((k for k in node.keywords if k.arg == "validate_spaces"), None)
            if kw is not None and len(node.args) == 2:
                node.args = node.args + [kw.value]
                node.keywords = [k for k in node.keywords if k.arg != "validate_spaces"]
        return node


def _normalize_src(src: str) -> str:
    """Normalize one method's *source* -- the path both trees and the self-tests use."""
    tree = _Normalize().visit(ast.parse(textwrap.dedent(src)).body[0])
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


def _normalize_body(func) -> str:
    func = inspect.unwrap(func)  # see through any functools.wraps decorator
    return _normalize_src(inspect.getsource(func))


# Methods that legitimately diverge at the sync/async I/O boundary -- the body
# check cannot apply here, so they are excluded by (class, method). Keep this list
# short and justified; adding to it is a conscious "this divergence is intended".
_BODY_DRIFT_ALLOWLIST = {
    # perform_request IS the sync/async boundary: the transport call is sync vs
    # awaited, and two observability string literals differ on purpose ("Making
    # async ..." and span "kibana.async.<verb>"). The other ~85 lines (auth/xsrf
    # headers, rate limiting, secret redaction, error translation) are identical
    # and covered by the dedicated perform_request unit tests; a future refactor
    # extracting just the transport call into a helper would let this be dropped.
    ("Kibana", "perform_request"),
    ("BaseClient", "perform_request"),
    # Async validates the scoped client *after* construction (it cannot await
    # inside __init__); sync validates in the constructor.
    ("Kibana", "space"),
    # close logs the client type -- "AsyncKibana client closed" vs "Kibana client
    # closed" -- an intentional label inside a string literal, which the normalizer
    # deliberately does not rewrite (so it cannot mask a real string-value drift).
    ("Kibana", "close"),
}


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
def test_discovered_the_client_pairs():
    # Sanity: we actually found the fleet of sub-clients, not just Kibana.
    assert len(_PAIRS) > 20


@pytest.mark.parametrize("name,sync_cls,async_cls", _PAIRS, ids=_IDS)
def test_public_member_names_match(name, sync_cls, async_cls):
    sync_names = _public_names(sync_cls)
    async_names = _public_names(async_cls)
    assert sync_names == async_names, (
        f"{name}: sync-only={sorted(sync_names - async_names)} "
        f"async-only={sorted(async_names - sync_names)}"
    )


@pytest.mark.parametrize("name,sync_cls,async_cls", _PAIRS, ids=_IDS)
def test_public_method_signatures_match(name, sync_cls, async_cls):
    for member in sorted(_public_names(sync_cls) & _public_names(async_cls)):
        sync_func = _underlying_func(sync_cls, member)
        async_func = _underlying_func(async_cls, member)
        if sync_func is None or async_func is None:
            continue  # property -- no signature to compare
        sync_shape = _param_shape(sync_func)
        async_shape = _param_shape(async_func)
        assert sync_shape == async_shape, (
            f"{name}.{member} signature drift:\n"
            f"  sync : {sync_shape}\n  async: {async_shape}"
        )


@pytest.mark.parametrize("name,sync_cls,async_cls", _PAIRS, ids=_IDS)
def test_public_method_bodies_match(name, sync_cls, async_cls):
    for member in sorted(_public_names(sync_cls) & _public_names(async_cls)):
        if (name, member) in _BODY_DRIFT_ALLOWLIST:
            continue
        sync_func = _underlying_func(sync_cls, member)
        async_func = _underlying_func(async_cls, member)
        if sync_func is None or async_func is None:
            continue  # property -- no body compared
        sync_body = _normalize_body(sync_func)
        async_body = _normalize_body(async_func)
        assert sync_body == async_body, (
            f"{name}.{member} body drift (a fix may have landed in only one tree). "
            f"If this divergence is intentional and async-boundary-driven, add "
            f'("{name}", "{member}") to _BODY_DRIFT_ALLOWLIST with a reason.\n'
            f"--- normalized sync ---\n{sync_body}\n"
            f"--- normalized async ---\n{async_body}"
        )


# --------------------------------------------------------------------------- #
# Normalizer self-tests -- the guard must not blind itself (#75)
# --------------------------------------------------------------------------- #
# The space-validation fold is the one place the normalizer *removes* a
# statement, so it is the one place it could hide a real bug. These pin what it
# may and may not swallow, using hand-written method pairs rather than the tree:
# they must keep failing even after every namespace has been fixed.
_SYNC_METHOD = """
def get(self, *, id, space_id=None, validate_spaces=None):
    path = self._build_space_path("/api/thing", space_id, validate_spaces=validate_spaces)
    return self.perform_request("GET", path)
"""

_ASYNC_METHOD = """
async def get(self, *, id, space_id=None, validate_spaces=None):
    await self._maybe_validate_space(space_id, validate_spaces)
    path = self._build_space_path("/api/thing", space_id)
    return await self.perform_request("GET", path)
"""

# The PR #60 bug class: the call is still there, so it reads as validated, but
# the coroutine is never awaited and validation silently never happens.
_ASYNC_METHOD_AWAIT_DROPPED = """
async def get(self, *, id, space_id=None, validate_spaces=None):
    self._maybe_validate_space(space_id, validate_spaces)
    path = self._build_space_path("/api/thing", space_id)
    return await self.perform_request("GET", path)
"""

# Issue #74's divergence: the path (and its format check) is built before the
# space is validated, so a malformed id costs a request and the wrong exception.
_ASYNC_METHOD_ORDER_SWAPPED = """
async def get(self, *, id, space_id=None, validate_spaces=None):
    path = self._build_space_path("/api/thing", space_id)
    await self._maybe_validate_space(space_id, validate_spaces)
    return await self.perform_request("GET", path)
"""

# Validation drifting away from the call it guards: anything may run (and fail,
# or issue requests) in between, so it is no longer the same statement pair.
# Its sync twin carries the same intervening statement, so only the detachment
# can make the two bodies differ.
_SYNC_METHOD_WITH_PARAMS = """
def get(self, *, id, space_id=None, validate_spaces=None):
    params = self._build_params(id)
    path = self._build_space_path("/api/thing", space_id, validate_spaces=validate_spaces)
    return self.perform_request("GET", path, params=params)
"""

_ASYNC_METHOD_DETACHED = """
async def get(self, *, id, space_id=None, validate_spaces=None):
    await self._maybe_validate_space(space_id, validate_spaces)
    params = self._build_params(id)
    path = self._build_space_path("/api/thing", space_id)
    return await self.perform_request("GET", path, params=params)
"""

# Validating a different space than the path is built for.
_ASYNC_METHOD_WRONG_SPACE = """
async def get(self, *, id, space_id=None, validate_spaces=None):
    await self._maybe_validate_space(self._default_space_id, validate_spaces)
    path = self._build_space_path("/api/thing", space_id)
    return await self.perform_request("GET", path)
"""


def test_normalizer_folds_the_canonical_validate_then_build_pair():
    """The one intended divergence still normalizes to the sync form."""
    assert _normalize_src(_ASYNC_METHOD) == _normalize_src(_SYNC_METHOD)


@pytest.mark.parametrize(
    "mutant,twin,why",
    [
        (
            _ASYNC_METHOD_AWAIT_DROPPED,
            _SYNC_METHOD,
            "a dropped await (validation never runs)",
        ),
        (
            _ASYNC_METHOD_ORDER_SWAPPED,
            _SYNC_METHOD,
            "path built before the space is validated",
        ),
        (
            _ASYNC_METHOD_DETACHED,
            _SYNC_METHOD_WITH_PARAMS,
            "validation detached from the call it guards",
        ),
        (
            _ASYNC_METHOD_WRONG_SPACE,
            _SYNC_METHOD,
            "a different space validated than built",
        ),
    ],
    ids=["dropped-await", "swapped-order", "detached", "wrong-space"],
)
def test_normalizer_surfaces_broken_space_validation(mutant, twin, why):
    """Only the exact ``await validate`` -> ``build`` pair may be folded away."""
    assert _normalize_src(mutant) != _normalize_src(twin), (
        f"the normalizer hid {why} -- the parity suite would pass a tree with "
        f"this bug in it.\n--- normalized ---\n{_normalize_src(mutant)}"
    )
