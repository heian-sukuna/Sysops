"""
core/world.py — Virtual environment state for SYSOPS
Everything the player interacts with: networks, files, containers, scan results.
"""

import random, time

# ── Fake data generators ──────────────────────────────────────────────────────

def fake_mac():
    return ':'.join(f'{random.randint(0,255):02x}' for _ in range(6))

def fake_ip(prefix="192.168"):
    return f"{prefix}.{random.randint(1,254)}.{random.randint(2,254)}"

def fake_cve():
    year = random.randint(2020, 2025)
    num  = random.randint(1000, 99999)
    return f"CVE-{year}-{num}"

SERVICES = {
    22:   ("ssh",     "OpenSSH 8.9"),
    80:   ("http",    "nginx 1.25.3"),
    443:  ("https",   "nginx 1.25.3 (TLS 1.3)"),
    3306: ("mysql",   "MySQL 8.0.36"),
    5432: ("postgres","PostgreSQL 16.2"),
    6379: ("redis",   "Redis 7.2.4"),
    8080: ("http-alt","Apache Tomcat 10.1"),
    8443: ("https-alt","Caddy 2.7.6"),
    21:   ("ftp",     "vsftpd 3.0.5"),
    25:   ("smtp",    "Postfix smtpd"),
    53:   ("dns",     "BIND 9.18"),
    3389: ("rdp",     "xrdp 0.9.23"),
    445:  ("smb",     "Samba 4.18.6"),
    139:  ("netbios", "Samba nmbd"),
    27017:("mongodb", "MongoDB 7.0.5"),
    9200: ("elastic", "Elasticsearch 8.12"),
    5601: ("kibana",  "Kibana 8.12"),
    4789: ("vxlan",   "VXLAN overlay"),
    2377: ("docker",  "Docker Swarm"),
    9090: ("prometheus","Prometheus 2.50"),
    3000: ("grafana", "Grafana 10.3"),
    2049: ("nfs",     "NFS v4"),
    111:  ("rpcbind", "rpcbind v4"),
}

VULN_DB = {
    21:   [("HIGH",   "Anonymous FTP login allowed",         fake_cve())],
    22:   [("LOW",    "SSH weak ciphers accepted",           fake_cve()),
           ("INFO",   "SSH version banner disclosure",       "N/A")],
    80:   [("MEDIUM", "Missing security headers (HSTS, CSP)","N/A"),
           ("LOW",    "Directory listing enabled",           fake_cve())],
    445:  [("CRITICAL","EternalBlue MS17-010 patch missing", "CVE-2017-0144"),
           ("HIGH",   "SMBv1 protocol enabled",             "CVE-2020-0796")],
    3389: [("HIGH",   "BlueKeep-adjacent RDP exposure",     "CVE-2019-0708")],
    27017:("CRITICAL","MongoDB no auth required (open port)","CVE-2021-32036"),
    3306: [("MEDIUM", "MySQL root login from remote allowed","N/A")],
    6379: [("HIGH",   "Redis no authentication configured", "CVE-2022-0543")],
}

# ── Blue-team / SOC simulation ────────────────────────────────────────────────
# A self-consistent intrusion is baked into the host logs so the defensive tools
# (journalctl, grep, siem, ioc, incident) all tell the same story: an external
# host brute-forces SSH, lands on the 'deploy' account, escalates via a sudo
# misconfig, and scans the web app. The breached account is fixed so missions
# can verify the player actually found it.
BREACHED_USER = "deploy"

