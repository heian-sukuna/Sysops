"""
modules/git.py — Git version control simulator
Covers: init, clone, status, add, commit, push, pull, log, branch,
        checkout, merge, rebase, diff, stash, remote, tag, reset,
        cherry-pick, bisect, worktree, submodule, reflog
"""

import time, random, hashlib
from core.ui import *

# ── Fake data helpers ──────────────────────────────────────────────────────────

def _fake_hash(seed=""):
    base = seed + str(time.time()) + str(random.random())
    return hashlib.sha1(base.encode()).hexdigest()

def _short(h): return h[:7]

COMMIT_MESSAGES = [
    "fix: resolve null pointer in auth middleware",
    "feat: add JWT refresh token endpoint",
    "chore: update dependencies to latest",
    "docs: add API documentation for /users",
    "style: format code with prettier",
    "refactor: extract database connection pool",
    "test: add unit tests for login handler",
    "fix: correct nginx proxy_pass configuration",
    "feat: implement rate limiting on API endpoints",
    "chore: add .env.example to repository",
    "fix: resolve CORS headers on preflight request",
    "feat: add Docker health check to backend service",
    "refactor: move config to environment variables",
    "docs: update README with deployment instructions",
    "feat: dark theme — dark red gradient header",
    "fix: mobile responsive layout on portfolio page",
    "chore: add GitHub Actions CI pipeline",
    "feat: add Tailscale mesh network documentation",
    "fix: nginx config — add security headers",
    "feat: implement portfolio project cards",
]

FAKE_FILES = [
    "src/index.js", "src/auth.js", "src/routes/api.js",
    "src/middleware/jwt.js", "docker-compose.yml",
    "nginx/nginx.conf", "README.md", ".env.example",
    "src/db/connection.js", "src/models/user.js",
    "public/index.html", "public/style.css",
    "Dockerfile", ".gitignore", "package.json",
]

