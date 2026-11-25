"""Validate the YAML consumed by skill loaders. CI-only dependency: PyYAML."""
from pathlib import Path
from zipfile import ZipFile

import yaml

root = Path(__file__).resolve().parents[1]
for path in sorted((root / "skills").glob("*/SKILL.md")):
    name = path.parent.name
    with ZipFile(root / "releases" / f"{name}.zip") as archive:
        packed = archive.read(f"{name}/SKILL.md").decode("utf-8")
    for label, text in ((str(path), path.read_text(encoding="utf-8")), (f"{name}.zip", packed)):
        try:
            fields = yaml.safe_load(text.split("---", 2)[1])
            if fields["name"] != name or not isinstance(fields["description"], str):
                raise ValueError("invalid name or description")
        except (yaml.YAMLError, IndexError, KeyError, TypeError, ValueError) as error:
            raise SystemExit(f"{label}: {error}")
print("Source and packaged skill frontmatter passed.")
