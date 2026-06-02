#!/usr/bin/env python3
"""
One-time git setup script.
Offers project rename options, creates .gitignore, inits git,
and pushes to a new GitHub repo via the `gh` CLI.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from rich.console import Console
from rich.panel import Panel

console = Console()

PROJECT_ROOT = Path(__file__).parent.resolve()

NAME_SUGGESTIONS = [
    ("freelance-quote-cli",  "Recommended — clear, professional, searchable"),
    ("web-quote-wizard",     "Friendly name, easy to remember"),
    ("quote-forge",          "Short and punchy"),
    ("dev-pricer",           "Developer-focused, minimal"),
    ("project-pricer",       "Generic, works for any freelance domain"),
    ("keep",                 f"Keep current name  ({PROJECT_ROOT.name})"),
]


def _run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd or PROJECT_ROOT, check=check, capture_output=True, text=True)


def _gh_installed() -> bool:
    return shutil.which("gh") is not None


def _git_installed() -> bool:
    return shutil.which("git") is not None


def _already_git_repo(path: Path) -> bool:
    return (path / ".git").exists()


def choose_name() -> str | None:
    """Let user pick a new repo name. Returns chosen name or None if keeping current."""
    console.print()
    console.print(Panel(
        "[bold cyan]Choose a repository name[/bold cyan]\n"
        "[dim]Select a name for the GitHub repo (and optionally rename the local folder).[/dim]",
        border_style="cyan",
        padding=(0, 2),
    ))
    console.print()

    choices = [
        Choice(value=value, name=f"[bold]{value}[/bold]  [dim]{desc}[/dim]")
        for value, desc in NAME_SUGGESTIONS
    ]

    selected = inquirer.select(
        message="Pick a name:",
        choices=choices,
        default="freelance-quote-cli",
    ).execute()

    return None if selected == "keep" else selected


def rename_directory(new_name: str) -> Path:
    """Rename the project root directory. Returns new path."""
    parent = PROJECT_ROOT.parent
    new_path = parent / new_name

    if new_path.exists():
        console.print(f"[yellow]Directory '{new_path}' already exists — skipping rename.[/yellow]")
        return PROJECT_ROOT

    PROJECT_ROOT.rename(new_path)
    console.print(f"[green]Renamed directory:[/green] {PROJECT_ROOT.name} → {new_name}")
    return new_path


def update_readme(new_name: str, project_path: Path) -> None:
    readme = project_path / "README.md"
    if not readme.exists():
        return
    content = readme.read_text(encoding="utf-8")
    # Replace the first heading if it matches the old name
    old_name = PROJECT_ROOT.name
    if old_name in content:
        content = content.replace(f"# {old_name}", f"# {new_name}", 1)
        readme.write_text(content, encoding="utf-8")


def init_and_push(repo_name: str, project_path: Path) -> None:
    if not _git_installed():
        console.print("[red]git is not installed. Please install git and re-run.[/red]")
        sys.exit(1)

    # git init
    if _already_git_repo(project_path):
        console.print("[dim]Git repo already initialised — skipping git init.[/dim]")
    else:
        _run(["git", "init"], cwd=project_path)
        console.print("[green]git init[/green] ✓")

    # git add + commit
    _run(["git", "add", "."], cwd=project_path)
    result = _run(
        ["git", "commit", "-m", "Initial commit — freelance quote calculator"],
        cwd=project_path,
        check=False,
    )
    if result.returncode == 0:
        console.print("[green]Initial commit created[/green] ✓")
    else:
        # Nothing to commit (already committed)
        console.print("[dim]Nothing new to commit.[/dim]")

    # Push to GitHub
    if not _gh_installed():
        console.print()
        console.print(Panel(
            "[yellow]gh CLI not found.[/yellow] To push to GitHub, run:\n\n"
            "  [bold]brew install gh[/bold]   (macOS)\n"
            "  [bold]sudo apt install gh[/bold]  (Ubuntu/Debian)\n\n"
            "Then authenticate with [bold]gh auth login[/bold] and re-run this script.",
            border_style="yellow",
            padding=(0, 2),
        ))
        return

    # Check if remote already exists
    remote_check = _run(["git", "remote"], cwd=project_path, check=False)
    if "origin" in remote_check.stdout:
        console.print("[dim]Remote 'origin' already set — skipping gh repo create.[/dim]")
        push_result = _run(["git", "push", "-u", "origin", "HEAD"], cwd=project_path, check=False)
        if push_result.returncode == 0:
            console.print("[green]Pushed to existing remote[/green] ✓")
        else:
            console.print(f"[red]Push failed:[/red] {push_result.stderr.strip()}")
        return

    visibility = inquirer.select(
        message="Repository visibility:",
        choices=[
            Choice(value="--public", name="Public"),
            Choice(value="--private", name="Private"),
        ],
        default="--private",
    ).execute()

    gh_result = _run(
        ["gh", "repo", "create", repo_name, visibility, "--source=.", "--remote=origin", "--push"],
        cwd=project_path,
        check=False,
    )

    if gh_result.returncode == 0:
        # Extract repo URL from output
        url_match = re.search(r"https://github\.com/\S+", gh_result.stdout + gh_result.stderr)
        url = url_match.group(0) if url_match else f"https://github.com/<you>/{repo_name}"
        console.print()
        console.print(Panel(
            f"[bold green]GitHub repo created and pushed![/bold green]\n[white]{url}[/white]",
            border_style="green",
            padding=(0, 2),
        ))
    else:
        console.print(f"[red]gh repo create failed:[/red]\n{gh_result.stderr.strip()}")
        console.print("[dim]You can push manually:\n  gh repo create " + repo_name + " --public --source=. --remote=origin --push[/dim]")


def main() -> None:
    console.print()
    console.print(Panel(
        "[bold cyan]Git Setup — freelance-quote-cli[/bold cyan]\n"
        "[dim]Initialise git, optionally rename the project, and push to GitHub.[/dim]",
        border_style="cyan",
        padding=(1, 4),
    ))

    new_name = choose_name()
    project_path = PROJECT_ROOT

    if new_name:
        confirm = inquirer.confirm(
            message=f"Rename local folder '{PROJECT_ROOT.name}' → '{new_name}'?",
            default=True,
        ).execute()
        if confirm:
            project_path = rename_directory(new_name)
            update_readme(new_name, project_path)
        repo_name = new_name
    else:
        repo_name = PROJECT_ROOT.name

    init_and_push(repo_name, project_path)

    console.print()
    if project_path != PROJECT_ROOT:
        console.print(
            f"[yellow]Note:[/yellow] The project folder was renamed.\n"
            f"cd into the new directory:  [bold]cd {project_path}[/bold]"
        )


if __name__ == "__main__":
    main()
