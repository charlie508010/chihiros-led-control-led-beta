#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_CONFIGS = {
    "core": ROOT / "chihiros_beta" / "config.yaml",
}
CORE_CACHE_VERSION_FILES = {
    ROOT / "custom_components/chihiros/manifest.json": r'("version"\s*:\s*")\d+\.\d+\.\d+("\s*,?)',
    ROOT / "custom_components/chihiros/www/chihiros-panel.js": (
        r'(chihiros-led-core-card\.js\?v=)\d+\.\d+\.\d+'
    ),
    ROOT / "custom_components/chihiros/www/chihiros-led-core-card.js": (
        r'(chihiros-led-panel\.js\?v=)\d+\.\d+\.\d+'
    ),
}


def parse_version(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", value.strip())
    if not match:
        raise ValueError(f"Invalid version: {value!r}")
    return tuple(int(part) for part in match.groups())


def format_version(parts: tuple[int, int, int]) -> str:
    return f"{parts[0]}.{parts[1]}.{parts[2]}"


def read_current_version(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("version:"):
            match = re.search(r'"([^"]+)"', line)
            if match:
                return match.group(1)
            raise ValueError(f"No quoted version found in {path}")
    raise ValueError(f"No version line found in {path}")


def write_version(path: Path, new_version: str) -> None:
    content = path.read_text(encoding="utf-8")
    updated, count = re.subn(
        r'^(version:\s*")(\d+\.\d+\.\d+)(")', rf"\g<1>{new_version}\3", content, count=1, flags=re.MULTILINE
    )
    if count != 1:
        raise ValueError(f"Could not update version in {path}")
    path.write_text(updated, encoding="utf-8")


def write_core_cache_versions(new_version: str) -> list[Path]:
    """Keep integration and browser cache versions aligned with the Core add-on."""
    updated_paths: list[Path] = []
    for path, pattern in CORE_CACHE_VERSION_FILES.items():
        content = path.read_text(encoding="utf-8")
        replacement = rf"\g<1>{new_version}\2" if path.name == "manifest.json" else rf"\g<1>{new_version}"
        updated, count = re.subn(pattern, replacement, content, count=1)
        if count != 1:
            raise ValueError(f"Could not update Core cache version in {path}")
        path.write_text(updated, encoding="utf-8")
        updated_paths.append(path)
    return updated_paths


def git_output(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Bump Home Assistant add-on versions and optionally commit them.")
    parser.add_argument(
        "--addon",
        choices=("core", "all"),
        default="core",
        help="Add-on version to bump. Device plugins are internal packages now; default: core.",
    )
    parser.add_argument("--version", help="Explicit version to set instead of bumping patch.")
    parser.add_argument("--message", help="Commit message to use after updating the version.")
    parser.add_argument("--commit", dest="message", help="Alias for --message.")
    parser.add_argument(
        "--include-worktree",
        action="store_true",
        help="Stage existing tracked worktree changes together with the version bump.",
    )
    parser.add_argument(
        "--no-include-worktree",
        action="store_true",
        help="Only stage the version file and skip other tracked worktree changes.",
    )
    parser.add_argument("--no-push", action="store_true", help="Commit locally but do not push.")
    parser.add_argument("--no-commit", action="store_true", help="Only update the version file.")
    args = parser.parse_args()

    targets = ["core"] if args.addon == "all" else [args.addon]
    updated_paths: list[Path] = []
    updated_versions: list[tuple[str, str, str]] = []
    for target in targets:
        config_path = ADDON_CONFIGS[target]
        current_version = read_current_version(config_path)
        if args.version:
            if len(targets) > 1:
                raise ValueError("--version can only be used with one --addon target")
            next_version = args.version.strip()
            parse_version(next_version)
        else:
            major, minor, patch = parse_version(current_version)
            next_version = format_version((major, minor, patch + 1))

        if next_version == current_version:
            print(f"{target}: version already at {next_version}; nothing to do.")
            continue

        write_version(config_path, next_version)
        updated_paths.append(config_path)
        if target == "core":
            updated_paths.extend(write_core_cache_versions(next_version))
        updated_versions.append((target, current_version, next_version))
        print(f"Updated {config_path.relative_to(ROOT)}: {current_version} -> {next_version}")

    if not updated_paths:
        return 0

    if args.no_commit:
        return 0

    if args.message:
        commit_message = args.message
    elif len(updated_versions) == 1:
        target, _old, new = updated_versions[0]
        commit_message = f"chore: bump {target} addon version to {new}"
    else:
        commit_message = "chore: bump addon versions"

    subprocess.run(["git", "add", *[str(path.relative_to(ROOT)) for path in updated_paths]], cwd=ROOT, check=True)
    include_worktree = not args.no_include_worktree
    if args.include_worktree:
        include_worktree = True
    if include_worktree:
        subprocess.run(["git", "add", "-A"], cwd=ROOT, check=True)
    subprocess.run(["git", "commit", "-m", commit_message], cwd=ROOT, check=True)
    commit_hash = git_output("rev-parse", "--short", "HEAD")
    branch = git_output("branch", "--show-current")
    print(f"Committed as {commit_hash}: {commit_message}")
    if not args.no_push:
        push_target = ["git", "push"]
        if branch:
            push_target.extend(["origin", branch])
            print(f"Pushing to origin/{branch} ...")
        else:
            print("Pushing ...")
        subprocess.run(push_target, cwd=ROOT, check=True)
        print("Push complete.")
    else:
        print("Push skipped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
