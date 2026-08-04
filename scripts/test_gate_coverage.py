#!/usr/bin/env python3
"""Direct unit tests for scripts/gate_coverage.py (#56 Ralph Tier 2 finding F5).

The module every gate's coverage floor is built on had no test of its own. It
was exercised only indirectly, through the subprocess-level runs of its three
callers, which means a change to its behaviour would surface as a confusing
failure somewhere else -- or, if the change made it more permissive, as nothing
at all. A helper whose job is to fail loudly is exactly the kind that stops
failing silently.

These tests assert the MESSAGE, not just the raised type. `require_examined`
declining is only useful if it says which surface came back empty and what the
operator should do, and an assertion on the exception class alone would keep
passing if the message degraded to "error".
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

_spec = importlib.util.spec_from_file_location("gate_coverage", SCRIPTS / "gate_coverage.py")
gc = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = gc
_spec.loader.exec_module(gc)


class TestRequireExamined:
    def test_zero_raises_with_the_surface_named(self, capsys):
        with pytest.raises(gc.VacuousGate) as exc:
            gc.require_examined("mygate", "tracked image", [], hint="rebuild first")
        assert exc.value.code == 2, "a coverage failure must exit 2, not 1"
        err = capsys.readouterr().err
        assert "vacuous-gate" in err and "mygate" in err
        assert "0 tracked image" in err, f"the surface must be named: {err!r}"
        assert "rebuild first" in err, "the hint tells the operator what to DO"

    def test_nonzero_returns_the_count_and_stays_silent(self, capsys):
        assert gc.require_examined("g", "page", ["a", "b"], hint="x") == 2
        assert capsys.readouterr().err == "", "a satisfied floor must not chatter"

    def test_accepts_a_bare_int(self):
        """Callers that already counted must not be forced to build a list."""
        assert gc.require_examined("g", "page", 7, hint="x") == 7
        with pytest.raises(gc.VacuousGate):
            gc.require_examined("g", "page", 0, hint="x")

    def test_negative_count_is_treated_as_empty(self):
        """A negative count is a broken caller, and must not read as satisfied."""
        with pytest.raises(gc.VacuousGate):
            gc.require_examined("g", "page", -1, hint="x")


class TestRequireReadable:
    def test_raises_naming_the_file_the_error_and_the_remedy(self, capsys):
        with pytest.raises(gc.VacuousGate) as exc:
            raise gc.require_readable(
                "mygate", Path("/tmp/broken.png"), ValueError("bad header"),
                remedy="re-export it")
        assert exc.value.code == 2
        err = capsys.readouterr().err
        assert "/tmp/broken.png" in err
        assert "bad header" in err, "the underlying error must survive"
        assert "re-export it" in err
        assert "indistinguishable from a clean one" in err, (
            "the message must say WHY an empty result is not acceptable here; "
            "that reasoning is the whole point of the helper"
        )


class TestFail:
    def test_writes_to_stderr_not_stdout(self, capsys):
        """A coverage failure on stdout would be swallowed by callers that
        capture only stderr, and would pollute gates whose stdout is parsed."""
        with pytest.raises(gc.VacuousGate):
            gc.fail("g", "boom")
        out = capsys.readouterr()
        assert out.out == ""
        assert "boom" in out.err

    def test_exit_code_is_two(self):
        with pytest.raises(SystemExit) as exc:
            gc.fail("g", "boom")
        assert exc.value.code == gc.EXIT_VACUOUS == 2

    def test_is_a_systemexit_so_an_unhandled_one_still_exits_2(self):
        """Gates call this without a handler; if it stopped being SystemExit the
        process would exit 1 with a traceback and read as a crash, not a verdict."""
        assert issubclass(gc.VacuousGate, SystemExit)
