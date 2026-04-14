import os
import ast
import json
from pathlib import Path


def extract_module_info(py_path, root_dir):
    rel_path = os.path.relpath(py_path, root_dir)
    package = rel_path.split(os.sep)[1] if os.sep in rel_path else "root"
    module = os.path.splitext(os.path.basename(py_path))[0]
    with open(py_path, "r", encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source, filename=py_path)
    functions = []
    classes = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef):
            functions.append(
                {
                    "name": node.name,
                    "line": node.lineno,
                    "description": ast.get_docstring(node) or "",
                    "kind": "function",
                }
            )
        elif isinstance(node, ast.ClassDef):
            classes.append(
                {
                    "name": node.name,
                    "line": node.lineno,
                    "description": ast.get_docstring(node) or "",
                    "bases": [b.id if isinstance(b, ast.Name) else getattr(b, "attr", str(b)) for b in node.bases],
                    "methods": [
                        {"name": n.name, "line": n.lineno, "description": ast.get_docstring(n) or "", "kind": "method"}
                        for n in node.body
                        if isinstance(n, ast.FunctionDef)
                    ],
                }
            )
    return {
        "path": rel_path.replace("\\", "/"),
        "package": package,
        "module": module,
        "description": ast.get_docstring(tree) or f"Provides `{module}` module logic.",
        "functions": functions,
        "classes": classes,
    }


def scan_src_tree(src_dir):
    modules = []
    for dirpath, _, filenames in os.walk(src_dir):
        for fn in filenames:
            if fn.endswith(".py") and not fn.startswith("__init__"):
                py_path = os.path.join(dirpath, fn)
                modules.append(extract_module_info(py_path, root_dir=src_dir.parent))
    return modules


def main():
    src_dir = Path(__file__).parent / "src"
    modules = scan_src_tree(src_dir)
    metadata = {"root": "main.py", "generated_from": "src/**/*.py", "module_count": len(modules), "modules": modules}
    out_path = Path(__file__).parent / "Documentation" / "module_metadata.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"Wrote {out_path} with {len(modules)} modules.")


if __name__ == "__main__":
    main()
