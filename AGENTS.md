# AGENTS.md

## git-haul: Agent Engineering Principles and Successor Standards

---

### Mission

`git-haul` exists to provide a **paranoid, robust, explicit, and safe** method for auditing and synchronizing all repositories for a GitHub user or organization via SSH, using local path control, colorized status reporting, and *never* risking local data.  
**It must always:**
- Tell the user *exactly* what it will do
- Ask for permission before any state-changing action
- Fail loudly and explicitly on all errors
- Preserve all local data and changes, always

---

### Design Principles

1. **Defensive Programming**
   - All inputs, subprocesses, and API requests must be checked for failure or unexpected response.  
   - Never assume success—**verify and report**.

2. **Explicit Error Handling**
   - Any ambiguity, mismatch, or potential for data loss is a *fatal error*.
   - Explanatory fatal errors are always shown to the user; never mask failures.

3. **Safe Defaults, No Destructive Actions**
   - No merges, commits, resets, or destructive operations on any repo.
   - All local changes are preserved and must not be lost or hidden.

4. **Single-Pass, Grouped User Prompts**
   - Always prompt *once per status group* (out-of-date, not present, modified/conflicted).
   - Never make assumptions about user intent.
   - No hidden actions.

5. **Organization/User Authentication Flexibility**
   - Must accept all of:
     - `<user>@<alias>`
     - `<org>:<user>@<alias>`
     - `--org <org> <user>@<alias>`
   - If both `org:` and `--org` are given, they *must* match or the program must fatal.

6. **Maximal Transparency**
   - All status tables must be colorized, explicit, and include all key fields (including `(none)` in submodules).
   - Pre- and post-action summaries must be shown.

7. **Minimum Dependencies**
   - No bloated libraries. Use only `requests` and `rich` outside the standard library.

---

### Implementation/Review Checklist

- [ ] **Authentication**: Verifies SSH access for the intended user, and the correct identity and alias are used.
- [ ] **Argument Parsing**: Accepts all forms and enforces org/user matching per above.
- [ ] **Status Detection**: For each repo, checks:
  - Local presence
  - Branch and remote sync status
  - Local changes, conflicts, and submodules
- [ ] **Prompting**: Groups repos and prompts once per group, never per-repo, and requires explicit consent.
- [ ] **Action Safety**: Only runs `git fetch`, `git pull` (if safe), `git clone`, and `git submodule update`. No commits, resets, or merges.
- [ ] **Submodules**: Always reports whether present, and updates/initializes when cloning or updating.
- [ ] **Error Handling**: All subprocess and API errors are caught and clearly reported to the user.
- [ ] **Output**: All tables and messages use color and explicit (never blank) field entries.
- [ ] **Documentation**: Code, README, and AGENTS.md are kept up to date with all behavior.

---

### Philosophy

"Assume everything will break. Assume every user will be confused.  
Assume that what can't go wrong, will—and that no one will read the docs unless it's because the tool bailed out with a loud, explicit error."

> **The only correct attitude is ruthless pragmatism and zero trust.**

---

### Code Quality

- Write comments for every non-trivial function or branch.
- Function names must be self-documenting.
- Any refactor must *not* weaken error reporting, safety, or user explicitness.
- Any change that could cause a destructive or irreversible action is **forbidden**.

---

### Extensibility

- For new features (such as GitHub API tokens, private repo support, filtering, multi-root, etc.):
  - Maintain defensive defaults and explicit prompts.
  - Never assume the user wants something unless they typed it.

---

### Quick Test Commands

- Authentication and org logic must be validated:
  - User: `git-haul.py matt@github-personal ~/src/personal`
  - Org:  `git-haul.py --org TheCompany matt@github-work ~/src/company`
  - Mixed: `git-haul.py TheCompany:matt@github-work ~/src/company`
  - Mismatch: `git-haul.py --org Alpha Beta:matt@github-work ~/src/company` (should FATAL)
- Repo table must always show all fields, no blanks.

---

### Success Criteria

- Zero incidents of lost local changes.
- Zero silent failures.
- Every user knows exactly what was done and why.
- All error conditions are discoverable and self-explanatory.

---

### Final Word

**If you aren’t sure if it’s explicit enough, paranoid enough, or clear enough,  
assume it isn’t, and make it so.**

---

*R. Talon — 2025-07-30*

