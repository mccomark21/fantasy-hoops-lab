import ast
import io
import os
import subprocess
import sys
from pathlib import Path

from fantasyhoops.core.console import use_utf8_output

SRC = Path(__file__).parents[2] / "src" / "fantasyhoops"
COMMANDS = [
    "adds/plan.py",
    "draft/auction.py", "draft/board.py", "draft/publish.py", "draft/rankings.py", "draft/report.py",
    "fetch/espn.py", "fetch/rotation.py", "fetch/yahoo.py",
]


def test_helper_lets_a_cp1252_stream_print_a_name_with_c_caron():
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="cp1252", newline="\n")
    use_utf8_output(stream)
    print("Vasilije Micič", file=stream)
    stream.flush()
    assert raw.getvalue().decode("utf-8") == "Vasilije Micič\n"


def test_helper_skips_a_stream_without_reconfigure():
    use_utf8_output(io.StringIO())


def test_plan_help_sets_piped_stdout_to_utf8():
    """Run the real __main__ block of adds/plan.py with --help. Stdout is a pipe and PYTHONIOENCODING is not set."""
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
    env["PYTHONPATH"] = os.pathsep.join([str(SRC.parent), env.get("PYTHONPATH", "")])
    code = (
        "import runpy, sys\n"
        "sys.argv = ['plan', '--help']\n"
        "try:\n"
        "    runpy.run_module('fantasyhoops.adds.plan', run_name='__main__')\n"
        "except SystemExit:\n"
        "    pass\n"
        "print('ENCODING=' + sys.stdout.encoding)\n"
    )
    result = subprocess.run([sys.executable, "-c", code], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    out = result.stdout.decode("utf-8")
    assert "--no-publish" in out
    assert out.strip().splitlines()[-1].lower().replace("-", "") == "encoding=utf8"


def main_blocks(tree):
    for node in tree.body:
        if (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
                and isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__"):
            yield node


def calls_helper_first(block):
    first = block.body[0]
    return (isinstance(first, ast.Expr) and isinstance(first.value, ast.Call)
            and isinstance(first.value.func, ast.Name) and first.value.func.id == "use_utf8_output")


def test_each_main_block_calls_the_helper_first():
    found = {}
    for path in sorted(SRC.rglob("*.py")):
        blocks = list(main_blocks(ast.parse(path.read_text(encoding="utf-8"))))
        if blocks:
            found[path.relative_to(SRC).as_posix()] = all(calls_helper_first(b) for b in blocks)
    assert set(COMMANDS) <= set(found)
    assert [name for name, ok in found.items() if not ok] == []
