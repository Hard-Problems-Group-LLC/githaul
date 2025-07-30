#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# git-haul.py -- Defensive, Paranoid GitHub repo synchronizer
#
# Author: (your name here)
# Python 3.9+
#
# Summary:
#   Supports syncing either a user’s or an organization’s repos via SSH.
#   Accepts one of:
#       <github-user>@<github-host-ssh-alias>
#       <github-org>:<github-user>@<github-host-ssh-alias>
#       --org <github-org> <github-user>@<github-host-ssh-alias>
#   If both org: and --org are used, they must match.
#   Verifies SSH access as the specified user, checks local repo status,
#   enumerates repos for the user or org, groups and displays by status.
#   Prompts once per group for update/clone/fetch, then proceeds.
#   Prints a post-action summary table.
#   Defensive, explicit error handling, no commits/merges/resets.
#
# Dependencies:
#   pip install requests rich
#
# Usage:
#   ./git-haul.py [--org <github-org>] [<github-org>:]<github-user>@<github-host-ssh-alias> <local-root-path>
#
# Status key:
#   NOT PRESENT   - No local clone
#   OUT OF DATE   - Behind remote (<30d)
#   OBSOLETE      - Behind remote (≥30d)
#   SYNCHRONIZED  - Up to date
#   MODIFIED      - Local unpushed/dirty
#   CONFLICT      - Merge conflict
#   DESYNCHRONIZED- Both dirty & behind

import argparse
import subprocess
import sys
import os
import pathlib
import requests
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()

def fatal(msg: str):
    """Print error and exit."""
    console.print(f"[bold red]FATAL:[/bold red] {msg}")
    sys.exit(1)

def run_command(cmd: List[str], cwd: Optional[str] = None, timeout: int = 40) -> Tuple[int, str, str]:
    """Run a command, return (exit_code, stdout, stderr)."""
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except Exception as e:
        return 99, "", str(e)

def parse_org_user_alias(arg: str) -> Tuple[Optional[str], str, str]:
    """
    Parse '[<github-org>:]<github-user>@<github-host-alias>'
    Returns (org or None, user, alias)
    """
    org = None
    if ':' in arg and '@' in arg and arg.index(':') < arg.index('@'):
        org_user, alias = arg.rsplit('@', 1)
        org, user = org_user.split(':', 1)
    elif '@' in arg:
        user, alias = arg.split('@', 1)
    else:
        fatal("Target must be in the form <user>@<alias> or <org>:<user>@<alias>")
    if not user or not alias:
        fatal("Parsing failed: user or alias missing")
    return org, user, alias

def verify_ssh_access(user: str, alias: str) -> None:
    """SSH authentication check as git@<alias> for user <user>."""
    cmd = ["ssh", "-T", f"git@{alias}"]
    code, out, err = run_command(cmd, timeout=12)
    expected = f"Hi {user}! You've successfully authenticated, but GitHub does not provide shell access."
    found = None
    if expected in out:
        found = "STDOUT"
    elif expected in err:
        found = "STDERR"
    if not found:
        details = f"SSH returned code {code}\nSTDOUT:\n{out}\nSTDERR:\n{err}"
        fatal(f"SSH authentication failed or wrong user/alias:\n{details}")
    console.print(
        f"[green]SSH authentication to {alias} verified for user {user} (message in {found})[/green]"
    )

def check_local_path(path: str) -> pathlib.Path:
    """Ensure local path exists and is writable."""
    p = pathlib.Path(path).expanduser().resolve()
    if not p.exists():
        fatal(f"Local path '{p}' does not exist")
    if not os.access(str(p), os.W_OK):
        fatal(f"Local path '{p}' is not writable")
    return p

def github_api_request(url: str, params=None, token=None):
    """Perform a GitHub API GET, die on failure."""
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=20)
    except Exception as e:
        fatal(f"GitHub API request failed (network): {e}")
    if resp.status_code != 200:
        fatal(f"GitHub API request failed: {resp.status_code} {resp.reason}\nURL: {url}\n{resp.text}")
    return resp.json()

