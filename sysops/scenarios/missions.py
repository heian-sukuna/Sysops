"""
scenarios/missions.py — All scenarios, missions, and combo challenges
"""

from core.ui import *
from scenarios.checks import ran, ran_any, ran_re, either

# ─── SCENARIOS ────────────────────────────────────────────────────────────────
# Each scenario: id, title, category, difficulty(1-4), tags, story, steps, xp_reward
# Step: (description, check_fn(world, save) -> bool, hint)

SCENARIOS = [

    # ── TAILSCALE + RSYNC ────────────────────────────────────────────────────
    {
        "id": "ts01",
        "title": "First Contact",
        "category": "tailscale + rsync",
        "difficulty": 1,
        "tags": ["TAILSCALE","RSYNC","EASY"],
        "story": (
            "You just spun up a server called 'projects'. Your laptop and server are "
            "both running Tailscale. Mission: connect to the tailnet, verify the server "
            "is reachable, and transfer report.pdf to the server."
        ),
        "steps": [
            ("Run tailscale up",
             lambda w,s: w.tailscale_up,
             "tailscale up"),
            ("Check tailscale status to see peers",
             lambda w,s: w.tailscale_up,
             "tailscale status"),
            ("Ping the server",
             lambda w,s: w.peers.get("server",{}).get("status") == "online",
             "ping projects"),
            ("Transfer report.pdf to projects",
             lambda w,s: any("report.pdf" in k for k in w.fs.get("server",{})),
             "rsync -avh --progress ~/Documents/report.pdf user@server:/home/user/backups/"),
        ],
        "xp_reward": 60,
    },

    {
        "id": "ts02",
        "title": "Big File Haul",
        "category": "tailscale + rsync",
        "difficulty": 2,
        "tags": ["TAILSCALE","RSYNC","MEDIUM"],
        "story": (
            "You need to move an 850MB video file to the server. "
            "SSH keys should be set up first for passwordless transfers. "
            "Use the optimal large-file flags: --partial, --inplace, --no-compress."
        ),
        "steps": [
            ("Connect to Tailscale",
             lambda w,s: w.tailscale_up,
             "tailscale up"),
            ("Generate an SSH key pair",
             lambda w,s: w.ssh_key_exists,
             "ssh-keygen"),
            ("Install SSH key on server",
             lambda w,s: "server" in w.ssh_keys_copied,
             "ssh-copy-id user@server"),
            ("Transfer demo.mp4 with optimal large-file flags",
             lambda w,s: any("demo.mp4" in k for k in w.fs.get("server",{})),
             "rsync -avh --progress --partial --inplace --no-compress ~/Videos/demo.mp4 user@server:/mnt/storage/"),
        ],
        "xp_reward": 90,
    },

    {
        "id": "ts03",
        "title": "Maximum Throughput",
        "category": "tailscale + rsync",
        "difficulty": 3,
        "tags": ["TAILSCALE","RSYNC","HARD"],
        "story": (
            "A 3.2GB archive needs to go to the server fast. "
            "Use the fastest SSH cipher (aes128-gcm), disable SSH compression, "
            "and use --inplace + --partial. Check tailscale status first — "
            "if the link is via relay, speeds will suffer."
        ),
        "steps": [
            ("Verify tailscale status and connection type",
             lambda w,s: w.tailscale_up,
             "tailscale status"),
            ("Use fastest cipher and flags for the 3.2GB archive",
             lambda w,s: any("archive.tar.gz" in k for k in w.fs.get("server",{})),
             'rsync -avh --progress --partial --inplace -e "ssh -T -c aes128-gcm@openssh.com -o Compression=no" ~/backups/archive.tar.gz user@server:/mnt/storage/'),
        ],
        "xp_reward": 120,
    },

    # ── DOCKER ───────────────────────────────────────────────────────────────
    {
        "id": "dk01",
        "title": "Container Launch",
        "category": "docker",
        "difficulty": 1,
        "tags": ["DOCKER","EASY"],
        "story": (
            "Deploy an nginx web server using Docker. Pull the image, run it "
            "on port 8080, verify it's running, check logs, then stop and remove it cleanly."
        ),
        "steps": [
            ("Pull the nginx image",
             lambda w,s: "nginx" in w.docker_images,
             "docker pull nginx"),
            ("Run nginx on port 8080 in detached mode",
             lambda w,s: any(c["status"]=="running" and "nginx" in c["image"]
                             for c in w.docker_containers.values()),
             "docker run -d --name webserver -p 8080:80 nginx"),
            ("Verify the container is running",
             lambda w,s: "webserver" in w.docker_containers,
             "docker ps"),
            ("View the container logs",
             ran("docker logs"),
             "docker logs webserver"),
            ("Stop the container",
             lambda w,s: w.docker_containers.get("webserver",{}).get("status") == "exited",
             "docker stop webserver"),
            ("Remove the container",
             lambda w,s: "webserver" not in w.docker_containers,
             "docker rm webserver"),
        ],
        "xp_reward": 70,
    },

    {
        "id": "dk02",
        "title": "Compose the Stack",
        "category": "docker",
        "difficulty": 2,
        "tags": ["DOCKER","MEDIUM"],
        "story": (
            "Launch the full Portfolio stack with docker compose. "
            "All three services — nginx, frontend, backend — should be running "
            "on the private app-net bridge network."
        ),
        "steps": [
            ("Start all services with docker compose",
             lambda w,s: all(svc in w.docker_containers and w.docker_containers[svc]["status"]=="running"
                             for svc in ["nginx","frontend","backend"]),
             "docker compose up -d"),
            ("Verify all three services are running",
             lambda w,s: len([c for c in w.docker_containers.values() if c["status"]=="running"]) >= 3,
             "docker ps"),
            ("Check backend logs",
             ran("docker logs"),
             "docker logs backend"),
            ("Inspect the nginx container",
             ran("docker inspect"),
             "docker inspect nginx"),
        ],
        "xp_reward": 80,
    },

    {
        "id": "dk03",
        "title": "Build & Ship",
        "category": "docker",
        "difficulty": 3,
        "tags": ["DOCKER","HARD"],
        "story": (
            "Build a custom image from a Dockerfile, run it with environment "
            "variables and a mounted volume, check stats, then clean up "
            "using docker system prune."
        ),
        "steps": [
            ("Build a custom image tagged sysops-app:v1",
             lambda w,s: "sysops-app:v1" in w.docker_images,
             "docker build -t sysops-app:v1 ."),
            ("Run it with env var PORT=3000 and volume mount",
             lambda w,s: any("sysops-app" in c["image"] and c["status"]=="running"
                             for c in w.docker_containers.values()),
             "docker run -d --name myapp -e PORT=3000 -v /data:/app/data -p 3000:3000 sysops-app:v1"),
            ("Check live resource stats",
             ran("docker stats"),
             "docker stats"),
            ("Stop and remove the container",
             lambda w,s: not any("sysops-app" in c["image"] and c["status"]=="running"
                                 for c in w.docker_containers.values()),
             "docker stop myapp && docker rm myapp"),
            ("Clean up disk with system prune",
             ran("docker", "prune"),
             "docker system prune"),
        ],
        "xp_reward": 110,
    },

    # ── NGINX ────────────────────────────────────────────────────────────────
    {
        "id": "nx01",
        "title": "Reverse Proxy Setup",
        "category": "nginx",
        "difficulty": 2,
        "tags": ["NGINX","MEDIUM"],
        "story": (
            "Configure nginx as a reverse proxy for the portfolio. "
            "Create a site config, enable it, test the configuration, then reload nginx."
        ),
        "steps": [
            ("Start nginx via docker",
             lambda w,s: w.nginx_running,
             "docker run -d --name nginx -p 80:80 nginx"),
            ("Create the site configuration",
             lambda w,s: bool(w.nginx_configs),
             "nginx config create my-portfolio"),
            ("Enable the site config",
             lambda w,s: any(k.startswith("/etc/nginx/sites-enabled/")
                             and len(k) > len("/etc/nginx/sites-enabled/")
                             for k in w.fs.get("server",{})),
             "nginx config enable my-portfolio"),
            ("Test the nginx config for errors",
             ran("nginx test"),
             "nginx test"),
            ("Reload nginx to apply changes",
             ran("nginx", "reload"),
             "nginx reload"),
        ],
        "xp_reward": 85,
    },

    {
        "id": "nx02",
        "title": "SSL/TLS Termination",
        "category": "nginx",
        "difficulty": 3,
        "tags": ["NGINX","SECURITY","HARD"],
        "story": (
            "Add HTTPS to your nginx reverse proxy. Configure TLS 1.3, "
            "add an SSL certificate block, and include security headers "
            "(HSTS, CSP, X-Frame-Options)."
        ),
        "steps": [
            ("Create the base site config",
             lambda w,s: bool(w.nginx_configs),
             "nginx config create app.ts.net"),
            ("Add SSL configuration",
             ran("ssl"),
             "nginx config ssl app.ts.net"),
            ("Test configuration is valid",
             ran("nginx test"),
             "nginx test"),
            ("Reload to serve HTTPS",
             ran("nginx", "reload"),
             "nginx reload"),
        ],
        "xp_reward": 100,
    },

    # ── NETWORKING ───────────────────────────────────────────────────────────
    {
        "id": "net01",
        "title": "Network Audit",
        "category": "networking",
        "difficulty": 1,
        "tags": ["NETWORKING","EASY"],
        "story": (
            "Perform a baseline audit of the local machine's network state. "
            "Check listening ports, interface addresses, routing table, "
            "and ARP neighbours."
        ),
        "steps": [
            ("Show all network interfaces",
             ran("ip addr"),
             "ip addr"),
            ("Show listening ports and PIDs",
             ran_any("ss", "netstat"),
             "ss -tulnp"),
            ("Show the routing table",
             ran_any("ip route", "route"),
             "ip route"),
            ("Check ARP neighbours",
             ran("arp"),
             "arp -n"),
        ],
        "xp_reward": 45,
    },

    # ── CYBERSECURITY ────────────────────────────────────────────────────────
    {
        "id": "cy01",
        "title": "Recon & Enumeration",
        "category": "cybersec",
        "difficulty": 2,
        "tags": ["SECURITY","CYBER","MEDIUM"],
        "story": (
            "You're a junior analyst. You've been given an IP to assess. "
            "Run a full nmap scan, enumerate web directories with gobuster, "
            "and scan for web vulnerabilities with nikto. Document your findings."
        ),
        "steps": [
            ("Run a version + OS detection scan",
             lambda w,s: len(w.known_hosts) > 0,
             "nmap -sV -O 100.64.1.20"),
            ("Run aggressive scan with vuln scripts",
             lambda w,s: any(h.get("vulns") for h in w.known_hosts.values()),
             "nmap -A --script vuln 100.64.1.20"),
            ("Enumerate web directories",
             ran("gobuster"),
             "gobuster dir -u http://100.64.1.20 -w /usr/share/wordlists/dirb/common.txt"),
            ("Run a web vulnerability scan",
             ran("nikto"),
             "nikto -h 100.64.1.20"),
        ],
        "xp_reward": 120,
    },

    {
        "id": "cy02",
        "title": "Packet Analysis",
        "category": "cybersec",
        "difficulty": 2,
        "tags": ["SECURITY","CYBER","MEDIUM"],
        "story": (
            "Suspicious traffic has been flagged on the network. "
            "Capture packets on eth0, filter for HTTP traffic specifically, "
            "save the capture, then analyse it."
        ),
        "steps": [
            ("Capture 20 packets on eth0",
             lambda w,s: len(w.captured_packets) > 0,
             "tshark -i eth0 -c 20"),
            ("Capture only HTTP traffic and save it",
             lambda w,s: len(w.captured_packets) > 0,
             "tshark -i eth0 -f 'tcp port 80' -c 30 -w http_capture.pcap"),
            ("Read back the saved capture",
             ran("tshark -r"),
             "tshark -r http_capture.pcap"),
        ],
        "xp_reward": 90,
    },

    {
        "id": "cy03",
        "title": "Host Hardening",
        "category": "cybersec",
        "difficulty": 3,
        "tags": ["SECURITY","HARD"],
        "story": (
            "The server scored poorly on a security audit. Harden it: "
            "run lynis to identify gaps, configure ufw firewall rules, "
            "and set up fail2ban to block brute force attacks."
        ),
        "steps": [
            ("Run a full lynis security audit",
             ran("lynis"),
             "lynis audit system"),
            ("Enable the UFW firewall",
             ran("ufw enable"),
             "ufw enable"),
            ("Allow only necessary ports (22, 80, 443)",
             ran("ufw allow"),
             "ufw allow 22 && ufw allow 80 && ufw allow 443"),
            ("Check fail2ban status for sshd jail",
             ran("fail2ban"),
             "fail2ban-client status sshd"),
        ],
        "xp_reward": 130,
    },

    # ── BASICS / NAVIGATION ──────────────────────────────────────────────────
    {
        "id": "rs01",
        "title": "Pack & Ship",
        "category": "rsync",
        "difficulty": 1,
        "tags": ["RSYNC","EASY"],
        "story": (
            "Before the fancy stuff — learn to move around. Find out where you "
            "are, look at your files, make a staging folder, then back your "
            "dataset up to the server with rsync."
        ),
        "steps": [
            ("Print your current working directory",
             ran("pwd"),
             "pwd"),
            ("List the files in your home directory",
             ran("ls"),
             "ls  (try Tab-completion and cd Documents too)"),
            ("Create a 'staging' folder",
             ran("mkdir"),
             "mkdir staging"),
            ("Connect to Tailscale so the server is reachable",
             lambda w,s: w.tailscale_up,
             "tailscale up"),
            ("Back up dataset.csv to the server",
             lambda w,s: any("dataset.csv" in k for k in w.fs.get("server",{})),
             "rsync -avh --progress ~/data/dataset.csv user@server:/home/user/backups/"),
        ],
        "xp_reward": 50,
    },

    # ── SSH ──────────────────────────────────────────────────────────────────
    {
        "id": "ssh01",
        "title": "Key-Based Access",
        "category": "ssh",
        "difficulty": 2,
        "tags": ["SSH","TAILSCALE","MEDIUM"],
        "story": (
            "Typing passwords is for amateurs. Set up key-based SSH to the "
            "server: generate a key pair, install the public key, "
            "then log in passwordless to confirm it works."
        ),
        "steps": [
            ("Connect to Tailscale",
             lambda w,s: w.tailscale_up,
             "tailscale up"),
            ("Generate an SSH key pair",
             lambda w,s: w.ssh_key_exists,
             "ssh-keygen"),
            ("Install your public key on the server",
             lambda w,s: "server" in w.ssh_keys_copied,
             "ssh-copy-id user@server"),
            ("Log into the server over SSH (now passwordless)",
             ran_re(r"^\s*ssh\s+.*server"),   # the ssh command itself, not ssh-copy-id
             "ssh user@server   (type 'exit' to come back)"),
        ],
        "xp_reward": 80,
    },

    # ── NETWORKING (advanced) ────────────────────────────────────────────────
    {
        "id": "net02",
        "title": "DNS & HTTP Recon",
        "category": "networking",
        "difficulty": 2,
        "tags": ["NETWORKING","MEDIUM"],
        "story": (
            "A service is misbehaving. Investigate from the network up: resolve "
            "its DNS record, trace the path to it, inspect the HTTP response, "
            "and confirm what's listening locally."
        ),
        "steps": [
            ("Resolve the A record for the service domain",
             ran("dig"),
             "dig app.ts.net A"),
            ("Trace the network path to the server",
             ran_any("traceroute", "tracepath"),
             "traceroute projects"),
            ("Inspect the HTTP response from the web server",
             ran("curl"),
             "curl -I http://projects"),
            ("Confirm which ports are listening locally",
             ran_any("ss", "netstat"),
             "ss -tulnp"),
        ],
        "xp_reward": 75,
    },

    # ── COMBO MISSIONS ───────────────────────────────────────────────────────
    {
        "id": "combo01",
        "title": "Full Stack Deploy",
        "category": "combo: tailscale + docker + nginx + rsync",
        "difficulty": 3,
        "tags": ["COMBO","HARD"],
        "story": (
            "End-to-end deployment of the portfolio. "
            "Connect Tailscale, spin up all Docker services, configure nginx "
            "as a reverse proxy, then rsync a 3GB archive to the server. "
            "This is the full pipeline."
        ),
        "steps": [
            ("Connect to Tailscale",
             lambda w,s: w.tailscale_up,
             "tailscale up"),
            ("Set up SSH keys for passwordless access",
             lambda w,s: "server" in w.ssh_keys_copied,
             "ssh-keygen && ssh-copy-id user@server"),
            ("Launch full stack with docker compose",
             lambda w,s: all(svc in w.docker_containers and w.docker_containers[svc]["status"]=="running"
                             for svc in ["nginx","frontend","backend"]),
             "docker compose up -d"),
            ("Configure nginx reverse proxy",
             lambda w,s: bool(w.nginx_configs),
             "nginx config create my-portfolio"),
            ("Test and reload nginx",
             ran("nginx", "reload"),
             "nginx test && nginx reload"),
            ("Transfer the 3.2GB archive",
             lambda w,s: any("archive.tar.gz" in k for k in w.fs.get("server",{})),
             "rsync -avh --progress --partial --inplace --no-compress ~/backups/archive.tar.gz user@server:/mnt/storage/"),
        ],
        "xp_reward": 200,
    },

    {
        "id": "combo02",
        "title": "Secure Lab Setup",
        "category": "combo: cybersec + docker + tailscale",
        "difficulty": 4,
        "tags": ["COMBO","CYBER","SECURITY"],
        "story": (
            "NIGHTMARE MODE. Set up a full security monitoring lab. "
            "Connect Tailscale, deploy a vulnerable docker container, "
            "run nmap + gobuster + nikto against it, capture traffic with tshark, "
            "harden the host with ufw + fail2ban, then run lynis for a final score."
        ),
        "steps": [
            ("Connect Tailscale",
             lambda w,s: w.tailscale_up,
             "tailscale up"),
            ("Deploy a target container",
             lambda w,s: any(c["status"]=="running" for c in w.docker_containers.values()),
             "docker run -d --name target -p 8080:80 nginx"),
            ("Full aggressive nmap scan with vuln scripts",
             lambda w,s: any(h.get("vulns") for h in w.known_hosts.values()),
             "nmap -A --script vuln 100.64.1.20"),
            ("Enumerate web directories",
             ran("gobuster"),
             "gobuster dir -u http://100.64.1.20:8080 -w /usr/share/wordlists/dirb/common.txt"),
            ("Capture 30 packets and save to file",
             lambda w,s: len(w.captured_packets) >= 10,
             "tshark -i eth0 -c 30 -w lab_capture.pcap"),
            ("Harden with UFW",
             ran("ufw"),
             "ufw enable && ufw allow 22 && ufw allow 443 && ufw deny 8080"),
            ("Run lynis security audit",
             ran("lynis"),
             "lynis audit system"),
        ],
        "xp_reward": 300,
    },

]