class VirtualWorld:
    def __init__(self, save_data: dict):
        w = save_data.get("world", {})

        # Tailscale
        self.tailscale_up   = w.get("tailscale_up", False)
        self.tailnet_name   = "tailnet.ts.net"
        self.peers = {
            "laptop":   {"ip":"100.64.1.10","ts_ip":"100.64.1.10","status":"online","relay":False,  "os":"Arch Linux"},
            "server": {"ip":"100.64.1.20","ts_ip":"100.64.1.20","status":"offline","relay":False, "os":"Ubuntu 24.04"},
            "nas":      {"ip":"100.64.1.30","ts_ip":"100.64.1.30","status":"offline","relay":True,  "os":"TrueNAS Scale"},
            "pi":       {"ip":"100.64.1.40","ts_ip":"100.64.1.40","status":"offline","relay":False, "os":"Raspberry Pi OS"},
        }
        if self.tailscale_up:
            for name, p in self.peers.items():
                if name != "laptop":
                    p["status"] = "online"

        # File system
        self.fs = {
            "laptop": {
                "~/Documents/report.pdf":        {"size_mb": 2.4,    "type":"file"},
                "~/Documents/thesis.pdf":         {"size_mb": 45.0,   "type":"file"},
                "~/Videos/demo.mp4":              {"size_mb": 850.0,  "type":"file"},
                "~/backups/archive.tar.gz":       {"size_mb": 3200.0, "type":"file"},
                "~/testfile":                     {"size_mb": 1.0,    "type":"file"},
                "~/data/dataset.csv":             {"size_mb": 512.0,  "type":"file"},
                "~/projects/my-portfolio/":   {"size_mb": 0,      "type":"dir"},
                "~/.ssh/":                        {"size_mb": 0,      "type":"dir"},
            },
            "server": {
                "/home/user/backups/":     {"size_mb": 0, "type":"dir"},
                "/home/user/.ssh/":        {"size_mb": 0, "type":"dir"},
                "/var/www/html/":                 {"size_mb": 0, "type":"dir"},
                "/etc/nginx/":                    {"size_mb": 0, "type":"dir"},
                "/etc/nginx/sites-available/":    {"size_mb": 0, "type":"dir"},
                "/etc/nginx/sites-enabled/":      {"size_mb": 0, "type":"dir"},
                "/mnt/storage/":                  {"size_mb": 0, "type":"dir"},
                "/tmp/":                          {"size_mb": 0, "type":"dir"},
                "/var/log/nginx/access.log":      {"size_mb": 1.2, "type":"file"},
                "/var/log/nginx/error.log":       {"size_mb": 0.3, "type":"file"},
            },
        }

        # SSH
        self.ssh_key_exists  = w.get("ssh_key_exists", False)
        self.ssh_keys_copied = set(w.get("ssh_keys_copied", []))

        # Docker
        self.docker_images     = list(w.get("docker_images", []))
        self.docker_containers = dict(w.get("docker_containers", {}))
        self.docker_networks   = list(w.get("docker_networks", ["bridge","host","none"]))
        self.docker_volumes    = list(w.get("docker_volumes", []))

        # Nginx
        self.nginx_configs  = dict(w.get("nginx_configs", {}))
        self.nginx_running  = any(
            c.get("image","").startswith("nginx") and c.get("status") == "running"
            for c in self.docker_containers.values()
        )

        # Cybersec / recon
        self.known_hosts     = dict(w.get("known_hosts", {}))   # ip -> scan result
        self.captured_packets= list(w.get("captured_packets", []))
        self.active_captures = {}   # interface -> session

        # Per-mission command log (session-only, not serialized).
        # Records raw commands the player runs; mission step-checks use it to
        # verify the *right* command was actually typed. Reset on mission start.
        self.cmd_log = []

        # Current working directory for the local shell (persisted).
        self.cwd = w.get("cwd", "~")

        # Git repositories
        self.git_repos = dict(w.get("git_repos", {}))

        # Architecture / Infrastructure-as-Code (terraform) state
        self.tf_state = dict(w.get("tf_state", {
            "initialized": False,
            "planned":     False,
            "applied":     [],     # resource addresses currently provisioned
        }))

        # Red team engagement state
        self.rt_state = w.get("rt_state", {
            "phase":        "recon",
            "target":       None,
            "emails":       [],
            "subdomains":   [],
            "open_ports":   [],
            "exploited":    False,
            "shell_type":   None,
            "loot":         [],
            "listener_up":  False,
            "sessions":     {},
            "report_items": [],
        })

        # Blue-team / SOC engagement state (persisted progress).
        # The attacker IP is persisted so the host logs, SIEM alerts and the
        # IOCs/timeline the player records all stay consistent across sessions.
        self.attacker_ip = w.get("attacker_ip") or fake_ip("45.142")
        self.defense_state = dict(w.get("defense_state", {
            "incident_open":       False,   # an alert has been escalated
            "attacker_ip":         None,    # confirmed once the player investigates
            "alerts_investigated": [],      # SIEM alert ids opened
            "alerts_acked":        [],      # SIEM alert ids closed as benign
            "alerts_escalated":    [],      # SIEM alert ids raised to incident
            "iocs":                [],      # [{"type":..., "value":...}]
            "timeline":            [],      # ["HH:MM  event"] reconstructed by analyst
            "blocked_ips":         [],      # IPs contained at the firewall
            "report_done":         False,   # incident report generated
        }))

        # Simulated log sources + SIEM alert queue. Regenerated each session
        # from the (persisted) attacker IP — like listening_ports, these are
        # live views, not saved state. Player progress lives in defense_state.
        self.logs        = {}
        self.siem_alerts = []
        self._build_soc_environment(save_data)

        # Networking state
        self.local_interfaces = {
            "eth0":    {"ip":"192.168.1.42","mac":fake_mac(),"up":True},
            "wlan0":   {"ip":"192.168.1.43","mac":fake_mac(),"up":False},
            "tailscale0":{"ip":"100.64.1.10","mac":"N/A",   "up":self.tailscale_up},
            "lo":      {"ip":"127.0.0.1",   "mac":"00:00:00:00:00:00","up":True},
        }
        self.routing_table = [
            {"dest":"0.0.0.0/0",       "gw":"192.168.1.1",   "iface":"eth0"},
            {"dest":"192.168.1.0/24",  "gw":"0.0.0.0",       "iface":"eth0"},
            {"dest":"100.64.0.0/10",   "gw":"0.0.0.0",       "iface":"tailscale0"},
        ]
        self.listening_ports = [
            {"port":22,   "proto":"tcp","state":"LISTEN","pid":1234,"proc":"sshd"},
            {"port":80,   "proto":"tcp","state":"LISTEN","pid":5678,"proc":"nginx"},
            {"port":443,  "proto":"tcp","state":"LISTEN","pid":5678,"proc":"nginx"},
            {"port":8080, "proto":"tcp","state":"LISTEN","pid":9012,"proc":"node"},
        ]

    def to_dict(self):
        """Serialize world state back to save dict."""
        return {
            "tailscale_up":    self.tailscale_up,
            "ssh_key_exists":  self.ssh_key_exists,
            "ssh_keys_copied": list(self.ssh_keys_copied),
            "docker_images":   self.docker_images,
            "docker_containers": self.docker_containers,
            "docker_networks": self.docker_networks,
            "docker_volumes":  self.docker_volumes,
            "nginx_configs":   self.nginx_configs,
            "known_hosts":     self.known_hosts,
            "captured_packets":self.captured_packets,
            "git_repos":       self.git_repos,
            "rt_state":        self.rt_state,
            "tf_state":        self.tf_state,
            "attacker_ip":     self.attacker_ip,
            "defense_state":   self.defense_state,
            "cwd":             self.cwd,
        }

    # ── Blue-team / SOC environment ───────────────────────────────────────────

    def _build_soc_environment(self, save_data):
        """Populate self.logs and self.siem_alerts with a self-consistent
        intrusion story keyed off self.attacker_ip. Called once per session."""
        atk  = self.attacker_ip
        prof = save_data if isinstance(save_data, dict) else {}
        host = prof.get("hostname", "server")
        base = time.strftime("%b %d")
        usr  = BREACHED_USER

        def t(h, m, s=0):
            return f"{base} {h:02d}:{m:02d}:{s:02d}"

        # Each entry is (timestamp, priority, message). journalctl/grep print the
        # unit/identifier separately, so messages don't repeat it.
        # --- /var/log/auth.log (journalctl -u sshd) : the brute force + breach
        auth = []
        for i in range(8):
            who = random.choice(["admin", "root", "test", "oracle", "ubuntu", usr])
            auth.append((t(2, 11, 10 + i * 3), "info",
                         f"Failed password for "
                         f"{'invalid user ' if who not in ('root', usr) else ''}{who} "
                         f"from {atk} port {random.randint(40000, 60000)} ssh2"))
        auth.append((t(2, 12, 4), "notice",
                     f"Accepted password for {usr} from {atk} "
                     f"port {random.randint(40000, 60000)} ssh2"))
        auth.append((t(2, 12, 4), "info",
                     f"pam_unix(sshd:session): session opened for user {usr}(uid=1001)"))

        # --- sudo : privilege escalation right after the breach
        sudo = [
            (t(2, 13, 30), "notice",
             f"{usr} : TTY=pts/1 ; PWD=/home/{usr} ; USER=root ; COMMAND=/bin/bash"),
            (t(2, 13, 31), "info",
             f"pam_unix(sudo:session): session opened for user root by {usr}(uid=1001)"),
        ]

        # --- nginx access log : web path scanning from the same IP
        paths = ["/admin", "/.env", "/wp-login.php", "/phpmyadmin",
                 "/.git/config", "/api/v1/users", "/backup.zip"]
        nginx = [(t(2, 9, 50 + i), "info",
                  f'{atk} - - "GET {p} HTTP/1.1" {random.choice([404, 403, 404, 200])} '
                  f'{random.randint(150, 900)} "-" "Mozilla/5.0 (compatible; Nmap)"')
                 for i, p in enumerate(paths)]

        # --- a few benign lines so logs aren't 100% malicious
        kernel = [
            (t(0, 0, 1), "info", "Linux version 6.8.0-arch1-1 (SMP PREEMPT_DYNAMIC)"),
            (t(1, 30, 0), "info",
             f"[UFW BLOCK] IN=eth0 SRC={fake_ip()} DST=192.168.1.42 PROTO=TCP DPT=23"),
        ]
        cron = [
            (t(3, 0, 0), "info", "(root) CMD (/usr/local/bin/backup.sh)"),
            (t(3, 0, 5), "info", "nightly backup completed -> /mnt/storage"),
        ]

        self.logs = {
            "sshd":   auth,
            "sudo":   sudo,
            "nginx":  nginx,
            "kernel": kernel,
            "cron":   cron,
        }

        # --- SIEM alert queue (base status 'new'; player progress overlaid
        #     from defense_state at display time). Mix of true + benign so the
        #     job is real triage, not click-everything.
        self.siem_alerts = [
            {"id": 1, "severity": "CRITICAL",
             "rule": "SSH brute-force followed by successful login",
             "src": atk, "host": host, "time": t(2, 12, 4),
             "mitre": "T1110.001 Brute Force / T1078 Valid Accounts",
             "detail": f"~8 failed SSH logins from {atk} then an ACCEPTED password "
                       f"for '{usr}'. Classic password-guessing success.",
             "recommend": f"Confirm, record IOC {atk}, contain the host, reset '{usr}'."},
            {"id": 2, "severity": "HIGH",
             "rule": "Suspicious privilege escalation (sudo to root)",
             "src": "localhost", "host": host, "time": t(2, 13, 30),
             "mitre": "T1548.003 Sudo and Sudo Caching",
             "detail": f"'{usr}' (a low-priv service account) spawned /bin/bash as "
                       f"root within 90s of the SSH login. Likely hands-on-keyboard.",
             "recommend": "Treat as part of the same incident; review sudoers."},
            {"id": 3, "severity": "MEDIUM",
             "rule": "Web application path scanning",
             "src": atk, "host": host, "time": t(2, 9, 50),
             "mitre": "T1595.003 Wordlist Scanning",
             "detail": f"{atk} requested /admin, /.env, /wp-login.php, /.git/config "
                       f"with an Nmap user-agent. Recon prior to the SSH attack.",
             "recommend": "Correlate with alert #1 — same source IP."},
            {"id": 4, "severity": "LOW",
             "rule": "Outbound connection to uncommon ASN",
             "src": host, "host": host, "time": t(4, 2, 0),
             "mitre": "T1071 Application Layer Protocol",
             "detail": "Single short-lived HTTPS connection to a CDN edge node. "
                       "Matches a known software-update endpoint.",
             "recommend": "Likely benign — acknowledge after a quick check."},
            {"id": 5, "severity": "INFO",
             "rule": "Scheduled job executed",
             "src": host, "host": host, "time": t(3, 0, 0),
             "mitre": "N/A",
             "detail": "Nightly backup.sh ran from root cron, as configured.",
             "recommend": "Benign — acknowledge to clear the queue."},
        ]

    def alert_by_id(self, aid):
        try:
            aid = int(aid)
        except (TypeError, ValueError):
            return None
        return next((a for a in self.siem_alerts if a["id"] == aid), None)

    def alert_status(self, aid):
        """Effective status of an alert, overlaying player progress."""
        d = self.defense_state
        if aid in d.get("alerts_escalated", []):    return "ESCALATED"
        if aid in d.get("alerts_acked", []):        return "CLOSED"
        if aid in d.get("alerts_investigated", []): return "INVESTIGATING"
        return "NEW"

    def file_size(self, path):
        host_fs = self.fs.get("laptop", {})
        for k, v in host_fs.items():
            tail = k.lstrip("~/").lstrip("/")
            if path.endswith(tail) or path == k:
                return v.get("size_mb", 1.0)
        return 1.0

    # ── Local filesystem navigation (for cd / pwd / ls) ───────────────────────

    def _laptop_fs(self):
        return self.fs.get("laptop", {})

    def resolve_path(self, target, base=None):
        """Resolve `target` against `base` (defaults to cwd) into a normalized
        '~' or '/' path, collapsing '.' and '..'. No existence check."""
        cur = base if base is not None else self.cwd
        if target in ("", "~", "~/"):
            return "~"
        if target.startswith("~") or target.startswith("/"):
            combined = target
        elif cur in ("~", "~/"):
            combined = "~/" + target
        else:
            combined = cur.rstrip("/") + "/" + target

        lead = "~" if combined.startswith("~") else ""
        raw = combined[1:] if lead else combined
        stack = []
        for seg in raw.split("/"):
            if seg in ("", "."):
                continue
            if seg == "..":
                if stack:
                    stack.pop()
            else:
                stack.append(seg)
        if lead == "~":
            return "~" + ("/" + "/".join(stack) if stack else "")
        return "/" + "/".join(stack)

    def dir_exists(self, path):
        """True if the normalized `path` is a known directory on the laptop."""
        p = path.rstrip("/")
        if p in ("", "~"):
            return True
        keys = self._laptop_fs().keys()
        if (p + "/") in keys:          # explicit directory entry
            return True
        return any(k.startswith(p + "/") for k in keys)   # implied by children

    def children(self, path):
        """Immediate children under directory `path` → dict {name: is_dir}."""
        p = path.rstrip("/")
        prefix = "~/" if p in ("", "~") else p + "/"
        out = {}
        for k, v in self._laptop_fs().items():
            if not k.startswith(prefix):
                continue
            rest = k[len(prefix):].strip("/")
            if not rest:
                continue
            name = rest.split("/", 1)[0]
            is_dir = ("/" in rest) or (v.get("type") == "dir")
            out[name] = out.get(name, False) or is_dir
        return out

    def remote_host(self, target_str):
        """Extract hostname from user@host:path string."""
        if "@" not in target_str:
            return None
        part = target_str.split("@")[1]
        return part.split(":")[0]

    def peer_online(self, host):
        p = self.peers.get(host)
        return p is not None and p.get("status") == "online"

    def bring_tailscale_up(self):
        self.tailscale_up = True
        for name, p in self.peers.items():
            if name != "laptop":
                p["status"] = "online"
        self.local_interfaces["tailscale0"]["up"] = True

    def generate_scan(self, target_ip):
        """Generate a realistic nmap-style scan result."""
        n_open = random.randint(3, 8)
        port_pool = list(SERVICES.keys())
        open_ports = random.sample(port_pool, min(n_open, len(port_pool)))
        open_ports.sort()
        result = {
            "ip": target_ip,
            "hostname": f"host-{target_ip.split('.')[-1]}.local",
            "os": random.choice(["Linux 5.x", "Ubuntu 22.04", "Debian 12", "Windows Server 2022"]),
            "latency": round(random.uniform(0.5, 8.0), 2),
            "ports": [],
            "vulns": [],
            "scanned_at": int(time.time()),
        }
        for p in open_ports:
            svc, banner = SERVICES.get(p, ("unknown", ""))
            result["ports"].append({
                "port": p, "proto":"tcp", "state":"open",
                "service": svc, "banner": banner
            })
            if p in VULN_DB:
                vulns = VULN_DB[p]
                if isinstance(vulns, list):
                    for v in vulns:
                        result["vulns"].append({"port":p,"severity":v[0],"desc":v[1],"cve":v[2]})
                else:
                    result["vulns"].append({"port":p,"severity":vulns[0],"desc":vulns[1],"cve":vulns[2]})
        self.known_hosts[target_ip] = result
        return result