def get_github_repos(user: str, org: Optional[str]) -> List[Dict]:
    """Return list of repo metadata for a GitHub user or organization."""
    repos = []
    page = 1
    if org:
        # List org repos
        while True:
            url = f"https://api.github.com/orgs/{org}/repos"
            params = {'per_page': 100, 'page': page, 'type': 'all', 'sort': 'full_name'}
            chunk = github_api_request(url, params=params)
            if not chunk:
                break
            repos.extend(chunk)
            if len(chunk) < 100:
                break
            page += 1
    else:
        # List user repos (owned only)
        while True:
            url = f"https://api.github.com/users/{user}/repos"
            params = {'per_page': 100, 'page': page, 'type': 'owner', 'sort': 'full_name'}
            chunk = github_api_request(url, params=params)
            if not chunk:
                break
            repos.extend(chunk)
            if len(chunk) < 100:
                break
            page += 1
    return repos

def repo_has_submodules(repo_path: pathlib.Path) -> bool:
    """Check if repo has a .gitmodules file."""
    return (repo_path / ".gitmodules").is_file()

def local_repo_status(repo_path: pathlib.Path, remote_url: str) -> Tuple[str, str, bool]:
    """
    Analyze repo status.
    Returns: (status_string, current_branch, has_submodules)
    """
    git_dir = repo_path / '.git'
    if not git_dir.is_dir():
        return ("NOT PRESENT", "-", False)
    code, out, _ = run_command(["git", "status", "--porcelain"], cwd=str(repo_path))
    if code != 0:
        return ("CONFLICT", "-", repo_has_submodules(repo_path))
    dirty = bool(out.strip())
    code, branch, _ = run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(repo_path))
    if code != 0:
        return ("CONFLICT", "-", repo_has_submodules(repo_path))
    code, _, _ = run_command(["git", "remote", "update"], cwd=str(repo_path))
    if code != 0:
        return ("CONFLICT", branch, repo_has_submodules(repo_path))
    code, ahead_behind, _ = run_command(
        ["git", "rev-list", "--left-right", "--count", "HEAD...@{u}"],
        cwd=str(repo_path))
    if code != 0:
        return ("MODIFIED" if dirty else "SYNCHRONIZED", branch, repo_has_submodules(repo_path))
    try:
        behind, ahead = map(int, ahead_behind.strip().split())
    except Exception:
        behind = ahead = 0
    code, out, _ = run_command(["git", "ls-files", "--unmerged"], cwd=str(repo_path))
    if code == 0 and out.strip():
        return ("CONFLICT", branch, repo_has_submodules(repo_path))
    if dirty and (behind > 0 or ahead > 0):
        return ("DESYNCHRONIZED", branch, repo_has_submodules(repo_path))
    if dirty:
        return ("MODIFIED", branch, repo_has_submodules(repo_path))
    if behind > 0:
        code, date_str, _ = run_command(
            ["git", "log", "--pretty=format:%cI", "HEAD..@{u}", "-1"], cwd=str(repo_path))
        if code == 0 and date_str:
            try:
                commit_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                days_behind = (datetime.utcnow() - commit_date.replace(tzinfo=None)).days
            except Exception:
                days_behind = 0
        else:
            days_behind = 0
        if days_behind >= 30:
            return ("OBSOLETE", branch, repo_has_submodules(repo_path))
        else:
            return ("OUT OF DATE", branch, repo_has_submodules(repo_path))
    if ahead > 0:
        return ("MODIFIED", branch, repo_has_submodules(repo_path))
    return ("SYNCHRONIZED", branch, repo_has_submodules(repo_path))

def check_repos(user: str, alias: str, org: Optional[str], repos: List[Dict], root_path: pathlib.Path) -> List[Dict]:
    """Check status of all repos, return dicts for display/action."""
    checked = []
    for repo in repos:
        repo_name = repo['name']
        owner = org if org else user
        remote_url = f"git@{alias}:{owner}/{repo_name}.git"
        repo_path = root_path / repo_name
        status, branch, has_submodules = local_repo_status(repo_path, remote_url)
        checked.append({
            'name': repo_name,
            'status': status,
            'branch': branch,
            'path': repo_path,
            'remote_url': remote_url,
            'has_submodules': has_submodules
        })
    return checked

def color_for_status(status: str) -> str:
    """Map status to rich color name."""
    return {
        "NOT PRESENT": "grey50",
        "OUT OF DATE": "yellow",
        "OBSOLETE": "magenta",
        "SYNCHRONIZED": "green",
        "MODIFIED": "yellow",
        "CONFLICT": "red",
        "DESYNCHRONIZED": "red"
    }.get(status, "white")

