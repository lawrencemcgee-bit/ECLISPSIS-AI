"""
CodingService — local static code analysis. No execution, ever.

The codebase's own SafetyRules permanently blocks "run_shell_command" —
a hard policy no permission can override (see safety_rules.py). This
service respects that by design, not just by convention: it never calls
subprocess, eval, exec, or anything that runs the code it's handed. It
only parses and inspects text.

Python gets real structural analysis via the standard library's `ast`
module: syntax validity, function/class/import inventory, docstring
coverage, a simple per-function complexity proxy (branch/loop keyword
count), long-function and TODO/FIXME flags. Other languages get an
honest, much shallower pass — line/comment counts, brace balance, TODO
flags — since parsing them correctly would need a real per-language
parser this project doesn't have; the result says so explicitly rather
than pretending non-Python gets the same depth.

Diffing (any language) is a real unified diff via the standard library's
`difflib`, plus a short added/removed/changed line summary.
"""

import ast
import difflib
import re


_TODO_PATTERN = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b[:\s]?", re.IGNORECASE)
_BRANCH_KEYWORDS = (ast.If, ast.For, ast.While, ast.Try, ast.With,
                    ast.BoolOp, ast.ExceptHandler)


class CodingService:
    def analyze(self, code: str, language: str = "python") -> dict:
        code = code or ""
        lines = code.splitlines()
        base = {
            "language": language,
            "line_count": len(lines),
            "blank_lines": sum(1 for l in lines if not l.strip()),
            "todo_flags": self._find_todos(lines),
        }

        if language.lower() in ("python", "py"):
            base.update(self._analyze_python(code))
        else:
            base.update(self._analyze_generic(code, lines))
            base["note"] = (
                f"'{language}' has no dedicated parser here — this is a shallow "
                "text-level pass (comments, brace balance, TODOs), not a real "
                "structural analysis like Python gets via ast."
            )

        return base

    def diff(self, old_code: str, new_code: str, old_label: str = "before", new_label: str = "after") -> dict:
        old_lines = (old_code or "").splitlines(keepends=True)
        new_lines = (new_code or "").splitlines(keepends=True)
        diff_lines = list(difflib.unified_diff(
            old_lines, new_lines, fromfile=old_label, tofile=new_label,
        ))

        added = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))

        return {
            "diff": "".join(diff_lines),
            "lines_added": added,
            "lines_removed": removed,
            "identical": added == 0 and removed == 0,
        }

    # -----------------------------------------------------------------
    def _find_todos(self, lines: list) -> list:
        hits = []
        for i, line in enumerate(lines, start=1):
            if _TODO_PATTERN.search(line):
                hits.append({"line": i, "text": line.strip()})
        return hits

    def _analyze_python(self, code: str) -> dict:
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return {
                "valid_syntax": False,
                "syntax_error": {
                    "message": exc.msg,
                    "line": exc.lineno,
                    "offset": exc.offset,
                },
            }

        functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        imports = self._collect_imports(tree)
        unused_imports = self._find_unused_imports(code, imports)

        documented_functions = sum(1 for f in functions if ast.get_docstring(f))
        documented_classes = sum(1 for c in classes if ast.get_docstring(c))
        total_documentable = len(functions) + len(classes)
        doc_coverage = (
            round((documented_functions + documented_classes) / total_documentable * 100, 1)
            if total_documentable else None
        )

        long_functions = []
        complex_functions = []
        for f in functions:
            length = (f.end_lineno - f.lineno + 1) if hasattr(f, "end_lineno") and f.end_lineno else None
            if length and length > 50:
                long_functions.append({"name": f.name, "line": f.lineno, "length": length})
            branch_count = sum(1 for n in ast.walk(f) if isinstance(n, _BRANCH_KEYWORDS))
            if branch_count > 10:
                complex_functions.append({"name": f.name, "line": f.lineno, "branch_count": branch_count})

        return {
            "valid_syntax": True,
            "function_count": len(functions),
            "class_count": len(classes),
            "import_count": len(imports),
            "unused_imports": unused_imports,
            "docstring_coverage_pct": doc_coverage,
            "long_functions": long_functions,
            "high_complexity_functions": complex_functions,
        }

    def _collect_imports(self, tree) -> list:
        names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    names.append(alias.asname or alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    names.append(alias.asname or alias.name)
        return names

    def _find_unused_imports(self, code: str, imports: list) -> list:
        """Heuristic, not a real usage-graph analysis: counts textual
        occurrences of the imported name elsewhere in the source. A name
        that appears only once (its own import line) is flagged. Can
        false-negative on shadowed names or `__all__` exports — a real
        linter (pyflakes/ruff) does this properly; this is a lightweight
        local approximation consistent with the rest of this service's
        scope."""
        unused = []
        for name in set(imports):
            occurrences = len(re.findall(r"\b" + re.escape(name) + r"\b", code))
            if occurrences <= 1:
                unused.append(name)
        return sorted(unused)

    def _analyze_generic(self, code: str, lines: list) -> dict:
        comment_lines = sum(
            1 for l in lines
            if l.strip().startswith(("//", "#", "/*", "*", "--"))
        )
        opens = sum(code.count(c) for c in "({[")
        closes = sum(code.count(c) for c in ")}]")
        return {
            "comment_lines": comment_lines,
            "brace_balance": opens - closes,
            "braces_balanced": opens == closes,
        }
