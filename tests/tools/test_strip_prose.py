"""Hermetic tests for ``tools/strip_prose.py`` (code-halving plan S4).

Covers the behaviours the strip must never get wrong: idempotence, a function
whose whole body is a docstring, marker comments (``noqa``/``type:``/``pragma``/
``fmt:``/shebang/encoding cookie) surviving, docstrings that are read at run time
surviving, non-ASCII column arithmetic, strings that merely look like docstrings
being left alone, the ``shared/`` refusal, and AST equivalence.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
import textwrap
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "tools" / "strip_prose.py"


def _load_strip_prose_module():
    spec = importlib.util.spec_from_file_location("strip_prose", _MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


sp = _load_strip_prose_module()


def _strip(source: str) -> str:
    return sp.strip_source(textwrap.dedent(source).lstrip("\n"))


def _roundtrip(source: str) -> str:
    """Strip, assert AST equivalence and idempotence, return the stripped text."""
    original = textwrap.dedent(source).lstrip("\n")
    stripped = sp.strip_source(original)
    sp.verify_equivalent(original, stripped)
    assert sp.strip_source(stripped) == stripped, "second pass changed the file"
    return stripped


# --------------------------------------------------------------------------
# docstrings
# --------------------------------------------------------------------------


def test_docstring_keeps_only_the_first_line():
    stripped = _roundtrip('''
        """Summary line.

        Several paragraphs of rationale that cite a plan and a review round.
        """
        X = 1
        ''')
    assert stripped == '"""Summary line."""\nX = 1\n'


def test_docstring_opening_with_a_newline_uses_the_first_non_empty_line():
    stripped = _roundtrip('''
        def f():
            """
            Summary line.

            detail
            """
            return 1
        ''')
    assert '"""Summary line."""' in stripped
    assert "detail" not in stripped


def test_function_whose_body_is_only_a_docstring_keeps_a_valid_body():
    stripped = _roundtrip('''
        def f():
            """Only a docstring here.

            and prose
            """


        class C:
            """Only a docstring here too.

            and prose
            """
        ''')
    module = ast.parse(stripped)
    for node in ast.walk(module):
        if isinstance(node, ast.FunctionDef | ast.ClassDef):
            assert node.body, f"{node.name} lost its body"
    assert stripped.count('"""Only a docstring here.') == 1
    assert "and prose" not in stripped


def test_empty_docstring_degrades_to_an_empty_string_literal():
    stripped = _roundtrip('''
        def f():
            """

            """
        ''')
    assert ast.parse(stripped).body[0].body[0].value.value == ""  # type: ignore[attr-defined]


def test_docstring_containing_a_triple_quote_falls_back_to_repr():
    stripped = _roundtrip("""
        def f():
            '''A line with \\"\\"\\" inside.

            prose
            '''
            return 1
        """)
    doc = ast.get_docstring(ast.parse(stripped).body[0])  # type: ignore[arg-type]
    assert doc == 'A line with """ inside.'


def test_docstring_with_a_backslash_keeps_its_value_exactly():
    # A raw docstring: the two source backslashes are two characters of value,
    # so a naive re-emission as a plain string would silently change it.
    original = 'def f():\n    r"""Path C:\\\\x and more.\n\n    prose\n    """\n'
    before = ast.get_docstring(ast.parse(original).body[0])  # type: ignore[arg-type]
    assert before is not None and before.startswith("Path C:\\\\x and more.")
    stripped = sp.strip_source(original)
    sp.verify_equivalent(original, stripped)
    assert sp.strip_source(stripped) == stripped
    assert ast.get_docstring(ast.parse(stripped).body[0]) == "Path C:\\\\x and more."  # type: ignore[arg-type]
    assert "prose" not in stripped


def test_a_string_that_is_not_the_first_statement_is_untouched():
    stripped = _roundtrip('''
        X = 1
        """This looks like a docstring but is a bare expression.

        It keeps every line.
        """
        ''')
    assert "It keeps every line." in stripped


def test_multiline_strings_and_fstrings_in_code_are_untouched():
    stripped = _roundtrip('''
        """Doc.

        prose
        """
        TEMPLATE = """line one
        line two  # not a comment
        """
        NAME = "x"
        MESSAGE = f"""hello {NAME}
        second line
        """
        ''')
    assert "line two  # not a comment" in stripped
    assert "second line" in stripped
    assert "prose" not in stripped


# --------------------------------------------------------------------------
# comments
# --------------------------------------------------------------------------


def test_comment_only_lines_are_deleted_and_markers_are_kept():
    stripped = _roundtrip("""
        #!/usr/bin/env python3
        # -*- coding: utf-8 -*-
        # plain prose comment
        # noqa line kept
        # fmt: off
        X = [
            1,
            # prose inside brackets
            2,
        ]
        # fmt: on
        """)
    assert stripped.splitlines()[0] == "#!/usr/bin/env python3"
    assert "# -*- coding: utf-8 -*-" in stripped
    assert "# noqa line kept" in stripped
    assert "# fmt: off" in stripped
    assert "# fmt: on" in stripped
    assert "plain prose comment" not in stripped
    assert "prose inside brackets" not in stripped