def display_repos_table(checked: List[Dict], title="GitHub Repository Status"):
    """Print formatted, colorized table."""
    table = Table(title=title, box=box.SIMPLE_HEAVY)
    table.add_column("Repository", style="bold")
    table.add_column("Branch", style="")
    table.add_column("Status", style="bold")
    table.add_column("Submodules", style="")
    for item in sorted(checked, key=lambda x: x['name'].lower()):
        color = color_for_status(item['status'])
        if item['has_submodules']:
            submodules = "[green]Yes[/green]"
        else:
            submodules = "[grey50](none)[/grey50]"
        table.add_row(item['name'], item['branch'], f"[{color}]{item['status']}[/{color}]", submodules)
    console.print(table)

def get_grouped_repos(checked: List[Dict]) -> Dict[str, List[Dict]]:
    """Group repos by status."""
    grouped = {}
    for item in checked:
        grouped.setdefault(item['status'], []).append(item)
    return grouped

def ask_yes_no(prompt: str, default_yes=True) -> bool:
    """Prompt for yes/no, default as indicated."""
    prompt_str = f"{prompt} [{'Y/n' if default_yes else 'y/N'}] "
    ans = input(prompt_str).strip().lower()
    if ans == "" and default_yes:
        return True
    if ans == "" and not default_yes:
        return False
    return ans in ("y", "yes")

def ensure_submodules(repo_path: pathlib.Path):
    """Initialize and update submodules recursively if present."""
    if not repo_has_submodules(repo_path):
        return
    code, _, err = run_command(["git", "submodule", "init"], cwd=str(repo_path))
    if code != 0:
        console.print(f"[yellow]Warning: git submodule init failed in {repo_path.name}: {err}[/yellow]")
        return
    code, _, err = run_command(["git", "submodule", "update", "--recursive"], cwd=str(repo_path))
    if code != 0:
        console.print(f"[yellow]Warning: git submodule update failed in {repo_path.name}: {err}[/yellow]")
    else:
        console.print(f"[green]Submodules updated in {repo_path.name}[/green]")

def do_updates_and_clones(checked: List[Dict]):
    """Prompt for and perform updates (fetch/pull) and clones as required."""
    grouped = get_grouped_repos(checked)
    out_of_date_statuses = ("OUT OF DATE", "OBSOLETE")
    not_present_status = "NOT PRESENT"
    always_fetch_statuses = ("MODIFIED", "CONFLICT", "DESYNCHRONIZED")

    need_update = [r for status in out_of_date_statuses for r in grouped.get(status, [])]
    if need_update:
        console.print("\n[bold yellow]The following repositories are out of date or obsolete:[/bold yellow]")
        for r in need_update:
            color = color_for_status(r['status'])
            console.print(f"  [{color}]{r['name']}[/{color}] ({r['status']})")
        update_all = ask_yes_no("Update (fetch & pull) ALL out-of-date repositories?", default_yes=True)
    else:
        update_all = False

    need_clone = grouped.get(not_present_status, [])
    if need_clone:
        console.print("\n[bold]The following repositories are not present locally:[/bold]")
        for r in need_clone:
            color = color_for_status(r['status'])
            console.print(f"  [{color}]{r['name']}[/{color}]")
        clone_all = ask_yes_no("Clone ALL missing repositories?", default_yes=True)
    else:
        clone_all = False

    need_fetch = [r for status in always_fetch_statuses for r in grouped.get(status, [])]
    if need_fetch:
        console.print("\n[bold red]The following repositories have local changes/conflicts:[/bold red]")
        for r in need_fetch:
            color = color_for_status(r['status'])
            console.print(f"  [{color}]{r['name']}[/{color}] ({r['status']})")
        fetch_all = ask_yes_no("Fetch latest info for ALL modified/conflicted repositories? (never pulls, never overwrites)", default_yes=True)
    else:
        fetch_all = False

    for r in need_update:
        if update_all:
            console.print(f"\n[cyan]Updating repository {r['name']}...[/cyan]")
            code, _, err = run_command(["git", "fetch"], cwd=str(r['path']))
            if code != 0:
                console.print(f"[red]git fetch failed for {r['name']}[/red]: {err}")
                continue
            code, out, _ = run_command(["git", "status", "--porcelain"], cwd=str(r['path']))
            dirty = bool(out.strip())
            code, out, _ = run_command(["git", "ls-files", "--unmerged"], cwd=str(r['path']))
            conflict = bool(out.strip())
            if not dirty and not conflict:
                code, _, err = run_command(["git", "pull"], cwd=str(r['path']))
                if code != 0:
                    console.print(f"[red]git pull failed for {r['name']}[/red]: {err}")
                else:
                    console.print(f"[green]Pulled latest changes for {r['name']}[/green]")
                ensure_submodules(r['path'])
            else:
                if dirty:
                    console.print(f"[yellow]Skipped pull in {r['name']} due to local changes[/yellow]")
                if conflict:
                    console.print(f"[red]Skipped pull in {r['name']} due to merge conflicts[/red]")
                ensure_submodules(r['path'])

    for r in need_clone:
        if clone_all:
            dest = r['path']
            console.print(f"\n[cyan]Cloning repository {r['name']}...[/cyan]")
            code, _, err = run_command(["git", "clone", r['remote_url'], str(dest.parent / dest.name)])
            if code != 0:
                console.print(f"[red]git clone failed for {r['name']}[/red]: {err}")
                continue
            ensure_submodules(dest)
            console.print(f"[green]Cloned {r['name']}[/green]")

    for r in need_fetch:
        if fetch_all:
            console.print(f"\n[yellow]Fetching latest info for {r['name']} ({r['status']})...[/yellow]")
            code, _, err = run_command(["git", "fetch"], cwd=str(r['path']))
            if code != 0:
                console.print(f"[red]git fetch failed for {r['name']}[/red]: {err}")
            else:
                ensure_submodules(r['path'])
                console.print(f"[green]Fetched for {r['name']}[/green]")