class GitModule:
    def __init__(self, world, save):
        self.w = world
        self.s = save

    # ─── Entry point ──────────────────────────────────────────────────────────

    def git(self, args):
        if not args:
            self._help(); return

        sub  = args[0].lower()
        rest = args[1:]

        dispatch = {
            "init":        self._init,
            "clone":       self._clone,
            "status":      self._status,
            "add":         self._add,
            "commit":      self._commit,
            "push":        self._push,
            "pull":        self._pull,
            "fetch":       self._fetch,
            "log":         self._log,
            "branch":      self._branch,
            "checkout":    self._checkout,
            "switch":      self._switch,
            "merge":       self._merge,
            "rebase":      self._rebase,
            "diff":        self._diff,
            "stash":       self._stash,
            "remote":      self._remote,
            "tag":         self._tag,
            "reset":       self._reset,
            "revert":      self._revert,
            "cherry-pick": self._cherry_pick,
            "reflog":      self._reflog,
            "bisect":      self._bisect,
            "submodule":   self._submodule,
            "worktree":    self._worktree,
            "show":        self._show,
            "shortlog":    self._shortlog,
            "blame":       self._blame,
            "clean":       self._clean,
            "config":      self._config,
            "help":        lambda a: self._help(),
        }

        fn = dispatch.get(sub)
        if fn:
            fn(rest)
        else:
            print(err(f"  git: '{sub}' is not a git command. See 'git help'."))

    # ─── Repo helpers ─────────────────────────────────────────────────────────

    def _active_repo(self):
        """Return the currently active repo dict or None."""
        repos = self.w.git_repos
        if not repos:
            print(err("  fatal: not a git repository (or any parent up to mount point /)"))
            print(dim("  Tip: git init  or  cd into an existing repo"))
            return None
        # return the most recently touched
        name = list(repos.keys())[-1]
        return repos[name], name

    def _get_repo(self, name=None):
        if name and name in self.w.git_repos:
            return self.w.git_repos[name], name
        return self._active_repo()

    def _xp(self, pts, reason):
        lvl = self.s.add_xp(pts, reason)
        xp_flash(pts, reason)
        if lvl > 0:
            from core.save import LEVEL_TITLES, level_for_xp
            lv = level_for_xp(self.s.get("xp", 0))
            print(f"\n  {BYELLOW}{B}★ LEVEL UP → Level {lv}{R}\n")

    # ─── git init ─────────────────────────────────────────────────────────────

    def _init(self, args):
        path = args[0] if args else "."
        name = path.rstrip("/").split("/")[-1]
        if name == ".":
            name = "current-project"

        bare = "--bare" in args
        branch = "main"
        for i, a in enumerate(args):
            if a in ("-b", "--initial-branch") and i+1 < len(args):
                branch = args[i+1]

        if name in self.w.git_repos:
            print(warn(f"  Reinitialized existing Git repository in {path}/.git/"))
            return

        self.w.git_repos[name] = {
            "path":      path,
            "branch":    branch,
            "branches":  [branch],
            "staged":    [],
            "unstaged":  list(random.sample(FAKE_FILES, 4)),
            "commits":   [],
            "remotes":   {},
            "stashes":   [],
            "tags":      [],
            "bare":      bare,
            "dirty":     True,
        }

        print(ok(f"  Initialized empty Git repository in {path}/.git/"))
        if bare:
            print(dim("  (bare repository — no working tree)"))
        print(dim(f"  Default branch: {branch}"))
        print(dim("  Hint: use 'git add .' then 'git commit -m \"msg\"' to make your first commit"))
        self._xp(8, "git init")

    # ─── git clone ────────────────────────────────────────────────────────────

    def _clone(self, args):
        if not args:
            print(warn("  Usage: git clone <url> [directory]")); return

        url  = args[0]
        dest = args[1] if len(args) > 1 else url.rstrip("/").split("/")[-1].replace(".git","")
        depth = None
        for i, a in enumerate(args):
            if a == "--depth" and i+1 < len(args):
                depth = args[i+1]
            elif a.startswith("--depth="):
                depth = a.split("=")[1]

        spinner(f"Cloning into '{dest}'", 1.2)

        n_objects = random.randint(120, 800)
        kb        = random.randint(200, 4000)

        print(f"  remote: Enumerating objects: {n_objects}, done.")
        print(f"  remote: Counting objects: 100% ({n_objects}/{n_objects}), done.")
        print(f"  remote: Compressing objects: 100% ({n_objects//2}/{n_objects//2}), done.")
        if depth:
            print(dim(f"  (shallow clone, depth={depth})"))
        print(f"  Receiving objects: 100% ({n_objects}/{n_objects}), {kb} KiB | "
              f"{random.randint(2,8)} MiB/s, done.")
        print(f"  Resolving deltas: 100% ({n_objects//4}/{n_objects//4}), done.")
        print(ok(f"\n  ✓ Cloned into '{dest}'"))

        init_hash = _fake_hash(url)
        self.w.git_repos[dest] = {
            "path":    dest,
            "branch":  "main",
            "branches":["main", "dev", "feature/auth"],
            "staged":  [],
            "unstaged":[],
            "commits": [
                {"hash": init_hash, "short": _short(init_hash),
                 "msg": "initial commit", "author": "origin",
                 "date": "2026-01-01 10:00:00"},
            ],
            "remotes": {"origin": url},
            "stashes": [],
            "tags":    ["v0.1.0"],
            "bare":    False,
            "dirty":   False,
        }
        self._xp(10, "git clone")

    # ─── git status ───────────────────────────────────────────────────────────

    def _status(self, args):
        result = self._active_repo()
        if not result: return
        repo, name = result

        branch = repo["branch"]
        staged   = repo.get("staged", [])
        unstaged = repo.get("unstaged", [])
        commits  = repo.get("commits", [])

        print(f"\n  On branch {cyan(branch)}")

        # Remote tracking
        remote = repo.get("remotes", {}).get("origin")
        if remote and commits:
            ahead = random.randint(0, 3)
            if ahead:
                print(f"  Your branch is {ok('ahead')} of 'origin/{branch}' by {ahead} commit(s).")
                print(dim("  (use \"git push\" to publish your local commits)"))
            else:
                print(f"  Your branch is {ok('up to date')} with 'origin/{branch}'.")
        elif not commits:
            print(dim("  No commits yet"))

        print()

        if staged:
            print(ok("  Changes to be committed:"))
            print(dim('  (use "git restore --staged <file>..." to unstage)'))
            for f in staged:
                action = "new file" if f not in [c for c in repo.get("commits",[]) ] else "modified"
                print(f"        {BGREEN}{'new file:' if action=='new file' else 'modified:':<14}{R} {f}")
            print()

        if unstaged:
            print(warn("  Changes not staged for commit:"))
            print(dim('  (use "git add <file>..." to update what will be committed)'))
            for f in unstaged:
                print(f"        {BYELLOW}{'modified:':<14}{R} {f}")
            print()

        if not staged and not unstaged:
            print(ok("  nothing to commit, working tree clean"))

        self.s.add_xp(2, "git status")

    # ─── git add ──────────────────────────────────────────────────────────────

    def _add(self, args):
        result = self._active_repo()
        if not result: return
        repo, name = result

        if not args:
            print(warn("  Usage: git add <file|.|-A>")); return

        target = args[0]
        unstaged = repo.get("unstaged", [])

        if target in (".", "-A", "--all", "*"):
            added = list(unstaged)
            repo["staged"]   = list(set(repo.get("staged", []) + added))
            repo["unstaged"] = []
            if added:
                for f in added:
                    print(dim(f"  add '{f}'") if "-v" in args else "")
                if "-v" not in args:
                    print(dim(f"  (staged {len(added)} file(s))"))
            else:
                print(dim("  nothing to add (working tree clean)"))
        elif target in unstaged:
            repo["staged"].append(target)
            repo["unstaged"].remove(target)
            print(dim(f"  staged: {target}"))
        else:
            # Add a fake new file
            repo["staged"].append(target)
            print(dim(f"  staged: {target}"))

        self._xp(4, "git add")

    # ─── git commit ───────────────────────────────────────────────────────────

    def _commit(self, args):
        result = self._active_repo()
        if not result: return
        repo, name = result

        msg     = None
        amend   = "--amend" in args
        no_edit = "--no-edit" in args
        allow_empty = "--allow-empty" in args

        for i, a in enumerate(args):
            if a in ("-m", "--message") and i+1 < len(args):
                msg = args[i+1]
            elif a.startswith("-m"):
                msg = a[2:]

        if not repo.get("staged") and not amend and not allow_empty:
            print(warn("  On branch " + repo["branch"]))
            print(warn("  nothing to commit, working tree clean"))
            print(dim("  Tip: stage files first with git add ."))
            return

        if not msg and not no_edit:
            print(warn("  Aborting commit due to empty commit message."))
            print(dim("  Use: git commit -m \"your message\""))
            return

        h      = _fake_hash(msg or "amend")
        short  = _short(h)
        staged = list(repo.get("staged", []))
        ts     = time.strftime("%Y-%m-%d %H:%M:%S")
        user   = self.s.get("username", "user")

        if amend and repo.get("commits"):
            old = repo["commits"][-1]
            repo["commits"][-1] = {
                "hash": h, "short": short,
                "msg": msg or old["msg"],
                "author": user, "date": ts,
                "files": staged or old.get("files", []),
            }
            print(ok(f"  [{repo['branch']} {short}] (amend) {msg or old['msg']}"))
        else:
            repo["commits"].append({
                "hash": h, "short": short,
                "msg": msg, "author": user,
                "date": ts, "files": staged,
            })
            repo["staged"]  = []
            repo["dirty"]   = False
            n_files = len(staged)
            insertions = random.randint(n_files * 5, n_files * 80)
            deletions  = random.randint(0, n_files * 10)
            print(ok(f"  [{repo['branch']} {short}] {msg}"))
            print(dim(f"  {n_files} file(s) changed, {insertions} insertion(s)(+), {deletions} deletion(s)(-)"))
            for f in staged[:5]:
                print(dim(f"   create mode 100644 {f}"))

        self._xp(12, "git commit")

        # Achievement
        commits_total = sum(len(r.get("commits",[])) for r in self.w.git_repos.values())
        if commits_total >= 10:
            if self.s.grant_achievement("committer","Made 10+ git commits"):
                print(f"  {BYELLOW}{B}🏆 Achievement: Serial Committer!{R}")

    # ─── git push ─────────────────────────────────────────────────────────────

    def _push(self, args):
        result = self._active_repo()
        if not result: return
        repo, name = result

        force      = "-f" in args or "--force" in args
        force_with = "--force-with-lease" in args
        set_upstream = "-u" in args or "--set-upstream" in args
        remote     = next((a for a in args if not a.startswith("-") and a in repo.get("remotes",{})), "origin")
        branch     = repo["branch"]

        if not repo.get("remotes"):
            print(err("  fatal: 'origin' does not appear to be a git repository"))
            print(dim("  Tip: git remote add origin <url>"))
            return

        unpushed = [c for c in repo.get("commits",[]) if not c.get("pushed")]
        if not unpushed and not force:
            print(ok(f"  Everything up-to-date"))
            return

        if force and not force_with:
            print(warn("  ⚠ Force push rewrites remote history — use with caution!"))
            print(dim("  Prefer: --force-with-lease (safer, checks remote state first)"))

        spinner(f"Pushing to {remote}/{branch}", 0.8)

        n = len(unpushed)
        print(f"  Enumerating objects: {n*3}, done.")
        print(f"  Counting objects: 100% ({n*3}/{n*3}), done.")
        print(f"  Writing objects: 100% ({n}/{n}), "
              f"{random.randint(2,40)} KiB | {random.randint(1,5)} MiB/s, done.")

        for c in unpushed:
            c["pushed"] = True

        origin_url = repo["remotes"].get(remote, "")
        branch_url = f"{origin_url.rstrip('/')}/{branch}" if origin_url else remote+"/"+branch

        if set_upstream:
            print(f"\n  Branch '{branch}' set up to track remote branch '{branch}' from '{remote}'.")

        print(ok(f"\n  ✓  {remote}/{branch}  →  {origin_url}"))
        self._xp(10, "git push")

    # ─── git pull ─────────────────────────────────────────────────────────────

    def _pull(self, args):
        result = self._active_repo()
        if not result: return
        repo, name = result

        rebase_flag = "--rebase" in args
        remote  = next((a for a in args if not a.startswith("-")), "origin")
        branch  = repo["branch"]

        spinner(f"Fetching from {remote}", 0.7)

        n_new = random.randint(0, 4)
        if n_new == 0:
            print(f"  Already up to date.")
            return

        print(f"  remote: Enumerating objects: {n_new*3}, done.")

        new_commits = []
        for i in range(n_new):
            h = _fake_hash(f"remote{i}")
            msg = random.choice(COMMIT_MESSAGES)
            new_commits.append({
                "hash": h, "short": _short(h),
                "msg": msg, "author": "teammate",
                "date": time.strftime("%Y-%m-%d %H:%M:%S"),
                "pushed": True,
            })
            repo["commits"].append(new_commits[-1])

        method = "Rebasing" if rebase_flag else "Merging"
        print(f"  {method}: {branch} → {remote}/{branch}")
        for c in new_commits:
            print(f"  {dim(c['short'])}  {c['msg']}")

        base_h   = _fake_hash("merge")
        print(ok(f"\n  Fast-forward  {_short(base_h)}"))
        print(dim(f"  {n_new} new commit(s) integrated"))
        self._xp(6, "git pull")

    # ─── git fetch ────────────────────────────────────────────────────────────

    def _fetch(self, args):
        result = self._active_repo()
        if not result: return
        repo, _ = result
        remote = next((a for a in args if not a.startswith("-")), "origin")
        spinner(f"Fetching from {remote}", 0.6)
        n = random.randint(0,3)
        if n:
            print(f"  From {repo['remotes'].get(remote,'origin')}")
            print(f"    origin/main  →  FETCH_HEAD  ({n} new commit(s))")
        else:
            print(dim("  Already up to date."))
        self.s.add_xp(3, "git fetch")

    # ─── git log ──────────────────────────────────────────────────────────────

    def _log(self, args):
        result = self._active_repo()
        if not result: return
        repo, name = result

        oneline  = "--oneline" in args
        graph    = "--graph" in args
        all_flag = "--all" in args
        stat     = "--stat" in args
        n_limit  = 10
        for i, a in enumerate(args):
            if a.startswith("-n") and len(a) > 2:
                try: n_limit = int(a[2:])
                except: pass
            elif a == "-n" and i+1 < len(args):
                try: n_limit = int(args[i+1])
                except: pass

        commits = list(reversed(repo.get("commits", [])))[:n_limit]

        if not commits:
            print(warn("  fatal: your current branch has no commits yet"))
            return

        print()
        for i, c in enumerate(commits):
            h     = c.get("short", "abcdef1")
            msg   = c.get("msg", "no message")
            auth  = c.get("author", self.s.get("username","user"))
            date  = c.get("date", "2026-01-01 12:00:00")
            files = c.get("files", [])

            if oneline:
                branch_tag = f" {BYELLOW}(HEAD → {repo['branch']}){R}" if i == 0 else ""
                graph_str  = f"{BRED}*{R} " if graph else ""
                print(f"  {graph_str}{BYELLOW}{h}{R}{branch_tag} {msg}")
            else:
                print(f"  {BYELLOW}commit {c.get('hash', h+'0'*33)}{R}")
                if i == 0:
                    print(f"  {dim('(')}HEAD → {cyan(repo['branch'])}{dim(')')}")
                print(f"  Author: {auth} <{auth}@sysops.local>")
                print(f"  Date:   {date}")
                print(f"\n      {msg}\n")
                if stat and files:
                    for f in files[:3]:
                        changes = random.randint(1, 40)
                        print(f"   {dim(f)} | {changes} {'+'*min(changes,20)}")
                    print()

        if graph and len(commits) > 1:
            print(dim("  (branch graph condensed for readability)"))

        self.s.add_xp(3, "git log")

    # ─── git branch ───────────────────────────────────────────────────────────

    def _branch(self, args):
        result = self._active_repo()
        if not result: return
        repo, name = result

        delete  = "-d" in args or "-D" in args
        force_d = "-D" in args
        rename  = "-m" in args
        all_f   = "-a" in args
        verbose = "-v" in args

        names = [a for a in args if not a.startswith("-")]

        if delete and names:
            b = names[0]
            if b == repo["branch"]:
                print(err(f"  error: Cannot delete the branch '{b}' checked out"))
                return
            if b in repo["branches"]:
                repo["branches"].remove(b)
                print(ok(f"  Deleted branch {b} (was {_short(_fake_hash(b))})."))
            else:
                print(err(f"  error: branch '{b}' not found."))

        elif rename and len(names) >= 2:
            old, new = names[0], names[1]
            if old in repo["branches"]:
                repo["branches"].remove(old)
                repo["branches"].append(new)
                if repo["branch"] == old:
                    repo["branch"] = new
                print(ok(f"  Renamed branch '{old}' → '{new}'"))

        elif names:
            new_branch = names[0]
            start      = names[1] if len(names) > 1 else repo["branch"]
            if new_branch in repo["branches"]:
                print(err(f"  fatal: A branch named '{new_branch}' already exists."))
            else:
                repo["branches"].append(new_branch)
                print(ok(f"  Branch '{new_branch}' created from '{start}'"))
            self._xp(5, "git branch")

        else:
            # List branches
            print()
            for b in repo.get("branches", []):
                active = b == repo["branch"]
                last_h = _short(_fake_hash(b))
                last_m = random.choice(COMMIT_MESSAGES)[:45]
                prefix = f"{BGREEN}*{R}" if active else " "
                v_info = f"  {dim(last_h)} {last_m}" if verbose else ""
                print(f"  {prefix} {cyan(b) if active else dim(b)}{v_info}")
            if all_f:
                for r_name, r_url in repo.get("remotes",{}).items():
                    for b in repo.get("branches",[]):
                        print(f"    {dim('remotes/'+r_name+'/'+b)}")
            print()

    # ─── git checkout ─────────────────────────────────────────────────────────

    def _checkout(self, args):
        result = self._active_repo()
        if not result: return
        repo, name = result

        new_branch = "-b" in args
        names = [a for a in args if not a.startswith("-")]

        if not names:
            print(warn("  Usage: git checkout [-b] <branch|file>")); return

        target = names[0]

        if new_branch:
            if target in repo["branches"]:
                print(err(f"  fatal: A branch named '{target}' already exists."))
                return
            repo["branches"].append(target)
            repo["branch"] = target
            print(ok(f"  Switched to a new branch '{target}'"))
            self._xp(6, "git checkout -b")
        elif target in repo["branches"]:
            old = repo["branch"]
            repo["branch"] = target
            print(ok(f"  Switched to branch '{target}'"))
            if repo.get("unstaged"):
                print(warn(f"  M\t{repo['unstaged'][0]}"))
        elif target in repo.get("unstaged", []):
            # Restore file
            repo["unstaged"].remove(target)
            print(ok(f"  Updated 1 path from the index"))
        else:
            print(err(f"  error: pathspec '{target}' did not match any file(s) known to git"))

    def _switch(self, args):
        """git switch — modern replacement for git checkout -b/-"""
        create = "-c" in args or "--create" in args
        names  = [a for a in args if not a.startswith("-")]
        if not names:
            print(warn("  Usage: git switch [-c] <branch>")); return
        if create:
            self._checkout(["-b", names[0]])
        else:
            self._checkout([names[0]])

    # ─── git merge ────────────────────────────────────────────────────────────

    def _merge(self, args):
        result = self._active_repo()
        if not result: return
        repo, name = result

        no_ff    = "--no-ff" in args
        squash   = "--squash" in args
        abort    = "--abort" in args
        branches = [a for a in args if not a.startswith("-")]

        if abort:
            print(ok("  Merge aborted. Working tree restored."))
            return

        if not branches:
            print(warn("  Usage: git merge <branch>")); return

        src = branches[0]
        dst = repo["branch"]

        if src not in repo.get("branches", []):
            print(err(f"  merge: {src} - not something we can merge")); return

        # Simulate conflict randomly on hard difficulty
        if self.s.get("difficulty", 2) >= 3 and random.random() > 0.7:
            conflict_file = random.choice(FAKE_FILES)
            print(warn(f"  Auto-merging {conflict_file}"))
            print(err(f"  CONFLICT (content): Merge conflict in {conflict_file}"))
            print(err("  Automatic merge failed; fix conflicts and then commit."))
            print(dim("  Tip: resolve conflicts, then: git add . && git commit"))
            repo["dirty"] = True
            return

        h   = _fake_hash(src + dst)
        msg = f"Merge branch '{src}' into {dst}"

        if squash:
            print(ok(f"  Squash merge of '{src}' into '{dst}'"))
            print(dim("  Run: git commit to complete the squash merge"))
            return

        repo["commits"].append({
            "hash": h, "short": _short(h),
            "msg": msg, "author": self.s.get("username","user"),
            "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        })

        method = "Merge made by 'ort' strategy" if no_ff else "Fast-forward"
        print(ok(f"  {method}"))
        n_files = random.randint(2,6)
        print(dim(f"  {n_files} file(s) changed"))
        self._xp(8, "git merge")

    # ─── git rebase ───────────────────────────────────────────────────────────

    def _rebase(self, args):
        result = self._active_repo()
        if not result: return
        repo, name = result

        interactive = "-i" in args
        onto        = "--onto" in args
        abort       = "--abort" in args
        cont        = "--continue" in args
        branches    = [a for a in args if not a.startswith("-")]

        if abort:
            print(ok("  Rebase aborted. HEAD is now at " + _short(_fake_hash("abort"))))
            return

        if cont:
            print(ok("  Applying: " + random.choice(COMMIT_MESSAGES)))
            print(ok("  Successfully rebased and updated refs/heads/" + repo["branch"]))
            return

        if interactive:
            target = branches[0] if branches else "HEAD~3"
            n = 3
            if "~" in target:
                try: n = int(target.split("~")[1])
                except: n = 3
            print(info(f"\n  Interactive rebase — {n} commit(s)"))
            print(dim("  (In a real terminal, your editor would open with:)\n"))
            commits = list(reversed(repo.get("commits", [])))[:n]
            for c in commits:
                print(f"  {BGREEN}pick{R} {dim(c['short'])} {c['msg']}")
            print()
            print(dim("  Commands: pick=use  reword=edit msg  edit=pause  squash=meld  drop=remove"))
            print(dim("  (simulated — treating as 'pick' for all)"))
            self._xp(15, "git rebase -i")
            return

        target = branches[0] if branches else "main"
        spinner(f"Rebasing onto {target}", 0.8)

        commits = repo.get("commits", [])
        n = min(len(commits), 3)
        for i, c in enumerate(commits[-n:], 1):
            new_h = _fake_hash(c["hash"])
            print(f"  Applying: {dim(_short(new_h))} {c['msg']}")
            c["hash"]  = new_h
            c["short"] = _short(new_h)
            time.sleep(0.08)

        print(ok(f"\n  Successfully rebased onto '{target}'"))
        print(dim("  Note: rebase rewrites history — avoid on shared branches"))
        self._xp(12, "git rebase")

    # ─── git diff ─────────────────────────────────────────────────────────────

    def _diff(self, args):
        result = self._active_repo()
        if not result: return
        repo, name = result

        staged   = "--staged" in args or "--cached" in args
        stat     = "--stat" in args
        target   = next((a for a in args if not a.startswith("-")), None)

        files    = repo.get("staged" if staged else "unstaged", [])

        if not files:
            print(dim("  (no differences)"))
            return

        for f in files[:3]:
            print(f"\n  {BYELLOW}diff --git a/{f} b/{f}{R}")
            print(dim(f"  --- a/{f}"))
            print(dim(f"  +++ b/{f}"))
            n_hunks = random.randint(1, 3)
            for _ in range(n_hunks):
                line_start = random.randint(1, 80)
                print(dim(f"  @@ -{line_start},{random.randint(3,8)} +{line_start},{random.randint(3,12)} @@"))
                for _ in range(random.randint(2, 5)):
                    t = random.choice(["add","del","ctx","ctx"])
                    if t == "add":
                        print(f"  {BGREEN}+  {random.choice(['const x = require(\"express\")', 'app.use(helmet())', 'module.exports = router', 'res.json({ status: \"ok\" })'])}{R}")
                    elif t == "del":
                        print(f"  {BRED}-  {random.choice(['var x = require(\"express\")', '// TODO: fix this', 'console.log(data)', 'callback(err)'])}{R}")
                    else:
                        print(dim(f"     {random.choice(['', 'const router = express.Router()', 'app.listen(PORT)'])}"))

        if stat:
            print(f"\n  {len(files)} file(s) changed")

        self.s.add_xp(3, "git diff")

    # ─── git stash ────────────────────────────────────────────────────────────

    def _stash(self, args):
        result = self._active_repo()
        if not result: return
        repo, name = result

        sub = args[0] if args else "push"

        if sub in ("push", "save", "") or sub == "push":
            msg = args[1] if len(args) > 1 and not args[1].startswith("-") else None
            label = f"WIP on {repo['branch']}: {_short(_fake_hash('stash'))} {random.choice(COMMIT_MESSAGES)[:30]}"
            if msg:
                label = f"On {repo['branch']}: {msg}"
            repo["stashes"].insert(0, {"msg": label, "files": list(repo.get("unstaged",[]))})
            repo["unstaged"] = []
            print(ok(f"  Saved working directory and index state"))
            print(dim(f"  {label}"))
            self._xp(5, "git stash")

        elif sub == "pop":
            if not repo["stashes"]:
                print(warn("  No stash entries found.")); return
            entry = repo["stashes"].pop(0)
            repo["unstaged"] = entry.get("files", [])
            print(ok(f"  Dropped refs/stash@{{0}} ({_short(_fake_hash('pop'))})"))
            self._xp(4, "git stash pop")

        elif sub == "list":
            if not repo["stashes"]:
                print(dim("  (no stash entries)")); return
            for i, st in enumerate(repo["stashes"]):
                print(f"  {BYELLOW}stash@{{{i}}}{R}: {st['msg']}")

        elif sub == "drop":
            idx = int(args[1]) if len(args) > 1 else 0
            if idx < len(repo["stashes"]):
                dropped = repo["stashes"].pop(idx)
                print(ok(f"  Dropped stash@{{{idx}}} ({dropped['msg'][:40]})"))

        elif sub == "apply":
            if repo["stashes"]:
                entry = repo["stashes"][0]
                repo["unstaged"] += entry.get("files",[])
                print(ok(f"  Applied stash@{{0}}"))

        elif sub == "clear":
            repo["stashes"] = []
            print(ok("  All stash entries dropped."))

        elif sub == "show":
            if repo["stashes"]:
                st = repo["stashes"][0]
                for f in st.get("files", []):
                    print(f"  {dim(f)} | {random.randint(1,20)} +-")

    # ─── git remote ───────────────────────────────────────────────────────────

    def _remote(self, args):
        result = self._active_repo()
        if not result: return
        repo, name = result

        sub = args[0] if args else "list"

        if sub in ("-v","--verbose","list",""):
            if not repo.get("remotes"):
                print(dim("  (no remotes configured)"))
                print(dim("  Tip: git remote add origin <url>"))
                return
            for r_name, url in repo["remotes"].items():
                print(f"  {cyan(r_name)}\t{url} (fetch)")
                print(f"  {cyan(r_name)}\t{url} (push)")

        elif sub == "add":
            if len(args) < 3:
                print(warn("  Usage: git remote add <name> <url>")); return
            r_name, url = args[1], args[2]
            repo["remotes"][r_name] = url
            print(ok(f"  Remote '{r_name}' added → {url}"))
            self._xp(5, "git remote add")

        elif sub in ("remove","rm"):
            r_name = args[1] if len(args) > 1 else ""
            if r_name in repo["remotes"]:
                del repo["remotes"][r_name]
                print(ok(f"  Removed remote '{r_name}'"))
            else:
                print(err(f"  fatal: No such remote: '{r_name}'"))

        elif sub == "rename":
            if len(args) < 3: return
            old, new = args[1], args[2]
            if old in repo["remotes"]:
                repo["remotes"][new] = repo["remotes"].pop(old)
                print(ok(f"  Renamed remote '{old}' → '{new}'"))

        elif sub == "set-url":
            if len(args) < 3: return
            r_name, url = args[1], args[2]
            repo["remotes"][r_name] = url
            print(ok(f"  Updated remote '{r_name}' URL → {url}"))

    # ─── git tag ──────────────────────────────────────────────────────────────

    def _tag(self, args):
        result = self._active_repo()
        if not result: return
        repo, name = result

        delete  = "-d" in args
        annot   = "-a" in args
        msg     = None
        for i, a in enumerate(args):
            if a == "-m" and i+1 < len(args): msg = args[i+1]

        names = [a for a in args if not a.startswith("-") and a != msg]

        if not names:
            if not repo["tags"]:
                print(dim("  (no tags)")); return
            for t in repo["tags"]:
                print(f"  {cyan(t)}")
            return

        tag_name = names[0]
        if delete:
            if tag_name in repo["tags"]:
                repo["tags"].remove(tag_name)
                print(ok(f"  Deleted tag '{tag_name}'"))
            else:
                print(err(f"  error: tag '{tag_name}' not found."))
        else:
            repo["tags"].append(tag_name)
            if annot:
                print(ok(f"  Annotated tag '{tag_name}' created"))
                if msg: print(dim(f"  Message: {msg}"))
            else:
                print(ok(f"  Tag '{tag_name}' created"))
            self._xp(5, "git tag")

    # ─── git reset ────────────────────────────────────────────────────────────

    def _reset(self, args):
        result = self._active_repo()
        if not result: return
        repo, name = result

        mode   = "mixed"
        if "--soft" in args:  mode = "soft"
        if "--hard" in args:  mode = "hard"
        if "--mixed" in args: mode = "mixed"

        target = next((a for a in args if not a.startswith("-")), "HEAD~1")

        if mode == "hard":
            print(warn("  ⚠ Hard reset discards all local changes — cannot be undone easily!"))
            repo["staged"]   = []
            repo["unstaged"] = []
            if repo["commits"]:
                repo["commits"].pop()
            print(ok(f"  HEAD is now at {_short(_fake_hash('reset'))} {random.choice(COMMIT_MESSAGES)[:40]}"))
        elif mode == "soft":
            if repo["commits"]:
                c = repo["commits"].pop()
                repo["staged"] = c.get("files", [])
            print(ok(f"  HEAD reset (soft) — changes kept in staging area"))
        else:
            if repo["commits"]:
                c = repo["commits"].pop()
                repo["staged"]   = []
                repo["unstaged"] = c.get("files", [])
            print(ok(f"  Unstaged changes after reset: {target}"))

        print(dim(f"  Mode: --{mode}"))
        self._xp(6, "git reset")

    # ─── git revert ───────────────────────────────────────────────────────────

    def _revert(self, args):
        result = self._active_repo()
        if not result: return
        repo, name = result
        target = args[0] if args else "HEAD"
        h = _fake_hash("revert")
        msg = f"Revert \"{random.choice(COMMIT_MESSAGES)[:40]}\""
        repo["commits"].append({
            "hash": h, "short": _short(h),
            "msg": msg, "author": self.s.get("username","user"),
            "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        print(ok(f"  [{repo['branch']} {_short(h)}] {msg}"))
        print(dim("  Revert creates a new commit — safe for shared branches"))
        self._xp(8, "git revert")

    # ─── git cherry-pick ──────────────────────────────────────────────────────

    def _cherry_pick(self, args):
        result = self._active_repo()
        if not result: return
        repo, name = result
        if not args:
            print(warn("  Usage: git cherry-pick <commit-hash>")); return
        src_hash = args[0]
        new_h    = _fake_hash(src_hash)
        msg      = random.choice(COMMIT_MESSAGES)
        repo["commits"].append({
            "hash": new_h, "short": _short(new_h),
            "msg": msg, "author": self.s.get("username","user"),
            "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        print(ok(f"  [{repo['branch']} {_short(new_h)}] {msg}"))
        print(dim(f"  Cherry-picked {src_hash[:7] if len(src_hash)>7 else src_hash} → {_short(new_h)}"))
        self._xp(8, "git cherry-pick")

    # ─── git reflog ───────────────────────────────────────────────────────────

    def _reflog(self, args):
        result = self._active_repo()
        if not result: return
        repo, name = result

        commits = list(reversed(repo.get("commits", [])))[:8]
        actions = ["commit","checkout","reset","merge","rebase","pull"]
        print()
        for i, c in enumerate(commits):
            action = actions[i % len(actions)]
            print(f"  {BYELLOW}{c['short']}{R} HEAD@{{{i}}}: {action}: {c['msg'][:50]}")
        print(dim("\n  reflog shows where HEAD has been — useful for recovering lost commits"))
        self.s.add_xp(4, "git reflog")

    # ─── git bisect ───────────────────────────────────────────────────────────

    def _bisect(self, args):
        result = self._active_repo()
        if not result: return
        repo, name = result

        sub = args[0] if args else "help"
        if sub == "start":
            print(ok("  Bisect started. Mark commits as good/bad."))
            print(dim("  git bisect good <hash>  — mark as working"))
            print(dim("  git bisect bad <hash>   — mark as broken"))
            print(dim("  git bisect reset        — exit bisect mode"))
            repo["bisect_active"] = True
        elif sub == "good":
            print(ok(f"  Marked as good. Checking {_short(_fake_hash('good'))}..."))
        elif sub == "bad":
            guilty = _short(_fake_hash("bad"))
            print(warn(f"  {guilty} is the first bad commit."))
            print(dim("  git bisect reset  to return to normal"))
        elif sub == "reset":
            repo["bisect_active"] = False
            print(ok("  Bisect reset. Back on " + repo["branch"]))
        self.s.add_xp(5, "git bisect")

    # ─── git submodule ────────────────────────────────────────────────────────

    def _submodule(self, args):
        result = self._active_repo()
        if not result: return
        repo, name = result
        sub = args[0] if args else "status"

        if sub == "add":
            url  = args[1] if len(args) > 1 else "https://github.com/example/lib"
            path = args[2] if len(args) > 2 else url.split("/")[-1]
            spinner(f"Adding submodule {path}", 0.8)
            repo.setdefault("submodules", {})[path] = url
            print(ok(f"  Submodule '{path}' added at {url}"))
            self._xp(8, "git submodule add")
        elif sub == "update":
            spinner("Updating submodules", 0.6)
            print(ok("  All submodules updated to latest commit"))
        elif sub == "status":
            mods = repo.get("submodules", {})
            if not mods:
                print(dim("  No submodules configured.")); return
            for path, url in mods.items():
                h = _short(_fake_hash(path))
                print(f"  {BYELLOW}{h}{R} {path} ({dim(url)})")
        elif sub == "init":
            print(ok("  Submodule paths initialized."))

    # ─── git worktree ─────────────────────────────────────────────────────────

    def _worktree(self, args):
        result = self._active_repo()
        if not result: return
        repo, name = result
        sub = args[0] if args else "list"

        if sub == "add":
            path   = args[1] if len(args) > 1 else "../worktree"
            branch = args[2] if len(args) > 2 else "worktree-branch"
            repo.setdefault("worktrees", {})[path] = branch
            print(ok(f"  Worktree added at '{path}' on branch '{branch}'"))
            self._xp(8, "git worktree")
        elif sub == "list":
            wt = repo.get("worktrees", {})
            print(f"  {repo.get('path','.')}  {_short(_fake_hash('main'))}  [{repo['branch']}]")
            for path, branch in wt.items():
                print(f"  {path}  {_short(_fake_hash(path))}  [{branch}]")
        elif sub in ("remove","prune"):
            print(ok(f"  Worktree pruned."))

    # ─── git show ─────────────────────────────────────────────────────────────

    def _show(self, args):
        result = self._active_repo()
        if not result: return
        repo, name = result
        target = args[0] if args else "HEAD"
        commits = repo.get("commits", [])
        c = commits[-1] if commits else None
        if not c:
            print(warn("  Nothing to show.")); return
        print(f"\n  {BYELLOW}commit {c['hash']}{R}")
        print(f"  Author: {c['author']} <{c['author']}@sysops.local>")
        print(f"  Date:   {c['date']}")
        print(f"\n      {c['msg']}\n")
        for f in c.get("files", [])[:3]:
            print(f"  {BGREEN}+++{R} b/{f}")

    # ─── git shortlog ─────────────────────────────────────────────────────────

    def _shortlog(self, args):
        result = self._active_repo()
        if not result: return
        repo, name = result
        authors = {}
        for c in repo.get("commits", []):
            a = c.get("author", "unknown")
            authors[a] = authors.get(a, 0) + 1
        for author, count in sorted(authors.items(), key=lambda x: -x[1]):
            print(f"  {count:>5}  {author}")

    # ─── git blame ────────────────────────────────────────────────────────────

    def _blame(self, args):
        file_ = args[0] if args else "src/index.js"
        result = self._active_repo()
        if not result: return
        repo, name = result
        commits = repo.get("commits", [])
        print(f"\n  {dim(file_)}")
        for i in range(8):
            c     = commits[i % max(1,len(commits))]
            user  = c.get("author", self.s.get("username","user"))
            h     = c.get("short", "abc1234")
            line  = random.choice([
                "const express = require('express');",
                "app.use(helmet());",
                "module.exports = router;",
                "const PORT = process.env.PORT || 3000;",
                "app.listen(PORT, () => console.log(`Server on ${PORT}`));",
            ])
            print(f"  {BYELLOW}{h}{R} ({dim(user):<12} {dim(c.get('date','')[:10])}) {i+1:>3}) {line}")
        print()

    # ─── git clean ────────────────────────────────────────────────────────────

    def _clean(self, args):
        result = self._active_repo()
        if not result: return
        repo, name = result
        dry_run = "-n" in args
        force   = "-f" in args
        dirs    = "-d" in args
        if not force and not dry_run:
            print(warn("  fatal: clean.requireForce defaults to true."))
            print(dim("  Use -f to force, or -n for a dry run.")); return
        junk = ["node_modules/", ".DS_Store", "dist/", "__pycache__/", "*.log"]
        for j in junk:
            if dry_run:
                print(dim(f"  Would remove {j}"))
            else:
                print(ok(f"  Removing {j}"))
        if not dry_run:
            self._xp(4, "git clean")

    # ─── git config ───────────────────────────────────────────────────────────

    def _config(self, args):
        global_f = "--global" in args
        list_f   = "--list" in args

        if list_f:
            user = self.s.get("username","user")
            print(f"  user.name={user}")
            print(f"  user.email={user}@sysops.local")
            print(f"  core.editor=nvim")
            print(f"  core.autocrlf=input")
            print(f"  push.default=current")
            print(f"  pull.rebase=false")
            print(f"  alias.st=status")
            print(f"  alias.co=checkout")
            print(f"  alias.br=branch")
            print(f"  alias.lg=log --oneline --graph --all")
            return

        keys = [a for a in args if not a.startswith("-") and "=" not in a]
        kvs  = [a for a in args if "=" in a]

        if kvs:
            k, v = kvs[0].split("=", 1)
            scope = "global" if global_f else "local"
            print(ok(f"  {scope}: {k} = {v}"))
        elif len(keys) == 2:
            k, v = keys[0], keys[1]
            scope = "global" if global_f else "local"
            print(ok(f"  {scope}: {k} = {v}"))
        elif len(keys) == 1:
            vals = {"user.name": self.s.get("username","user"),
                    "user.email": self.s.get("username","user")+"@sysops.local",
                    "core.editor": "nvim",
                    "push.default": "current"}
            print(f"  {vals.get(keys[0], '(not set)')}")

    # ─── Help ─────────────────────────────────────────────────────────────────

    def _help(self):
        lines = [
            f"  {bold('// BASICS')}",
            f"  {cyan('git init [dir]')}                start a repo",
            f"  {cyan('git clone <url> [dir]')}         clone remote repo",
            f"  {cyan('git status')}                    show working tree state",
            f"  {cyan('git add <file|.|-A>')}           stage changes",
            f"  {cyan('git commit -m \"msg\"')}           save snapshot",
            f"  {cyan('git commit --amend')}             edit last commit",
            "",
            f"  {bold('// REMOTE')}",
            f"  {cyan('git push [-u] [remote] [branch]')} upload commits",
            f"  {cyan('git push --force-with-lease')}   safe force push",
            f"  {cyan('git pull [--rebase]')}           fetch + integrate",
            f"  {cyan('git fetch [remote]')}            download without merge",
            f"  {cyan('git remote add origin <url>')}   link remote",
            f"  {cyan('git remote -v')}                 list remotes",
            "",
            f"  {bold('// BRANCHES')}",
            f"  {cyan('git branch')}                    list branches",
            f"  {cyan('git branch <name>')}             create branch",
            f"  {cyan('git checkout -b <name>')}        create + switch",
            f"  {cyan('git switch -c <name>')}          modern equivalent",
            f"  {cyan('git merge [--no-ff] <branch>')}  merge branch",
            f"  {cyan('git rebase [-i] <branch>')}      rebase (interactive)",
            f"  {cyan('git cherry-pick <hash>')}        apply single commit",
            "",
            f"  {bold('// HISTORY & INSPECTION')}",
            f"  {cyan('git log [--oneline] [--graph]')} commit history",
            f"  {cyan('git diff [--staged]')}           show changes",
            f"  {cyan('git show [hash]')}               inspect commit",
            f"  {cyan('git blame <file>')}              line-by-line authorship",
            f"  {cyan('git reflog')}                    HEAD movement history",
            f"  {cyan('git shortlog')}                  commits by author",
            "",
            f"  {bold('// UNDO')}",
            f"  {cyan('git reset --soft/--mixed/--hard')} undo commits",
            f"  {cyan('git revert <hash>')}             safe undo (new commit)",
            f"  {cyan('git stash [push/pop/list/drop]')} shelve changes",
            f"  {cyan('git clean -fd')}                 remove untracked files",
            "",
            f"  {bold('// ADVANCED')}",
            f"  {cyan('git tag [-a] <name>')}           create release tag",
            f"  {cyan('git bisect start/good/bad')}     binary-search bug",
            f"  {cyan('git submodule add <url>')}       embed sub-repo",
            f"  {cyan('git worktree add <path>')}       multiple working trees",
            f"  {cyan('git config [--global] --list')}  view config",
        ]
        box("git — Full Reference", lines, border_color=BYELLOW, width=72)
