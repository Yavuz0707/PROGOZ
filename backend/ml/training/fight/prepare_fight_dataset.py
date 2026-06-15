import argparse
import json
import random
import shutil
from pathlib import Path


VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".mpeg", ".mpg", ".m4v", ".wmv", ".flv", ".3gp"}
CLASS_ALIASES = {
    "violence": ["violence", "Violence", "VIOLENCE", "violence_temp", "violent", "fight", "fights", "real life violence", "reallifeviolence"],
    "non_violence": [
        "non_violence",
        "non-violence",
        "non violence",
        "nonviolence",
        "nonviolent",
        "normal",
        "normals",
        "nonfight",
        "non_fight",
        "non-fight",
        "no_fight",
        "nofight",
    ],
}


def normalize_name(value: str) -> str:
    return value.lower().replace("_", "").replace("-", "").replace(" ", "")


def find_class_dirs(raw: Path, aliases: list[str]) -> list[Path]:
    normalized_aliases = {normalize_name(alias) for alias in aliases}
    matches = []
    for child in raw.rglob("*") if raw.exists() else []:
        if child.is_dir() and normalize_name(child.name) in normalized_aliases:
            matches.append(child)
    if raw.is_dir() and normalize_name(raw.name) in normalized_aliases:
        matches.append(raw)
    unique: list[Path] = []
    for match in sorted(set(matches)):
        if not any(parent in unique for parent in match.parents):
            unique.append(match)
    return unique


def collect_videos(directory: Path) -> list[Path]:
    return sorted(path for path in directory.rglob("*") if path.suffix.lower() in VIDEO_EXTENSIONS)


def copy_split(files: list[Path], out: Path, label: str, train_ratio: float, val_ratio: float, seed: int) -> dict[str, int]:
    random.Random(seed).shuffle(files)
    total = len(files)
    train_end = int(total * train_ratio)
    val_end = train_end + int(total * val_ratio)
    splits = {
        "train": files[:train_end],
        "val": files[train_end:val_end],
        "test": files[val_end:],
    }
    for split, split_files in splits.items():
        target_dir = out / split / label
        target_dir.mkdir(parents=True, exist_ok=True)
        for index, src in enumerate(split_files):
            safe_parent = "_".join(src.relative_to(src.parents[1]).parts[:-1]) if len(src.parents) > 1 else src.parent.name
            target = target_dir / f"{safe_parent}_{src.stem}_{index}{src.suffix.lower()}"
            shutil.copy2(src, target)
    return {split: len(split_files) for split, split_files in splits.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare fight/non-fight video dataset for PROGOZ.")
    parser.add_argument("--raw", default="ml/datasets/fight/raw")
    parser.add_argument("--out", default="ml/datasets/fight/processed")
    parser.add_argument("--train-ratio", type=float, default=0.70)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--clear", action="store_true", help="Clear output directory before copy")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[3]
    raw = (root / args.raw).resolve() if not Path(args.raw).is_absolute() else Path(args.raw)
    out = (root / args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out)
    if not raw.exists():
        raise SystemExit(
            f"Raw dataset bulunamadi: {raw}\n"
            "Beklenen yapi: raw/violence ve raw/non_violence veya raw/fight ve raw/normal."
        )
    if args.clear and out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, dict] = {}
    for label, aliases in CLASS_ALIASES.items():
        source_dirs = find_class_dirs(raw, aliases)
        if not source_dirs:
            raise SystemExit(f"{label} sinifi icin klasor bulunamadi. Desteklenen adlar: {', '.join(aliases)}")
        files: list[Path] = []
        source_counts: dict[str, int] = {}
        for source_dir in source_dirs:
            source_files = collect_videos(source_dir)
            source_counts[str(source_dir)] = len(source_files)
            files.extend(source_files)
        files = sorted(set(files))
        if not files:
            raise SystemExit(f"{label} sinifi icin bulunan klasorlerde video yok: {source_dirs}")
        split_counts = copy_split(files, out, label, args.train_ratio, args.val_ratio, args.seed)
        manifest[label] = {"total": len(files), "sources": source_counts, "splits": split_counts}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Dataset hazir: {out}")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