def main():
    """Main entry point, with full org/user parsing and CLI error logic."""
    example_usage = (
        "Examples:\n"
        "  git-haul.py jdobbs@github-yoyodyne ~/src/yoyodyne\n"
        "  git-haul.py Hard-Problems-Group-LLC:hpg-mheck@github-hpg ~/src/hpg\n"
        "  git-haul.py --org Hard-Problems-Group-LLC hpg-mheck@github-hpg ~/src/hpg\n\n"
        "You may specify an organization either as a prefix (org:user@alias),\n"
        "or with --org, but NOT both with different orgs. If both, they must match."
    )
    parser = argparse.ArgumentParser(
        description="git-haul: Defensive multi-repo synchronizer for GitHub via SSH\n\n" + example_usage,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="See README.TXT for full documentation."
    )
    parser.add_argument("--org", help="GitHub organization to enumerate repos for")
    parser.add_argument("target", nargs="?", help="[<org>:]<github-user>@<github-host-ssh-alias>")
    parser.add_argument("local_root", nargs="?", help="Path to local root directory for repositories")
    args = parser.parse_args()

    if not args.target or not args.local_root:
        parser.print_help()
        console.print(
            "[bold yellow]Insufficient arguments: you must provide a target ([<org>:]user@alias) and a local path.[/bold yellow]"
        )
        sys.exit(2)

    org1, user, alias = parse_org_user_alias(args.target)
    org2 = args.org

    # Validate org logic
    if org1 and org2 and org1 != org2:
        fatal(f"Organization mismatch: '{org1}' (from target) != '{org2}' (from --org). Use only one, or ensure they match.")
    org = org2 or org1

    root_path = check_local_path(args.local_root)
    verify_ssh_access(user, alias)

    if org:
        console.print(f"[bold cyan]Listing repositories for organization [white]{org}[/white], authenticating as user [white]{user}[/white] via SSH alias [white]{alias}[/white][/bold cyan]")
    else:
        console.print(f"[bold cyan]Listing repositories for user [white]{user}[/white], authenticating via SSH alias [white]{alias}[/white][/bold cyan]")

    repos = get_github_repos(user, org)
    if not repos:
        fatal("No repositories found for this user or organization.")
    checked = check_repos(user, alias, org, repos, root_path)

    # Upfront grouped status display
    console.print("\n[bold underline]Initial Repository Status Summary[/bold underline]")
    display_repos_table(checked)

    # All grouped prompts and actions
    do_updates_and_clones(checked)

    # Post-action status table
    console.print("\n[bold green]Post-Action Repository Status Summary[/bold green]")
    checked_post = check_repos(user, alias, org, repos, root_path)
    display_repos_table(checked_post)

    console.print("\n[bold green]All done.[/bold green]")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[bold red]Interrupted by user[/bold red]")
        sys.exit(130)
    except Exception as e:
        fatal(f"Unhandled exception:\n{e}")

