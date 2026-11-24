"""Build deterministic skill archives or compare them with the current sources."""
import argparse
import io
from pathlib import Path
import tempfile
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]


def package(skill):
    files = {p.relative_to(skill).as_posix(): p.read_bytes()
             for p in skill.rglob("*") if p.is_file()
             and "__pycache__" not in p.parts and p.suffix != ".pyc"
             and not any(part.startswith(".") for part in p.relative_to(skill).parts)}
    if "SKILL.md" not in files:
        raise ValueError(f"Missing SKILL.md in {skill}")
    files["LICENSE"] = (ROOT / "LICENSE").read_bytes()
    for name in files:
        if name == "LICENSE" or Path(name).suffix in {".md", ".py"}:
            files[name] = files[name].replace(b"\r\n", b"\n")
    buf = io.BytesIO()
    with ZipFile(buf, "w") as archive:
        for name, data in sorted(files.items()):
            info = ZipInfo(f"{skill.name}/{name}")
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compress_type=ZIP_DEFLATED)
    return buf.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    releases = ROOT / "releases"
    problems = []
    if not args.check:
        releases.mkdir(exist_ok=True)
    skills = sorted(p for p in (ROOT / "skills").iterdir() if p.is_dir())
    for skill in skills:
        dest = releases / f"{skill.name}.zip"
        data = package(skill)
        if args.check:
            # Compare contents so differing zlib versions do not cause false failures.
            with ZipFile(io.BytesIO(data)) as expected:
                if not dest.exists():
                    problems.append(dest.name)
                    continue
                with ZipFile(dest) as actual:
                    if sorted(actual.namelist()) != sorted(expected.namelist()) or any(
                        actual.read(n) != expected.read(n) for n in expected.namelist()
                    ):
                        problems.append(dest.name)
        else:
            with tempfile.NamedTemporaryFile(dir=releases, delete=False) as tmp:
                tmp.write(data)
            Path(tmp.name).replace(dest)
    problems.extend(p.name for p in releases.glob("*.zip") if p.stem not in {s.name for s in skills})
    if problems:
        raise SystemExit("Review release archives: " + ", ".join(problems))
    print(f"{'Checked' if args.check else 'Built'} {len(skills)} skill archives.")


if __name__ == "__main__":
    main()
