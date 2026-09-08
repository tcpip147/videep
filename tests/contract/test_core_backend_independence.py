import ast
from pathlib import Path

FORBIDDEN = ("cuda", "vulkan", "vaapi", "direct3d", "metal", "nvidia", "pynvvideocodec")


def test_core_does_not_import_backend_specific_modules() -> None:
    for path in Path("src/videep/core").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        assert not [name for name in imports if any(term in name.lower() for term in FORBIDDEN)], (
            path
        )
