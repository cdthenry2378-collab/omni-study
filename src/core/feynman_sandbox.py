"""Restricted subprocess runner for short educational code snippets."""
from __future__ import annotations
from dataclasses import dataclass
import ast, os, subprocess, sys, tempfile
from pathlib import Path

@dataclass
class ExecutionResult:
    ok: bool
    stdout: str
    stderr: str
    returncode: int
    error_line: int | None = None

class FeynmanSandbox:
    """Runs a snippet in a fresh Python process with timeout and output limits.

    This is defense-in-depth, not a hardened security boundary against hostile code.
    Do not run untrusted code on a machine containing sensitive data.
    """
    def __init__(self, timeout_seconds: float = 3.0, output_limit: int = 20000):
        self.timeout_seconds = max(0.2, min(timeout_seconds, 30))
        self.output_limit = max(1000, output_limit)

    def run(self, source: str) -> ExecutionResult:
        if len(source) > 100_000:
            raise ValueError("Code input exceeds 100 KB.")
        try:
            ast.parse(source)
        except SyntaxError as exc:
            return ExecutionResult(False, "", f"SyntaxError: {exc.msg}", 1, exc.lineno)
        bootstrap = (
            "import builtins, os, sys\n"
            "os.environ.clear()\n"
            "sys.path[:] = [p for p in sys.path if 'site-packages' in p or p.endswith('python.zip')]\n"
            "try:\n"
            + "".join("    " + line for line in source.splitlines(keepends=True))
            + "\nexcept BaseException as e:\n"
              "    print(f'{type(e).__name__}: {e}', file=sys.stderr)\n"
              "    raise\n"
        )
        with tempfile.TemporaryDirectory(prefix="omnistudy-sandbox-") as temp:
            script = Path(temp) / "snippet.py"
            script.write_text(bootstrap, encoding="utf-8")
            env = {"PYTHONIOENCODING": "utf-8", "PYTHONNOUSERSITE": "1"}
            try:
                completed = subprocess.run(
                    [sys.executable, "-I", str(script)], cwd=temp, env=env,
                    capture_output=True, text=True, timeout=self.timeout_seconds,
                    check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                )
                stdout = completed.stdout[-self.output_limit:]
                stderr = completed.stderr[-self.output_limit:]
                line = None
                for item in reversed(stderr.splitlines()):
                    if 'line ' in item:
                        try: line = int(item.split('line ', 1)[1].split(',', 1)[0].split()[0])
                        except ValueError: pass
                        if line: break
                return ExecutionResult(completed.returncode == 0, stdout, stderr,
                                       completed.returncode, line)
            except subprocess.TimeoutExpired as exc:
                return ExecutionResult(False, str(exc.stdout or "")[-self.output_limit:],
                                       f"Execution timed out after {self.timeout_seconds:g}s.",
                                       124, None)
            except OSError as exc:
                return ExecutionResult(False, "", f"Could not start Python runtime: {exc}", 126, None)

    def evaluate_expression(self, expression: str) -> ExecutionResult:
        # Expression mode deliberately accepts arithmetic AST only.
        try:
            tree = ast.parse(expression, mode="eval")
            allowed = (ast.Expression, ast.Constant, ast.BinOp, ast.UnaryOp, ast.Add, ast.Sub,
                       ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.USub, ast.UAdd,
                       ast.Load, ast.Name)
            names = {"pi": "3.141592653589793", "e": "2.718281828459045"}
            for node in ast.walk(tree):
                if not isinstance(node, allowed) or (isinstance(node, ast.Name) and node.id not in names):
                    raise ValueError("Only arithmetic expressions and pi/e are allowed.")
            expression = expression.replace("pi", names["pi"]).replace("e", names["e"])
            return self.run(f"print({expression})")
        except (SyntaxError, ValueError) as exc:
            return ExecutionResult(False, "", str(exc), 1, getattr(exc, "lineno", None))
