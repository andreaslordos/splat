from pathlib import Path

from splat.cli.init import detect_github_remote


def test_detect_github_remote_stripping_bug(tmp_path: Path) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    config = git_dir / "config"

    # Case 1: URL with .git extension
    config.write_text(
        '[remote "origin"]\n    url = https://github.com/andreaslordos/splat.git'
    )
    assert detect_github_remote(tmp_path) == "andreaslordos/splat"

    # Case 2: URL without .git extension
    config.write_text(
        '[remote "origin"]\n    url = https://github.com/andreaslordos/splat'
    )
    assert detect_github_remote(tmp_path) == "andreaslordos/splat"

    # Case 3: Repo ending in 't' (the reported bug - rstrip removes 't')
    config.write_text(
        '[remote "origin"]\n    url = https://github.com/andreaslordos/splat.git'
    )
    # The bug makes this "spla" because rstrip(".git") strips chars from the set
    assert detect_github_remote(tmp_path) == "andreaslordos/splat"

    # Case 4: SSH URL with .git extension
    config.write_text(
        '[remote "origin"]\n    url = git@github.com:andreaslordos/splat.git'
    )
    assert detect_github_remote(tmp_path) == "andreaslordos/splat"

    # Case 5: Repo name ending in 'g' (another char in .git set)
    config.write_text('[remote "origin"]\n    url = https://github.com/owner/blog.git')
    assert detect_github_remote(tmp_path) == "owner/blog"
