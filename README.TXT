git-haul: Defensive GitHub Repo Synchronizer
===========================================
Hard Problems Group, LLC
Matt Heck
R. Talon
30JUL2025


Overview
--------
git-haul is a Python utility for auditing and synchronizing all repositories for a specified GitHub account or GitHub organization, using SSH authentication and a local path root.

You can use your user credentials to authenticate and operate on all repos you can access, including organization repos for which you are a member.

Features
--------
- Verifies SSH connectivity to GitHub using the provided SSH alias and user.
- Enumerates all GitHub repositories for a given user or organization (public, or private if you have access).
- Accepts any of these command line forms:
    - <github-user>@<github-host-ssh-alias>
    - <github-org>:<github-user>@<github-host-ssh-alias>
    - --org <github-org> <github-user>@<github-host-ssh-alias>
  If both org: and --org are present, they must match or the program will FATAL and quit.
- Checks for the presence and status of each repo under your chosen local path.
- Shows a color-coded, grouped, ASCII table (using 'rich') for all repositories:
    - NOT PRESENT    (gray)     - Repo missing locally
    - OUT OF DATE    (yellow)   - Behind remote, <30 days
    - OBSOLETE       (magenta)  - Behind remote, ≥30 days
    - SYNCHRONIZED   (green)    - Up-to-date
    - MODIFIED       (yellow)   - Local changes (uncommitted or unpushed)
    - CONFLICT       (red)      - Merge conflict
    - DESYNCHRONIZED (red)      - Dirty & behind remote
    - Submodules: "Yes" (green) or "(none)" (gray) for each repo.
- Groups repositories by status for prompts and action.
- Prompts once per group:
    - Update all out-of-date/obsolete repositories? (fetch, then pull if clean)
    - Clone all missing repositories?
    - Fetch all with local changes/conflicts? (never pulls, never overwrites)
- All submodules are initialized/updated if present (after clone, pull, or fetch).
- Post-action summary shows updated state.
- No commits, resets, merges, or destructive operations—**all local changes are preserved**.
- Paranoid, explicit error handling—any error is reported immediately, never masked or skipped.

Requirements
------------
- Python 3.9 or higher
- Dependencies: `requests`, `rich`
    Install with: `pip install requests rich`

Usage
-----
    ./git-haul.py [--org <github-org>] [<github-org>:]<github-user>@<github-host-ssh-alias> <local-root-path>

Examples:
    ./git-haul.py jdobbs@github-yoyodyne ~/src/yoyodyne
    ./git-haul.py Hard-Problems-Group-LLC:hpg-mheck@github-hpg ~/src/hpg
    ./git-haul.py --org Hard-Problems-Group-LLC hpg-mheck@github-hpg ~/src/hpg

  - 'jdobbs' or 'hpg-mheck' is your GitHub username.
  - 'github-yoyodyne' or 'github-hpg' is an SSH host alias you define in your ~/.ssh/config file:

        Host github-hpg
            HostName github.com
            User git
            IdentityFile ~/.ssh/id_rsa_hpg

  - If you only use a single GitHub account and SSH key, you can use 'github.com' as the alias.
  - The local-root-path is the directory where all repositories will be checked for and managed. Each repo is expected as a subdirectory directly beneath this path, named after the repo.

Prompts & Actions
-----------------
- **All questions are asked up front, grouped by repo status:**
    - "Update (fetch & pull) ALL out-of-date repositories?" (default Yes)
    - "Clone ALL missing repositories?" (default Yes)
    - "Fetch latest info for ALL modified/conflicted repositories? (never pulls, never overwrites)" (default Yes)
- If you decline, that action is skipped for all repos in the group.
- Submodules are always initialized/updated after clone/fetch/pull if present.

Safety & Limitations
--------------------
- Only repositories you can access are shown (public or private as allowed by your credentials).
- No repo is ever reset, merged, or committed to by this script.
- All local changes, stashes, and untracked files are **left untouched**.
- Post-action summary shows updated repo status in a new colorized table.

Error Handling
--------------
- Fatal errors are explicitly reported and the program quits immediately.
- If both a colon org: and --org flag are given, they must match.

Author
------
(Your Name)
2025

License
-------
MIT, no warranty.