def test_inline_comments_are_stripped_unless_they_carry_a_marker():
    stripped = _roundtrip("""
        import os  # noqa: F401
        X = 1  # trailing prose
        Y = 2  # type: int
        Z = 3  # pragma: no cover
        """)
    assert "import os  # noqa: F401" in stripped
    assert "Y = 2  # type: int" in stripped
    assert "Z = 3  # pragma: no cover" in stripped
    assert "X = 1\n" in stripped
    assert "trailing prose" not in stripped


def test_shebang_is_only_kept_on_the_first_line():
    stripped = _roundtrip("""
        X = 1
        #!not a shebang here
        Y = 2
        """)
    assert "not a shebang here" not in stripped


def test_non_ascii_lines_keep_their_code_intact():
    stripped = _roundtrip('''
        """한글 요약 줄.

        긴 설명 문단.
        """
        한글 = "값"  # 한글 주석
        X = {"키": "값"}  # noqa: E501 한글 마커 주석
        ''')
    assert '한글 = "값"\n' in stripped
    assert 'X = {"키": "값"}  # noqa: E501 한글 마커 주석' in stripped
    assert "긴 설명 문단." not in stripped
    assert '"""한글 요약 줄."""' in stripped


def test_comment_on_the_line_closing_a_multiline_docstring():
    stripped = _roundtrip('''
        def f():
            """Summary.

            prose
            """  # trailing prose
            return 1
        ''')
    assert '"""Summary."""' in stripped
    assert "trailing prose" not in stripped


# --------------------------------------------------------------------------
# docstrings read at run time
# --------------------------------------------------------------------------


def test_module_docstring_survives_a_bare_dunder_doc_read():
    source = textwrap.dedent('''
        """Tool summary.

        Long help text that argparse prints.
        """
        import argparse


        def main():
            return argparse.ArgumentParser(description=__doc__)
        ''').lstrip("\n")
    stripped = _roundtrip(source)
    assert "Long help text that argparse prints." in stripped


def test_named_docstring_survives_a_qualified_dunder_doc_read():
    stripped = _roundtrip('''
        """Module summary.

        module prose
        """


        def criterion():
            """Criterion summary.

            The wording below is the criterion itself.
            """


        def other():
            """Other summary.

            other prose
            """


        def read():
            return criterion.__doc__
        ''')
    assert "The wording below is the criterion itself." in stripped
    assert "other prose" not in stripped
    assert "module prose" not in stripped


# --------------------------------------------------------------------------
# equivalence / safety
# --------------------------------------------------------------------------


def test_verify_equivalent_rejects_a_change_outside_docstrings():
    before = 'def f():\n    """Doc."""\n    return 1\n'
    after = 'def f():\n    """Doc."""\n    return 2\n'
    with pytest.raises(sp.StripError):
        sp.verify_equivalent(before, after)


def test_verify_equivalent_accepts_a_docstring_only_change():
    before = 'def f():\n    """Doc.\n\n    prose\n    """\n    return 1\n'
    sp.verify_equivalent(before, sp.strip_source(before))


def test_forbidden_roots_are_never_selected(tmp_path):
    (tmp_path / "shared" / "decision" / "setups").mkdir(parents=True)
    witness = tmp_path / "shared" / "decision" / "setups" / "vwap_reversion.py"
    witness.write_text('"""Witness.\n\nprose\n"""\n', encoding="utf-8")
    (tmp_path / "tos" / "src").mkdir(parents=True)
    kernel = tmp_path / "tos" / "src" / "mod.py"
    kernel.write_text('"""Kernel.\n\nprose\n"""\n', encoding="utf-8")

    selected = sp.iter_files(["shared", "tos/src"], tmp_path)
    assert kernel in selected
    assert witness not in selected


def test_write_mode_rewrites_only_in_scope_files(tmp_path, capsys):
    (tmp_path / "tos" / "src").mkdir(parents=True)
    target = tmp_path / "tos" / "src" / "mod.py"
    target.write_text('"""Kernel.\n\nprose\n"""\nX = 1  # prose\n', encoding="utf-8")

    assert sp.main(["--check", "--root", str(tmp_path), "tos/src"]) == 1
    assert target.read_text(encoding="utf-8").count("prose") == 2

    assert sp.main(["--write", "--root", str(tmp_path), "tos/src"]) == 0
    assert target.read_text(encoding="utf-8") == '"""Kernel."""\nX = 1\n'

    assert sp.main(["--check", "--root", str(tmp_path), "tos/src"]) == 0
    assert sp.main(["--verify", "--root", str(tmp_path), "tos/src"]) == 0
    capsys.readouterr()


def test_real_scope_is_strippable_and_behaviour_preserving():
    """Every in-scope file parses, verifies and is idempotent -- no writes."""
    files = sp.iter_files(sp.DEFAULT_SCOPE, _REPO_ROOT)
    assert len(files) > 500, "the S4 scope should cover the tos trees"
    for path in files:
        source = path.read_bytes().decode("utf-8")
        stripped = sp.strip_source(source)
        sp.verify_equivalent(source, stripped)
        assert sp.strip_source(stripped) == stripped, path
