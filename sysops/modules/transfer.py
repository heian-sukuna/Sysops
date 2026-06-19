"""
modules/transfer.py — rsync, ssh, ssh-keygen, ssh-copy-id, tailscale
"""

import time, random, shlex
from core.ui import *
from core.world import SERVICES, VULN_DB

class TransferModule:
    def __init__(self, world, save):
        self.w = world
        self.s = save

    # ─── TAILSCALE ────────────────────────────────────────────────────────────

    def tailscale(self, args):
        if not args:
            self._ts_help(); return
        sub = args[0].lower()

        if sub == "up":
            if self.w.tailscale_up:
                print(info("  Tailscale is already running.")); return
            spinner("Connecting to Tailscale control plane", 1.4)
            self.w.bring_tailscale_up()
            print(ok(f"  ✓ Connected to Tailscale — tailnet: {cyan(self.w.tailnet_name)}"))
            print(dim(f"  Your IP: {self.w.peers['laptop']['ts_ip']}"))
            lvl = self.s.add_xp(10, "tailscale up"); self._xp(10, "tailscale up", lvl)

        elif sub == "down":
            self.w.tailscale_up = False
            for p in self.w.peers.values():
                if p != self.w.peers["laptop"]:
                    p["status"] = "offline"
            self.w.local_interfaces["tailscale0"]["up"] = False
            print(ok("  Tailscale stopped."))

        elif sub == "status":
            if not self.w.tailscale_up:
                print(warn("  Tailscale stopped. Run: tailscale up")); return
            print()
            header = f"  {'NAME':<14} {'IP':<16} {'STATUS':<10} {'OS':<18} CONNECTION"
            print(info(header))
            print(dim("  " + "─" * 68))
            me = self.w.peers["laptop"]
            print(f"  {cyan('laptop (you)'):<23} {me['ts_ip']:<16} {ok('online'):<19} {dim(me['os']):<18} —")
            for name, p in self.w.peers.items():
                if name == "laptop": continue
                conn  = warn("relay/DERP") if p["relay"] else ok("direct")
                stat  = ok(p["status"]) if p["status"]=="online" else err(p["status"])
                print(f"  {name:<14} {p['ts_ip']:<16} {stat:<19} {dim(p['os']):<18} {conn}")
            print()
            relay_peers = [n for n,p in self.w.peers.items() if p.get("relay")]
            if relay_peers:
                print(warn(f"  ⚠ Relay path detected for: {', '.join(relay_peers)}"))
                print(dim("  Tip: direct connections are faster — check firewall UDP 41641"))
            self.s.add_xp(3, "tailscale status")

        elif sub == "ping":
            host = args[1] if len(args) > 1 else None
            if not host:
                print(warn("  Usage: tailscale ping <host>")); return
            if not self.w.tailscale_up:
                print(err("  Tailscale not running. Run: tailscale up")); return
            peer = self.w.peers.get(host)
            if not peer:
                print(err(f"  Unknown host: {host}")); return
            spinner(f"Pinging {host}", 0.6)
            if peer["relay"]:
                print(warn(f"  pong from {host} ({peer['ts_ip']}): via DERP relay  38ms"))
                print(dim("  Note: relay path active — direct path not established"))
            else:
                ms = round(random.uniform(2.1, 6.8), 2)
                print(ok(f"  pong from {host} ({peer['ts_ip']}): direct  {ms}ms"))
            lvl = self.s.add_xp(5, "tailscale ping"); self._xp(5, "tailscale ping", lvl)

        elif sub == "ip":
            if not self.w.tailscale_up:
                print(err("  Tailscale not running.")); return
            print(info(f"  {self.w.peers['laptop']['ts_ip']}"))

        elif sub == "netcheck":
            spinner("Running network quality check", 1.8)
            print(info("\n  Tailscale netcheck report:"))
            print(f"    UDP         : {ok('reachable')}")
            print(f"    IPv4        : {ok('reachable (100.64.1.10)')}")
            print(f"    IPv6        : {warn('not available')}")
            print(f"    DERP latency: {dim('fra=12ms  lon=18ms  sin=45ms')}")
            print(f"    Direct IPs  : {ok('3 peers have direct connections')}")

        elif sub == "logout":
            self.w.tailscale_up = False
            print(ok("  Logged out of Tailscale."))

        else:
            print(err(f"  Unknown subcommand: tailscale {sub}"))
            self._ts_help()

    def _ts_help(self):
        lines = [
            f"  {cyan('tailscale up')}          connect to tailnet",
            f"  {cyan('tailscale down')}        disconnect",
            f"  {cyan('tailscale status')}      show peers, IPs, connection type",
            f"  {cyan('tailscale ping <host>')} test latency (direct vs relay)",
            f"  {cyan('tailscale ip')}          show your Tailscale IP",
            f"  {cyan('tailscale netcheck')}    run connectivity diagnostics",
            f"  {cyan('tailscale logout')}      sign out",
            "",
            dim("  Key concept: Tailscale gives each device a private routable IP"),
            dim("  (100.x.x.x). Machines behave as if on the same LAN — no port"),
            dim("  forwarding or public IPs needed."),
        ]
        box("tailscale — Command Reference", lines, border_color=BMAGENTA)

    # ─── PING ─────────────────────────────────────────────────────────────────

    def ping(self, args):
        host = args[0] if args else None
        count = 4
        for i, a in enumerate(args):
            if a == "-c" and i+1 < len(args):
                try: count = int(args[i+1])
                except: pass

        if not host or host.startswith("-"):
            print(warn("  Usage: ping [-c count] <host>")); return
        if not self.w.tailscale_up and not host.startswith("192.168"):
            print(err("  Network unreachable — start tailscale or check interface")); return

        peer = self.w.peers.get(host)
        if peer:
            ip = peer["ts_ip"]
        elif host.startswith("100.") or host.startswith("192."):
            ip = host
        else:
            print(err(f"  ping: {host}: Name or service not known")); return

        print(f"\n  PING {host} ({ip}) 56(84) bytes of data.")
        for i in range(count):
            ms = round(random.uniform(1.8, 8.2) if not (peer and peer.get("relay")) else random.uniform(28,55), 2)
            print(f"  64 bytes from {ip}: icmp_seq={i+1} ttl=64 time={ms} ms")
            pause(0.22)
        print(f"\n  --- {host} ping statistics ---")
        print(f"  {count} packets transmitted, {count} received, 0% packet loss")
        self.s.add_xp(3, "ping")

    # ─── SSH ─────────────────────────────────────────────────────────────────

    def ssh(self, args):
        if not args:
            print(warn("  Usage: ssh [options] user@host")); return
        target = args[-1]
        if "@" not in target:
            print(err("  Specify user@host")); return
        user, host = target.split("@", 1)
        if not self.w.tailscale_up:
            print(err("  Cannot reach host — run tailscale up first")); return
        if not self.w.peer_online(host):
            print(err(f"  ssh: connect to host {host}: Connection refused")); return

        if host not in self.w.ssh_keys_copied and self.s.get("difficulty", 2) >= 2:
            print(warn(f"  ⚠ No SSH key installed on {host}. Password auth (simulated)."))
            print(dim(f"  Tip: ssh-keygen && ssh-copy-id {user}@{host}"))
            pause(0.3)
            print(dim("  (simulated password accepted)"))

        spinner(f"Connecting to {user}@{host}", 0.7)
        print(ok(f"  ✓ Connected to {host}"))
        print(dim(f"  Welcome to {self.w.peers[host]['os']}"))
        print(dim(f"  Last login: {time.strftime('%a %b %d %H:%M:%S')} from 100.64.1.10"))
        print(dim("  Type 'exit' to return to local shell\n"))

        self._remote_shell(user, host)
        self.s.add_xp(8, "ssh session")

    def _remote_shell(self, user, host):
        host_fs = self.w.fs.get(host, {})
        while True:
            try:
                cmd_in = input(f"  {magenta(user+'@'+host)}:{dim('~')}$ ").strip()
            except (EOFError, KeyboardInterrupt):
                print(dim("\n  Connection closed.")); break
            if not cmd_in: continue
            if cmd_in in ("exit","logout","quit"):
                print(dim("  logout")); break
            elif cmd_in in ("ls","ls -la","ls -l","ls -a"):
                for f in host_fs:
                    mb = host_fs[f].get("size_mb",0)
                    print(f"  {'drwxr-xr-x' if host_fs[f]['type']=='dir' else '-rw-r--r--'}  {user}  {user}  {mb:>8.0f}  {f}")
            elif cmd_in == "pwd":   print(f"  /home/{user}")
            elif cmd_in == "whoami": print(f"  {user}")
            elif cmd_in == "hostname": print(f"  {host}")
            elif cmd_in.startswith("uname"):
                print(f"  Linux {host} 6.1.0-21-amd64 #1 SMP Debian 6.1.90-1 x86_64 GNU/Linux")
            elif cmd_in.startswith("cat /etc/os-release"):
                print(f"  NAME=\"{self.w.peers[host]['os']}\"")
            elif cmd_in == "df -h":
                print("  Filesystem      Size  Used Avail Use%  Mounted on")
                print("  /dev/sda1       500G  120G  380G  24%  /")
                print("  /dev/sdb1       2.0T  800G  1.2T  40%  /mnt/storage")
            elif cmd_in == "free -h":
                print("                total   used   free")
                print("  Mem:          15Gi   4.2Gi  11Gi")
                print("  Swap:          2Gi     0B    2Gi")
            elif cmd_in.startswith("systemctl"):
                print(ok("  ✓ (simulated systemctl)"))
            elif cmd_in.startswith("sudo"):
                print(ok(f"  [sudo] simulated — {cmd_in[5:]} executed"))
            else:
                print(warn(f"  bash: {cmd_in.split()[0]}: command not found (simulated shell)"))

    def ssh_keygen(self, args):
        if self.w.ssh_key_exists:
            print(warn("  ~/.ssh/id_rsa already exists."))
            print(dim("  Use -f to specify a different filename.")); return
        spinner("Generating RSA 4096-bit key pair", 1.2)
        self.w.ssh_key_exists = True
        self.w.fs["laptop"]["~/.ssh/id_rsa"]      = {"size_mb":0.004,"type":"file"}
        self.w.fs["laptop"]["~/.ssh/id_rsa.pub"]  = {"size_mb":0.001,"type":"file"}
        print(ok("  ✓ Keys written to ~/.ssh/id_rsa and ~/.ssh/id_rsa.pub"))
        print(dim("  Fingerprint: SHA256:dGhpcyBpcyBhIHNpbXVsYXRlZCBrZXk="))
        print(dim("  Key type: RSA 4096 bits — good choice for security"))
        lvl = self.s.add_xp(12, "ssh-keygen"); self._xp(12, "ssh-keygen", lvl)

    def ssh_copy_id(self, args):
        if not args:
            print(warn("  Usage: ssh-copy-id user@host")); return
        target = args[-1]
        if "@" not in target:
            print(err("  Format: user@host")); return
        user, host = target.split("@",1)
        if not self.w.ssh_key_exists:
            print(err("  ✗ No key found. Run: ssh-keygen")); return
        if not self.w.tailscale_up:
            print(err("  ✗ Network not reachable.")); return
        if not self.w.peer_online(host):
            print(err(f"  ✗ {host} offline.")); return
        spinner(f"Copying public key to {host}", 0.8)
        self.w.ssh_keys_copied.add(host)
        print(ok(f"  ✓ Key installed — {user}@{host} will no longer need a password."))
        print(dim("  Key added to: ~/.ssh/authorized_keys"))
        lvl = self.s.add_xp(10, "ssh-copy-id"); self._xp(10, "ssh-copy-id", lvl)

    # ─── RSYNC ───────────────────────────────────────────────────────────────

    def rsync(self, args):
        if not args:
            self._rsync_help(); return

        # tokenize preserving quoted -e args
        try:
            tokens = shlex.split(" ".join(args))
        except:
            tokens = args

        flags   = [t for t in tokens if t.startswith("-") and not t.startswith("--")]
        lflags  = [t for t in tokens if t.startswith("--")]
        all_flags = flags + lflags
        posits  = [t for t in tokens if not t.startswith("-")]

        # -e "ssh ..." handling
        e_val = None
        for i, t in enumerate(tokens):
            if t == "-e" and i+1 < len(tokens):
                e_val = tokens[i+1]

        if e_val and e_val in posits:
            posits.remove(e_val)

        if len(posits) < 2:
            print(warn("  rsync needs <source> and <destination>"))
            self._rsync_help(); return

        src, dst = posits[0], posits[-1]
        src_remote = "@" in src
        dst_remote = "@" in dst

        if not self.w.tailscale_up and (src_remote or dst_remote):
            print(err("  ✗ Remote host unreachable — run: tailscale up")); return

        remote_host = None
        if dst_remote:
            remote_host = self.w.remote_host(dst)
        elif src_remote:
            remote_host = self.w.remote_host(src)

        if remote_host and not self.w.peer_online(remote_host):
            print(err(f"  ✗ Host '{remote_host}' is offline.")); return

        if remote_host:
            peer = self.w.peers.get(remote_host, {})
            relay = peer.get("relay", False)
        else:
            relay = False

        # SSH key warning
        if remote_host and remote_host not in self.w.ssh_keys_copied:
            print(warn(f"  ⚠ No SSH key on {remote_host} — password may be required."))
            print(dim(f"  Tip: ssh-keygen && ssh-copy-id {self.s.get('username')}@{remote_host}"))

        # File size
        local_path = src if not src_remote else dst
        size_mb = self.w.file_size(local_path.split(":")[-1])

        # Flag analysis
        has_a       = any("-a" in f for f in flags) or "-a" in " ".join(all_flags)
        has_v       = "-v" in " ".join(flags)
        has_h       = "-h" in " ".join(flags)
        has_z       = "-z" in " ".join(flags)
        has_progress= "--progress" in lflags or "--info=progress2" in lflags
        has_partial = "--partial" in lflags
        has_inplace = "--inplace" in lflags
        has_delete  = "--delete" in lflags
        no_compress = "--no-compress" in lflags or "--compress-level=0" in lflags
        has_dryrun  = "-n" in flags or "--dry-run" in lflags
        has_bwlimit = any("--bwlimit" in f for f in lflags)

        # Speed calculation
        base_speed = 15.0 if relay else random.uniform(85, 115)
        if has_z and not no_compress and size_mb > 100:
            base_speed *= 0.72
        if e_val and "aes128-gcm" in e_val:
            base_speed *= 1.18
        if has_bwlimit:
            for f in lflags:
                if f.startswith("--bwlimit="):
                    try: base_speed = min(base_speed, int(f.split("=")[1])/1024)
                    except: pass

        # Print summary header
        print()
        print(f"  {dim('src :')} {cyan(src)}")
        print(f"  {dim('dst :')} {cyan(dst)}")
        if e_val:
            print(f"  {dim('-e  :')} {dim(e_val)}")
        print()

        # Flag explanations
        flag_info = []
        if has_a:       flag_info.append(ok("-a") + dim("  archive: perms + timestamps + symlinks + recursive"))
        if has_v:       flag_info.append(ok("-v") + dim("  verbose"))
        if has_h:       flag_info.append(ok("-h") + dim("  human-readable sizes"))
        if has_z and not no_compress: flag_info.append(warn("-z") + dim("  compression ON (consider --no-compress for fast links)"))
        if no_compress: flag_info.append(ok("--no-compress") + dim("  compression OFF — faster on Tailscale"))
        if has_progress:flag_info.append(ok("--progress") + dim("  shows speed + ETA per file"))
        if has_partial: flag_info.append(ok("--partial")  + dim("  keep partial files — enables resume"))
        if has_inplace: flag_info.append(ok("--inplace")  + dim("  write directly — avoids full rewrite on resume"))
        if has_delete:  flag_info.append(warn("--delete") + dim("  ⚠ removes files on dest not present in source"))
        if has_dryrun:  flag_info.append(warn("-n/--dry-run") + dim("  preview only — no files transferred"))
        if has_bwlimit: flag_info.append(warn("--bwlimit") + dim("  throttle bandwidth"))

        if flag_info and (self.s.difficulty_hints() or self.s.get("difficulty",2) <= 3):
            print(dim("  Flag meanings:"))
            for fi in flag_info:
                print(f"    {fi}")
            print()

        if relay:
            print(warn(f"  ⚠ {remote_host} connected via relay — speeds ~15 MB/s"))
            print(dim("  Run: tailscale status to check connection type"))

        if has_dryrun:
            print(warn("  DRY RUN — nothing will be transferred:"))
            for f in list(self.w.fs.get("laptop",{}).keys())[:5]:
                print(f"    {dim('(would send)')}  {f}")
            print(ok("\n  ✓ Dry run complete."))
            self.s.add_xp(5, "rsync dry-run"); return

        print(info(f"  Transferring {size_mb:.0f} MB @ ~{base_speed:.0f} MB/s"))

        if has_progress or size_mb > 5:
            progress_bar(src.split("/")[-1], size_mb, base_speed)
        else:
            pause(0.6)
            print(ok(f"  ✓ {src.split('/')[-1]} ({size_mb:.1f} MB) sent"))
            print()

        # Store in dest filesystem
        fname     = src.split("/")[-1]
        dest_host = remote_host or "laptop"
        dest_path = (dst.split(":")[-1].rstrip("/") + "/" + fname) if remote_host else dst
        self.w.fs.setdefault(dest_host, {})[dest_path] = {"size_mb": size_mb, "type":"file"}

        xp = 20 if size_mb > 500 else (15 if size_mb > 50 else 10)
        lvl = self.s.add_xp(xp, "rsync"); self._xp(xp, "rsync transfer", lvl)

        # Achievements
        if size_mb >= 1000:
            if self.s.grant_achievement("big_hauler","Transferred 1GB+ in a single rsync"):
                print(f"  {BYELLOW}{B}🏆 Achievement: Big Hauler!{R}")
        if has_partial and has_inplace and no_compress:
            if self.s.grant_achievement("rsync_pro","Used optimal large-file rsync flags"):
                print(f"  {BYELLOW}{B}🏆 Achievement: rsync Pro!{R}")

    def _rsync_help(self):
        lines = [
            f"  {bold('rsync [options] <source> <destination>')}",
            "",
            f"  {cyan('Essential flags:')}",
            f"    {ok('-a')}              archive (perms, timestamps, symlinks, recursive)",
            f"    {ok('-v')}              verbose",
            f"    {ok('-h')}              human-readable sizes",
            f"    {ok('-z')}              compress (skip for large files on fast links)",
            f"    {ok('-n / --dry-run')}  preview without transferring",
            "",
            f"  {cyan('Large file flags (200MB–100GB):')}",
            f"    {ok('--progress')}      per-file speed + ETA",
            f"    {ok('--partial')}       keep partial — enables resume on drop",
            f"    {ok('--inplace')}       write direct — no temp file rewrite",
            f"    {ok('--no-compress')}   disable compression (faster on Tailscale)",
            f"    {ok('--bwlimit=5000')}  throttle to 5 MB/s (KB/s unit)",
            "",
            f"  {cyan('Advanced:')}",
            f"    {ok('--delete')}        mirror: remove dest files not in source",
            f"    {ok('-e ssh')}          explicit SSH transport",
            f"    {ok('-e \"ssh -p 2222\"')} custom SSH port",
            f"    {ok('-e \"ssh -T -c aes128-gcm@openssh.com -o Compression=no\"')}",
            f"               fastest cipher, no SSH compression",
            f"    {ok('--info=progress2')}  single overall progress bar",
            "",
            f"  {cyan('Examples:')}",
            f"    rsync -avh --progress ~/report.pdf user@server:/home/user/",
            f"    rsync -avh --progress --partial --inplace --no-compress \\",
            f"          ~/big.tar.gz user@server:/mnt/storage/",
            f"    rsync -avzn ~/data/ user@nas:/backup/   {dim('# dry-run')}",
            f"    rsync -avh --delete ~/site/ user@server:/var/www/html/",
        ]
        box("rsync — Full Reference", lines, border_color=BGREEN)

    def _xp(self, pts, reason, level_diff):
        xp_flash(pts, reason)
        if level_diff > 0:
            print(f"\n  {BYELLOW}{B}★ LEVEL UP! You are now level {self.s.get('level')} — "
                  f"{self._level_title()}{R}\n")

    def _level_title(self):
        from core.save import LEVEL_TITLES, level_for_xp
        lvl = level_for_xp(self.s.get("xp",0))
        return LEVEL_TITLES[min(lvl, len(LEVEL_TITLES)-1)]
