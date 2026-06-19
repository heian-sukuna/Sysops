"""
modules/cybersec.py — Cybersecurity tools (all simulated)
nmap, tshark/wireshark, gobuster, nikto, hydra, hashcat, john, netcat,
openssl, fail2ban, ufw, lynis, shodan-style recon
"""

import time, random, hashlib
from core.ui import *
from core.world import SERVICES, VULN_DB, fake_mac, fake_ip, fake_cve

SEVERITY_COLOR = {
    "CRITICAL": f"{BG_RED}{B}{BWHITE}",
    "HIGH":     f"{BRED}{B}",
    "MEDIUM":   f"{BYELLOW}{B}",
    "LOW":      f"{BBLUE}",
    "INFO":     f"{DIM}",
}

def sev(s):
    col = SEVERITY_COLOR.get(s, "")
    return f"{col} {s:<8} {R}"

class CyberSecModule:
    def __init__(self, world, save):
        self.w = world
        self.s = save

    # ─── NMAP ────────────────────────────────────────────────────────────────

    def nmap(self, args):
        if not args:
            self._nmap_help(); return

        # Parse nmap flags
        target    = None
        syn_scan  = "-sS" in args or "-sT" in args
        udp_scan  = "-sU" in args
        os_detect = "-O"  in args
        svc_ver   = "-sV" in args
        aggressive= "-A"  in args
        vuln_scan = "--script" in args and any("vuln" in a for a in args)
        script    = None
        ports     = None
        timing    = 3
        output    = None

        i = 0
        while i < len(args):
            a = args[i]
            if a.startswith("-"):
                if a.startswith("-T") and len(a) > 2:
                    try: timing = int(a[2])
                    except: pass
                elif a == "-p" and i+1 < len(args):
                    ports = args[i+1]; i+=1
                elif a == "--script" and i+1 < len(args):
                    script = args[i+1]; i+=1
                elif a in ("-oN","-oX","-oG") and i+1 < len(args):
                    output = args[i+1]; i+=1
            elif not a.startswith("-"):
                target = a
            i += 1

        if not target:
            print(warn("  nmap needs a target: nmap [flags] <host/IP/range>")); return

        # Resolve target
        peer = self.w.peers.get(target)
        if peer:
            target_ip = peer["ts_ip"]
        elif target.endswith("/24"):
            # subnet scan
            self._subnet_scan(target, timing); return
        else:
            target_ip = target

        scan_label = "SYN Stealth" if syn_scan else ("UDP" if udp_scan else "Connect")
        if aggressive: scan_label = "Aggressive (-A)"

        print(f"\n  {BRED}Starting Nmap 7.95 {R}{dim('( https://nmap.org )')}")
        print(f"  {dim('Scan report for')} {cyan(target)} {dim('('+target_ip+')')}")
        print(f"  Scan type: {info(scan_label)}")
        if timing:
            print(f"  Timing: {dim('T'+str(timing))} ({'insane' if timing>=5 else 'aggressive' if timing>=4 else 'normal'})")
        print()

        spinner(f"Scanning {target_ip}", 0.4 + (0.6 / max(timing, 1)))

        result = self.w.generate_scan(target_ip)

        print(f"  Host is {ok('up')} (latency {result['latency']}ms)")
        print(f"  rDNS record: {result['hostname']}")
        print()
        print(f"  {'PORT':<10} {'STATE':<10} {'SERVICE':<14} {'VERSION'}")
        print(dim("  " + "─" * 65))

        for p in result["ports"]:
            port_str = f"{p['port']}/tcp"
            print(f"  {cyan(port_str):<18} {ok(p['state']):<17} {p['service']:<14} {dim(p['banner'])}")

        if os_detect or aggressive:
            print(f"\n  OS detection:")
            print(f"  {dim('Running:')} {ok(result['os'])}")
            print(f"  {dim('Aggressive OS guesses:')} {result['os']} (97%), Linux 4.x (90%)")

        if svc_ver or aggressive:
            print(f"\n  Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel")

        if vuln_scan or (script and "vuln" in script):
            print(f"\n  {BRED}Vulnerability scan results:{R}")
            if result["vulns"]:
                for v in result["vulns"]:
                    print(f"    {sev(v['severity'])} Port {v['port']}/{dim(next((p['service'] for p in result['ports'] if p['port']==v['port']),'?'))}")
                    print(f"           {v['desc']}")
                    if v['cve'] != "N/A":
                        print(f"           {dim('CVE:')} {warn(v['cve'])}")
            else:
                print(f"    {ok('No critical vulnerabilities found')}")

        if script and script != "vuln":
            print(f"\n  NSE script: {script}")
            if "http" in script:
                print(f"    |_ http-title: Welcome to nginx!")
                print(f"    |_ http-server-header: nginx/1.25.3")
            elif "ssh" in script:
                print(f"    |_ ssh-hostkey:")
                print(f"       3072 {fake_mac().replace(':','')} (RSA)")
                print(f"       256  {fake_mac().replace(':','')[:32]} (ED25519)")
            elif "smb" in script:
                print(f"    |_ smb-security-mode: guest account disabled")
                print(f"    |_ smb-vuln-ms17-010: {BRED}VULNERABLE{R}")

        if output:
            print(f"\n  {ok(f'✓ Output saved to: {output}')}")

        print(f"\n  Nmap done: 1 IP address (1 host up) scanned in {random.uniform(3,12):.2f} seconds")

        # Record findings
        self.w.known_hosts[target_ip] = result
        xp = 20 if result["vulns"] else 12
        if aggressive: xp += 10
        lvl = self.s.add_xp(xp, "nmap scan"); xp_flash(xp, "nmap scan")

        if result["vulns"]:
            crits = [v for v in result["vulns"] if v["severity"] == "CRITICAL"]
            if crits and self.s.grant_achievement("vuln_hunter","Found a CRITICAL vulnerability with nmap"):
                print(f"  {BYELLOW}{B}🏆 Achievement: Vulnerability Hunter!{R}")

    def _subnet_scan(self, subnet, timing):
        print(f"\n  {BRED}Starting Nmap 7.95{R} — subnet scan")
        print(f"  Target: {cyan(subnet)}")
        print()
        spinner("Performing host discovery", 1.8)

        n_hosts = random.randint(4, 8)
        prefix  = subnet.split("/")[0].rsplit(".",1)[0]
        hosts   = []

        print(f"  Hosts up ({n_hosts} discovered):\n")
        for _ in range(n_hosts):
            ip = prefix + "." + str(random.randint(2, 254))
            hostname = f"host-{ip.split('.')[-1]}.local"
            n_ports  = random.randint(2, 5)
            print(f"  {ok('●')} {cyan(ip):<20} {dim(hostname)}")
            port_sample = random.sample(list(SERVICES.keys()), n_ports)
            for p in sorted(port_sample):
                svc, _ = SERVICES[p]
                print(f"      {p}/tcp  {ok('open')}  {svc}")
            hosts.append(ip)
            pause(0.12)

        print(f"\n  Nmap done: {n_hosts} hosts up, scanned in {random.uniform(8,20):.2f}s")
        for ip in hosts:
            self.w.generate_scan(ip)
        self.s.add_xp(25,"subnet scan"); xp_flash(25,"subnet scan")

    def _nmap_help(self):
        lines = [
            f"  {bold('nmap [flags] <target>')}",
            "",
            f"  {cyan('Scan types:')}",
            f"    {ok('-sS')}        SYN stealth scan (requires root)",
            f"    {ok('-sT')}        TCP connect scan",
            f"    {ok('-sU')}        UDP scan",
            f"    {ok('-A')}         aggressive: OS + services + scripts + traceroute",
            "",
            f"  {cyan('Discovery:')}",
            f"    {ok('-p 80,443')}  specific ports",
            f"    {ok('-p-')}        all 65535 ports",
            f"    {ok('-p 1-1000')}  port range",
            f"    {ok('-sV')}        service version detection",
            f"    {ok('-O')}         OS detection",
            "",
            f"  {cyan('Scripts (NSE):')}",
            f"    {ok('--script vuln')}      run all vuln detection scripts",
            f"    {ok('--script http-enum')} enumerate HTTP paths",
            f"    {ok('--script smb-vuln-ms17-010')} EternalBlue check",
            f"    {ok('--script ssh-hostkey')} get SSH fingerprint",
            "",
            f"  {cyan('Timing:')}",
            f"    {ok('-T0')} paranoid  {ok('-T3')} normal  {ok('-T5')} insane",
            "",
            f"  {cyan('Output:')}",
            f"    {ok('-oN file.txt')}  normal output",
            f"    {ok('-oX file.xml')}  XML output",
            "",
            f"  {cyan('Examples:')}",
            f"    nmap -sV -O server",
            f"    nmap -A --script vuln 100.64.1.20",
            f"    nmap -sS -p 80,443,22 192.168.1.0/24",
        ]
        box("nmap — Network Scanner Reference", lines, border_color=BRED)

    # ─── TSHARK / WIRESHARK ──────────────────────────────────────────────────

    def tshark(self, args):
        self._capture(args, tool="tshark")

    def wireshark(self, args):
        print(info("  Wireshark is a GUI tool — using tshark (CLI equivalent)"))
        print(dim("  In a real system: wireshark opens a GUI. Use tshark for terminal."))
        print()
        self._capture(args, tool="wireshark")

    def _capture(self, args, tool="tshark"):
        iface   = "eth0"
        count   = 10
        filter_ = None
        write   = None
        read    = None

        i = 0
        while i < len(args):
            a = args[i]
            if a == "-i" and i+1 < len(args):   iface  = args[i+1]; i+=1
            elif a == "-c" and i+1 < len(args):  count  = int(args[i+1]); i+=1
            elif a in ("-f","-Y") and i+1 < len(args): filter_ = args[i+1]; i+=1
            elif a == "-w" and i+1 < len(args):  write  = args[i+1]; i+=1
            elif a == "-r" and i+1 < len(args):  read   = args[i+1]; i+=1
            i += 1

        if read:
            self._read_capture(read); return

        print(f"\n  {info('Capturing on')} {cyan(iface)}")
        if filter_:
            print(f"  Filter: {warn(filter_)}")
        print(f"  Count: {count} packets")
        print(dim("  Ctrl+C to stop\n"))

        protos  = ["TCP","UDP","ICMP","DNS","HTTP","TLS","ARP"]
        ips     = [fake_ip() for _ in range(5)]
        my_ip   = self.w.local_interfaces.get(iface,{}).get("ip","192.168.1.42")
        packets = []

        try:
            for n in range(1, count+1):
                src = random.choice(ips + [my_ip])
                dst = random.choice(ips + [my_ip])
                proto = random.choice(protos)
                sport = random.randint(1024, 65535)
                dport = random.choice([22,80,443,53,8080,3306])
                ln    = random.randint(60, 1500)

                if filter_:
                    if "tcp" in filter_.lower() and proto not in ("TCP","HTTP","TLS"): continue
                    if "udp" in filter_.lower() and proto != "UDP": continue
                    if "dns" in filter_.lower() and proto != "DNS": continue
                    if "http" in filter_.lower() and proto not in ("HTTP","TLS"): continue

                flags_str = ""
                info_str  = ""
                if proto == "TCP":
                    flags_str = random.choice(["[SYN]","[ACK]","[SYN, ACK]","[PSH, ACK]","[FIN, ACK]"])
                    info_str  = f"{sport} → {dport} {flags_str} Seq=0 Win=65535"
                elif proto == "HTTP":
                    method = random.choice(["GET","POST","PUT"])
                    info_str = f"{method} / HTTP/1.1"
                    dport = 80
                elif proto == "TLS":
                    info_str = random.choice(["Client Hello","Server Hello","Application Data"])
                    dport = 443
                elif proto == "DNS":
                    domain = random.choice(["google.com","tailscale.com","example.com"])
                    info_str = f"Standard query A {domain}"
                    dport = 53
                elif proto == "ARP":
                    info_str = f"Who has {dst}? Tell {src}"
                elif proto == "ICMP":
                    info_str = "Echo (ping) request"

                ts = f"  {n:>4}  {time.strftime('%H:%M:%S')}.{random.randint(0,999999):06d}"
                col = BCYAN if proto in ("HTTP","TLS") else (BGREEN if proto=="DNS" else (BYELLOW if proto=="ARP" else ""))
                line = f"{dim(ts)}  {src:<16}  {dst:<16}  {col}{proto:<6}{R}  {ln:>5}  {dim(info_str)}"
                print(line)
                packets.append({"n":n,"src":src,"dst":dst,"proto":proto,"len":ln,"info":info_str})
                pause(0.08)

        except KeyboardInterrupt:
            print(dim("\n  Capture stopped."))

        print(f"\n  {len(packets)} packets captured")

        if write:
            self.w.captured_packets.extend(packets)
            print(ok(f"  ✓ Saved to {write} ({len(packets)} packets)"))

        self.s.add_xp(18,"tshark capture"); xp_flash(18,"tshark capture")
        if self.s.grant_achievement("packet_hunter","Captured network traffic with tshark"):
            print(f"  {BYELLOW}{B}🏆 Achievement: Packet Hunter!{R}")

    def _read_capture(self, fname):
        packets = self.w.captured_packets or []
        if not packets:
            print(warn(f"  No capture data found for {fname}"))
            print(dim("  Tip: run tshark -i eth0 -c 20 -w capture.pcap first"))
            return
        print(info(f"\n  Reading from {fname} ({len(packets)} packets)\n"))
        for p in packets[:20]:
            col = BCYAN if p["proto"] in ("HTTP","TLS") else ""
            print(f"  {p['n']:>4}  {p['src']:<16}  {p['dst']:<16}  {col}{p['proto']:<6}{R}  {dim(p['info'])}")

    # ─── GOBUSTER / DIRB ─────────────────────────────────────────────────────

    def gobuster(self, args):
        if not args:
            print(warn("  Usage: gobuster dir -u <url> -w <wordlist>")); return

        url = None
        wordlist = "/usr/share/wordlists/dirb/common.txt"
        for i, a in enumerate(args):
            if a in ("-u","--url") and i+1<len(args):     url = args[i+1]
            elif a in ("-w","--wordlist") and i+1<len(args): wordlist = args[i+1]

        if not url:
            print(warn("  -u <url> required")); return

        print(f"\n  {BRED}Gobuster{R} v3.6")
        print(f"  Target: {cyan(url)}")
        print(f"  Wordlist: {dim(wordlist)}")
        print()
        spinner("Initializing", 0.5)

        paths = [
            ("/admin",        200, "5.2KB"),
            ("/login",        200, "3.1KB"),
            ("/api",          200, "0.8KB"),
            ("/static",       301, "0.2KB"),
            ("/dashboard",    302, "0.1KB"),
            ("/backup",       403, "0.3KB"),
            ("/wp-admin",     404, "1.2KB"),
            ("/.git",         403, "0.1KB"),
            ("/config",       403, "0.2KB"),
            ("/upload",       200, "2.8KB"),
            ("/api/v1/users", 200, "4.5KB"),
            ("/.env",         200, "0.5KB"),  # intentionally alarming
        ]

        found = []
        for path, code, size in paths:
            pause(0.07)
            if code == 200:
                col = ok(f"/{path.lstrip('/')}")
                status_col = ok(str(code))
            elif code in (301,302):
                col = warn(f"/{path.lstrip('/')}")
                status_col = warn(str(code))
            else:
                col = dim(f"/{path.lstrip('/')}")
                status_col = dim(str(code))

            print(f"  {status_col}  {size:>8}  {url}{path}")
            if code == 200:
                found.append(path)

        print(f"\n  Done. {len(found)} results found.")
        if "/.env" in found:
            print(warn(f"\n  ⚠ /.env exposed! This file often contains API keys and secrets."))
            print(dim("  In production: add 'deny all;' for /.env in nginx config."))
        self.s.add_xp(16,"gobuster"); xp_flash(16,"gobuster")

    def dirb(self, args):
        url = args[0] if args else "http://localhost"
        print(info(f"\n  DIRB v2.22 — {url}"))
        spinner("Scanning directories", 1.5)
        self.gobuster(["-u", url, "-w", "common.txt"])

    # ─── NIKTO ───────────────────────────────────────────────────────────────

    def nikto(self, args):
        host = None
        for i, a in enumerate(args):
            if a in ("-h","--host") and i+1<len(args): host = args[i+1]
            elif not a.startswith("-"): host = a

        if not host:
            print(warn("  Usage: nikto -h <host>")); return

        print(f"\n  {BRED}Nikto{R} v2.1.6")
        print(f"  Target: {cyan(host)}")
        print(f"  Start time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(dim("  " + "─" * 60))
        spinner("Running web server scan", 2.0)

        findings = [
            ("INFO",     "Server: nginx/1.25.3"),
            ("MEDIUM",   "Missing X-Content-Type-Options header"),
            ("MEDIUM",   "Missing X-Frame-Options header"),
            ("LOW",      "Cookie without HttpOnly flag"),
            ("HIGH",     "/.git directory accessible — source code exposure risk"),
            ("MEDIUM",   "Directory indexing enabled at /static/"),
            ("INFO",     "PHP version disclosure in error pages"),
            ("HIGH",     "/admin/ accessible without authentication"),
            ("LOW",      "ETag header leaks inode information (CVE-2003-1418)"),
            ("MEDIUM",   "OPTIONS method enabled — TRACE method may be available"),
        ]

        for sev_str, finding in findings:
            col = SEVERITY_COLOR.get(sev_str, "")
            print(f"  + {col}{sev_str:<8}{R}  {finding}")
            pause(0.12)

        print(dim(f"\n  Scan complete. {len(findings)} items found."))
        print(dim(f"  End time: {time.strftime('%Y-%m-%d %H:%M:%S')}"))
        self.s.add_xp(18,"nikto"); xp_flash(18,"nikto")

    # ─── HYDRA ───────────────────────────────────────────────────────────────

    def hydra(self, args):
        target, service, user, wordlist = None, "ssh", None, None
        for i, a in enumerate(args):
            if a == "-l" and i+1<len(args):  user     = args[i+1]
            elif a == "-P" and i+1<len(args): wordlist = args[i+1]
            elif a == "-s" and i+1<len(args): pass
            elif not a.startswith("-"):
                if not target: target = a
                elif not service: service = a

        if not target:
            print(warn("  Usage: hydra -l <user> -P <wordlist> <host> <service>")); return

        print(f"\n  {BRED}Hydra{R} v9.5 — {warn('(Educational simulation)')}")
        print(f"  Target  : {cyan(target)}")
        print(f"  Service : {service}")
        print(f"  User    : {user or 'from list'}")
        print(f"  Wordlist: {wordlist or 'default'}")
        print(warn("\n  ⚠ Only run Hydra against systems you own or have explicit permission to test."))
        print()
        spinner("Starting brute-force simulation", 1.2)

        attempts = random.randint(45, 120)
        for i in range(min(8, attempts)):
            pwd = random.choice(["password","123456","admin","letmein","qwerty","root"])
            pause(0.1)
            print(f"  [{time.strftime('%H:%M:%S')}] {dim(f'attempt {i+1}:')} {user}:{pwd} — {err('FAILED')} ")

        # Random success
        if random.random() > 0.3:
            win_pwd = random.choice(["password123","admin2024","welcome1"])
            print(f"  [{time.strftime('%H:%M:%S')}] {ok('SUCCESS:')} {user}:{win_pwd}")
            print(ok(f"\n  [DATA] host: {target}   login: {user}   password: {win_pwd}"))
        else:
            print(warn(f"\n  0 valid credentials found after {attempts} attempts"))
            print(dim("  Target may have rate limiting or account lockout enabled."))

        self.s.add_xp(14,"hydra"); xp_flash(14,"hydra")

    # ─── HASHCAT / JOHN ──────────────────────────────────────────────────────

    def hashcat(self, args):
        hash_file = args[0] if args else "hashes.txt"
        mode = "0"
        wordlist = "rockyou.txt"
        for i, a in enumerate(args):
            if a == "-m" and i+1<len(args): mode = args[i+1]
            elif a == "-a" and i+1<len(args): pass
            elif not a.startswith("-"):
                if a != hash_file: wordlist = a

        mode_names = {"0":"MD5","100":"SHA1","1000":"NTLM","1800":"sha512crypt","3200":"bcrypt"}
        mode_name  = mode_names.get(mode, f"mode {mode}")

        print(f"\n  {BRED}hashcat{R} v6.2.6")
        print(f"  Hash type : {mode_name}")
        print(f"  Wordlist  : {wordlist}")
        print()
        spinner("Initializing GPU attack", 1.0)

        hashes = [
            f"{random.randint(10**31, 10**32-1):x}" for _ in range(3)
        ]
        cracked = []

        print(f"  {'HASH':<35} STATUS")
        print(dim("  " + "─" * 50))
        for h in hashes:
            pause(0.3)
            if random.random() > 0.4:
                pwd = random.choice(["monkey","iloveyou","sunshine","football","abc123"])
                print(f"  {dim(h[:32]+'...'):<35} {ok('Cracked:')} {warn(pwd)}")
                cracked.append((h,pwd))
            else:
                print(f"  {dim(h[:32]+'...'):<35} {dim('Not found')}")

        print(f"\n  Session complete. {len(cracked)}/{len(hashes)} hashes cracked.")
        if cracked:
            print(warn("  ⚠ Weak passwords detected — recommend bcrypt with cost ≥12"))
        self.s.add_xp(16,"hashcat"); xp_flash(16,"hashcat")

    def john(self, args):
        wordlist = "--wordlist=/usr/share/wordlists/rockyou.txt"
        hashfile = args[-1] if args else "shadow.txt"
        print(f"\n  {BRED}John the Ripper{R} 1.9.0-jumbo")
        print(f"  Target: {hashfile}")
        spinner("Loading wordlist & running rules", 1.5)
        cracked = random.randint(0, 5)
        print(ok(f"  {cracked} password hashes cracked, {random.randint(2,8) - cracked} left"))
        if cracked:
            print(f"  {warn('admin')}         ({dim('hash:1')})")
        self.s.add_xp(12,"john"); xp_flash(12,"john")

    # ─── NETCAT ──────────────────────────────────────────────────────────────

    def nc(self, args):
        listen  = "-l" in args or "-lv" in args
        verbose = "-v" in args or "-lv" in args
        port    = None
        host    = None

        for i, a in enumerate(args):
            if a == "-p" and i+1<len(args):
                try: port = int(args[i+1])
                except: pass
            elif not a.startswith("-"):
                if host is None and not listen: host = a
                elif port is None:
                    try: port = int(a)
                    except: pass

        if listen:
            port = port or 4444
            print(info(f"  Listening on 0.0.0.0:{port}"))
            if verbose:
                print(dim("  Ncat: Version 7.95 — listening"))
            pause(0.5)
            peer_ip = fake_ip()
            print(ok(f"  Connection from {peer_ip}:{random.randint(40000,60000)}"))
            print(dim("  (simulated shell — type 'exit' to close)"))
            try:
                while True:
                    inp = input("  > ")
                    if inp == "exit": break
                    print(f"  {dim('[remote]')} {inp}")
            except (EOFError, KeyboardInterrupt):
                pass
            print(dim("  Connection closed."))
        else:
            host = host or "localhost"
            port = port or 80
            spinner(f"Connecting to {host}:{port}", 0.7)
            print(ok(f"  Connected to {host} port {port} [tcp/*] succeeded!"))
            print(dim("  (type to send, Ctrl+C to close)"))
            try:
                while True:
                    inp = input("  > ")
                    if inp == "exit": break
                    print(dim(f"  [sent {len(inp)} bytes]"))
            except (EOFError, KeyboardInterrupt):
                pass

    # ─── OPENSSL ─────────────────────────────────────────────────────────────

    def openssl(self, args):
        if not args:
            print(warn("  Usage: openssl <command> [options]")); return
        sub = args[0]

        if sub == "s_client":
            host_port = next((a for a in args if ":" in a and not a.startswith("-")), "localhost:443")
            h, p = host_port.split(":") if ":" in host_port else (host_port, "443")
            spinner(f"TLS handshake with {h}:{p}", 1.0)
            print(f"  CONNECTED({h}:{p})")
            print(f"  SSL-Session: Protocol: TLSv1.3  Cipher: TLS_AES_256_GCM_SHA384")
            print(f"  Server certificate: CN={h}, O=Example Ltd, C=US")
            print(f"  Verify return code: 0 (ok)")

        elif sub == "genrsa":
            bits = args[-1] if args[-1].isdigit() else "2048"
            spinner(f"Generating {bits}-bit RSA key", 0.8)
            print(ok(f"  ✓ Private key generated ({bits} bits)"))

        elif sub == "req":
            print(ok("  ✓ Certificate signing request (CSR) generated"))

        elif sub in ("enc","rand","dgst"):
            print(ok(f"  ✓ openssl {sub} completed"))

        else:
            print(dim(f"  openssl {sub} — simulated"))

    # ─── UFW / FIREWALL ──────────────────────────────────────────────────────

    def ufw(self, args):
        sub = args[0] if args else "status"

        if sub == "status":
            print(info("\n  Status: active\n"))
            print(f"  {'To':<22} {'Action':<10} From")
            print(dim("  " + "─" * 44))
            rules = [("22/tcp","ALLOW","Anywhere"),("80/tcp","ALLOW","Anywhere"),
                     ("443/tcp","ALLOW","Anywhere"),("22/tcp (v6)","ALLOW","Anywhere (v6)")]
            for r in rules:
                col = ok(r[1]) if r[1]=="ALLOW" else err(r[1])
                print(f"  {r[0]:<22} {col:<19} {r[2]}")
            print()

        elif sub == "allow":
            port = args[1] if len(args)>1 else "?"
            print(ok(f"  ✓ Rule added: allow {port}"))

        elif sub == "deny":
            port = args[1] if len(args)>1 else "?"
            print(ok(f"  ✓ Rule added: deny {port}"))

        elif sub in ("enable","disable"):
            print(ok(f"  ✓ Firewall {sub}d"))

        elif sub == "reload":
            print(ok("  ✓ Firewall rules reloaded"))

        else:
            print(warn(f"  Unknown: ufw {sub}"))

    # ─── FAIL2BAN ────────────────────────────────────────────────────────────

    def fail2ban(self, args):
        sub = " ".join(args[:2]) if args else "client status"

        if "status" in sub:
            jail = args[-1] if args and args[-1] not in ("status","client") else "sshd"
            print(info(f"\n  Status for jail: {jail}"))
            print(f"  Filter: {dim('File: /etc/fail2ban/filter.d/'+jail+'.conf')}")
            print(f"  Actions: iptables-multiport")
            print(f"  Currently failed: {random.randint(0,5)}")
            print(f"  Total failed    : {random.randint(40,200)}")
            bans = random.randint(0,3)
            print(f"  Currently banned: {bans}")
            if bans:
                for _ in range(bans):
                    print(f"    Banned IP: {fake_ip()}")
            print()

        elif "ban" in sub:
            ip = args[-1]
            print(ok(f"  ✓ {ip} banned in jail sshd"))

        elif "unban" in sub:
            ip = args[-1]
            print(ok(f"  ✓ {ip} unbanned"))

    # ─── LYNIS ───────────────────────────────────────────────────────────────

    def lynis(self, args):
        print(f"\n  {BRED}Lynis{R} 3.0.9 — Security Auditing Tool")
        print(dim("  System audit — this may take a moment"))
        print()
        categories = [
            ("Bootloader",       3, 3, []),
            ("Filesystems",      8, 6, ["Separate /tmp partition not found"]),
            ("SSH",              12, 10, ["SSH PermitRootLogin is enabled"]),
            ("Firewall",         6, 5, ["UFW: some rules could be tightened"]),
            ("Authentication",   9, 7, ["Password policy not enforced"]),
            ("Kernel hardening", 15, 9, ["ASLR enabled","SYN cookies not configured"]),
            ("Networking",       8, 7, []),
            ("Services",         11, 9, ["NFS daemon active but not needed"]),
        ]
        total_ok = total_warn = 0
        for cat, tests, ok_n, warns in categories:
            warn_n = tests - ok_n
            total_ok += ok_n; total_warn += warn_n
            bar = f"{BGREEN}{'▪'*ok_n}{R}{BYELLOW}{'▪'*warn_n}{R}"
            print(f"  {cat:<22} [{bar}{' '*(15-tests)}] {ok_n}/{tests}")
            for w in warns:
                print(f"    {warn('⚠')} {dim(w)}")
            pause(0.1)

        score = int((total_ok/(total_ok+total_warn))*100)
        score_col = ok(str(score)) if score >= 75 else warn(str(score))
        print(f"\n  Hardening index : {score_col}/100")
        print(f"  Tests performed : {total_ok+total_warn}")
        print(f"  Warnings        : {BYELLOW}{total_warn}{R}")
        print(dim("\n  Full report: /var/log/lynis.log"))
        self.s.add_xp(22,"lynis audit"); xp_flash(22,"lynis audit")

    # ─── SHODAN RECON ────────────────────────────────────────────────────────

    def shodan(self, args):
        sub = args[0] if args else "help"

        if sub == "host":
            ip = args[1] if len(args)>1 else fake_ip()
            print(f"\n  {info('Shodan host report')} — {cyan(ip)}")
            print(f"  Hostnames  : host-{ip.split('.')[-1]}.isp.example.com")
            print(f"  Country    : Kenya (KE)")
            print(f"  ISP        : Example ISP Ltd")
            print(f"  ASN        : AS12345")
            print(f"\n  Open ports:")
            for p in random.sample(list(SERVICES.keys()), 4):
                svc, banner = SERVICES[p]
                print(f"    {cyan(str(p)):<8} {svc:<12} {dim(banner)}")
            vulns = random.randint(0,3)
            if vulns:
                print(f"\n  {warn(f'Vulnerabilities: {vulns}')}")
                for _ in range(vulns):
                    print(f"    {err(fake_cve())}")
            self.s.add_xp(10,"shodan host"); xp_flash(10,"shodan recon")

        elif sub == "search":
            query = " ".join(args[1:]) if len(args)>1 else "nginx"
            print(info(f"\n  Shodan search: {query}"))
            print(f"  Total results: {random.randint(1000,50000)}")
            print(f"\n  Top results:")
            for _ in range(5):
                ip = fake_ip()
                port = random.choice([80,443,8080,22])
                print(f"    {ip:<18} :{port}  {dim(random.choice(['nginx','apache','OpenSSH']))}")
            self.s.add_xp(8,"shodan search"); xp_flash(8,"shodan search")

        else:
            print(warn("  Usage: shodan host <ip> | shodan search <query>"))