# ─── QUICK CHALLENGES (single-command drills) ─────────────────────────────────

QUICK_CHALLENGES = [
    {
        "id": "qc01",
        "prompt": "What command shows all TCP/UDP listening ports with PIDs?",
        "answers": ["ss -tulnp","netstat -tulnp","ss -tlnp"],
        "explanation": "ss -tulnp: -t=TCP -u=UDP -l=listening -n=numeric -p=PIDs",
        "xp": 10,
    },
    {
        "id": "qc02",
        "prompt": "Rsync a folder to remote, deleting files on dest not in source. Show only overall progress.",
        "answers": [
            "rsync -avh --delete --info=progress2",
            "rsync -avh --delete --progress",
        ],
        "explanation": "--delete mirrors exact source. --info=progress2 gives one overall bar vs per-file.",
        "xp": 15,
    },
    {
        "id": "qc03",
        "prompt": "What nmap flag runs ALL vulnerability detection scripts?",
        "answers": ["--script vuln","--script=vuln"],
        "explanation": "--script vuln loads the 'vuln' category NSE scripts — checks for known CVEs.",
        "xp": 12,
    },
    {
        "id": "qc04",
        "prompt": "Run a docker container in detached mode with container port 3000 exposed on host port 8080.",
        "answers": ["docker run -d -p 8080:3000","docker run --detach -p 8080:3000"],
        "explanation": "-d = detached (background). -p host:container maps the port.",
        "xp": 10,
    },
    {
        "id": "qc05",
        "prompt": "How do you resume a dropped rsync transfer of a large file?",
        "answers": ["rsync --partial --inplace","rsync -avh --partial --inplace","just re-run the same rsync command with --partial"],
        "explanation": "--partial keeps the incomplete file on dest. Re-running the same command resumes from where it stopped.",
        "xp": 15,
    },
    {
        "id": "qc06",
        "prompt": "What tailscale command checks whether a peer is using a direct or relay (DERP) connection?",
        "answers": ["tailscale status","tailscale ping <host>"],
        "explanation": "tailscale status shows 'direct' or 'relay'. tailscale ping shows the path per-ping.",
        "xp": 10,
    },
    {
        "id": "qc07",
        "prompt": "Reload nginx after a config change without dropping connections.",
        "answers": ["nginx -s reload","systemctl reload nginx","nginx reload"],
        "explanation": "nginx -s reload sends SIGHUP — graceful reload, zero downtime.",
        "xp": 10,
    },
    {
        "id": "qc08",
        "prompt": "Filter tshark capture to only show DNS traffic.",
        "answers": ["tshark -f 'udp port 53'","tshark -Y 'dns'","tshark -i eth0 -f 'udp port 53'"],
        "explanation": "-f is a capture filter (BPF). -Y is a display filter. Both work for DNS.",
        "xp": 12,
    },
]

from scenarios.git_redteam_missions import GIT_MISSIONS, REDTEAM_MISSIONS
from scenarios.architecture_missions import ARCH_MISSIONS
from scenarios.blueteam_missions import BLUETEAM_MISSIONS
from scenarios.soc_missions import SOC_MISSIONS
SCENARIOS = (SCENARIOS + GIT_MISSIONS + REDTEAM_MISSIONS + ARCH_MISSIONS
             + BLUETEAM_MISSIONS + SOC_MISSIONS)

def get_scenario(sid):
    return next((s for s in SCENARIOS if s["id"] == sid), None)

def get_scenarios_by_category(cat):
    return [s for s in SCENARIOS if cat.lower() in s["category"].lower()]

def get_scenarios_by_difficulty(diff):
    return [s for s in SCENARIOS if s["difficulty"] == diff]

def get_random_challenge():
    import random
    return random.choice(QUICK_CHALLENGES)
