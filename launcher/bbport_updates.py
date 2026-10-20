# SPDX-License-Identifier: GPL-2.0-or-later
"""Safe source checkout update checks for the GTK launcher."""

import subprocess
from pathlib import Path


class UpdateError(RuntimeError):
    pass


def _git(repo, *args, timeout=30):
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True, text=True,
            timeout=timeout, check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise UpdateError(str(error)) from error
    if result.returncode:
        message = result.stderr.strip() or result.stdout.strip() or f"git {' '.join(args)} failed"
        raise UpdateError(message)
    return result.stdout.strip()


def check_for_updates(repo):
    """Fetch origin and summarize changes without touching checked-out files."""
    repo = Path(repo)
    branch = _git(repo, "branch", "--show-current")
    if not branch:
        raise UpdateError("This checkout is detached; switch to a branch to receive updates.")
    upstream_result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
        capture_output=True, text=True, check=False,
    )
    upstream = upstream_result.stdout.strip() if upstream_result.returncode == 0 else ""
    _git(repo, "fetch", "--quiet", "origin", timeout=60)
    target = upstream or f"origin/{branch}"
    remote_head = _git(repo, "rev-parse", "--verify", target)
    head = _git(repo, "rev-parse", "HEAD")
    count = int(_git(repo, "rev-list", "--count", f"HEAD..{target}"))
    clean = not bool(_git(repo, "status", "--porcelain", "--untracked-files=normal"))
    fast_forward = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", "HEAD", target],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    ).returncode == 0

    commits = []
    changed_files = []
    submodule_changes = []
    if count:
        log = _git(repo, "log", "--format=%h%x09%s", "--reverse", "--max-count=40", f"HEAD..{target}")
        commits = [tuple(line.split("\t", 1)) for line in log.splitlines() if "\t" in line]
        names = _git(repo, "diff", "--name-status", "HEAD", target)
        changed_files = [line for line in names.splitlines() if line][:80]
        raw = _git(repo, "diff", "--raw", "HEAD", target)
        for line in raw.splitlines():
            if line.startswith(":") and "\t" in line:
                modes, path = line[1:].split("\t", 1)
                if "160000" in modes.split():
                    submodule_changes.append(path)

    return {
        "branch": branch,
        "target": target,
        "head": head,
        "remote_head": remote_head,
        "count": count,
        "clean": clean,
        "fast_forward": fast_forward,
        "commits": commits,
        "changed_files": changed_files,
        "submodule_changes": submodule_changes,
    }


def apply_update(repo, target, expected_head):
    """Fast-forward a clean checkout only; never stash, reset, or update submodules."""
    repo = Path(repo)
    head = _git(repo, "rev-parse", "HEAD")
    if head != expected_head:
        raise UpdateError("The local branch changed after the update check. Check again first.")
    if _git(repo, "status", "--porcelain", "--untracked-files=normal"):
        raise UpdateError("Local files changed. Save or commit them before applying the update.")
    if subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", "HEAD", target],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    ).returncode:
        raise UpdateError("The remote branch cannot be applied as a fast-forward. Resolve branches manually.")

    raw = _git(repo, "diff", "--raw", "HEAD", target)
    for line in raw.splitlines():
        if line.startswith(":") and "\t" in line:
            modes, path = line[1:].split("\t", 1)
            if "160000" in modes.split():
                raise UpdateError(f"The update changes submodule {path}; update it manually after reviewing it.")

    changed_files = _git(repo, "diff", "--name-only", "HEAD", target).splitlines()
    old_head = head
    _git(repo, "merge", "--ff-only", "--no-edit", target, timeout=90)
    new_head = _git(repo, "rev-parse", "HEAD")

    native_build_changed = any(
        path.startswith(("gpu/", "src/", "cp/", "shim/"))
        or path in ("CMakeLists.txt", "build.sh")
        for path in changed_files
    )
    if native_build_changed:
        marker = repo / "out" / ".bbport-rebuild-required"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(f"{new_head}\n", encoding="utf-8")
    return {"old_head": old_head, "new_head": new_head, "rebuild": native_build_changed}
