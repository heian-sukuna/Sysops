"""
modules/networking.py — Networking commands
netstat, ss, ip, ifconfig, route, dig, nslookup, traceroute, curl, wget, arp, nload, iftop
"""

import time, random
from core.ui import *

class NetworkingModule:
    def __init__(self, world, save):
        self.w = world
        self.s = save

    def netstat(self, args):
        tulnp = any(x in " ".join(args) for x in ["-t","-u","-l","-n","-p","tulnp","tlnp"])
        show_all = "-a" in args
        route    = "-r" in args

        if route:
            self._route_table(); return

        print()
        print(info(f"  {'Proto':<8} {'Local Address':<26} {'Foreign Address':<26} {'State':<12} {'PID/Program'}"))
        print(dim("  " + "─" * 90))

        # Listening ports
        for entry in self.w.listening_ports:
            local = f"0.0.0.0:{entry['port']}"
            print(f"  {entry['proto']:<8} {local:<26} {'0.0.0.0:*':<26} {ok('LISTEN'):<19} {dim(str(entry['pid'])+'/'+entry['proc'])}")

        if show_all:
            # Established connections
            for _ in range(random.randint(3, 7)):
                lport  = random.randint(32000, 65000)
                rport  = random.choice([80, 443, 22, 5432])
                rip    = f"100.64.1.{random.randint(10,50)}"
                proto  = "tcp"
                pid    = random.randint(1000, 9999)
                proc   = random.choice(["nginx","node","python3","curl"])
                print(f"  {proto:<8} {'0.0.0.0:'+str(lport):<26} {rip+':'+str(rport):<26} {cyan('ESTABLISHED'):<19} {dim(str(pid)+'/'+proc)}")

        print()
        if self.s.difficulty_hints():
            print(dim("  Tip: netstat -tulnp  →  TCP+UDP Listening ports with PID"))
            print(dim("       netstat -an     →  all connections with numeric addresses"))
            print()
        self.s.add_xp(5,"netstat")

    def ss(self, args):
        """Modern replacement for netstat."""
        tulnp = any(x in " ".join(args) for x in ["t","u","l","n","p"])
        print()
        print(info(f"  {'Netid':<6} {'State':<12} {'Recv-Q':<8} {'Send-Q':<8} {'Local Address:Port':<28} {'Peer Address:Port':<24} Process"))
        print(dim("  " + "─" * 95))

        for entry in self.w.listening_ports:
            local = f"0.0.0.0:{entry['port']}"
            proc  = f'users:(("{entry["proc"]}",pid={entry["pid"]},fd=6))'
            print(f"  {entry['proto']:<6} {ok('LISTEN'):<19} {'0':<8} {'128':<8} {local:<28} {'0.0.0.0:*':<24} {dim(proc)}")

        # Established
        for _ in range(3):
            lport  = random.randint(40000,60000)
            rip    = f"100.64.1.{random.randint(10,40)}"
            rport  = random.choice([22,443,80])
            proc   = random.choice(["ssh","curl","node"])
            pid    = random.randint(1000,9999)
            pinfo  = f'users:(("{proc}",pid={pid},fd=3))'
            print(f"  tcp    {cyan('ESTAB'):<19} {'0':<8} {'0':<8} {'0.0.0.0:'+str(lport):<28} {rip+':'+str(rport):<24} {dim(pinfo)}")

        print()
        if self.s.difficulty_hints():
            print(dim("  ss -tulnp  →  same as netstat -tulnp but faster"))
            print(dim("  ss -s      →  summary statistics"))
        self.s.add_xp(5,"ss")

    def ip(self, args):
        if not args:
            print(warn("  Usage: ip <addr|route|link|neigh> [show|add|del]")); return
        sub = args[0].lower()

        if sub in ("addr","a","address"):
            self._ip_addr(args[1:])
        elif sub in ("route","r"):
            self._ip_route(args[1:])
        elif sub in ("link","l"):
            self._ip_link(args[1:])
        elif sub == "neigh":
            self._ip_neigh()
        else:
            print(warn(f"  Unknown: ip {sub}"))

    def _ip_addr(self, args):
        print()
        for idx, (iface, info) in enumerate(self.w.local_interfaces.items()):
            state = ok("UP") if info["up"] else err("DOWN")
            print(f"  {idx+1}: {cyan(iface)}: <BROADCAST,MULTICAST,{('UP,' if info['up'] else '')}LOWER_UP>")
            print(f"       link/ether {info['mac']} brd ff:ff:ff:ff:ff:ff")
            if info["up"] and info["ip"] != "N/A":
                mask = "32" if iface == "lo" else ("10" if "tailscale" in iface else "24")
                print(f"       inet {info['ip']}/{mask} scope global {iface}")
            print()
        self.s.add_xp(3,"ip addr")

    def _ip_route(self, args):
        self._route_table()

    def _ip_link(self, args):
        sub = args[0] if args else "show"
        if sub in ("show","list",""):
            for iface, info in self.w.local_interfaces.items():
                state = ok("UP") if info["up"] else err("DOWN")
                print(f"  {iface}: {state}  {dim(info['mac'])}")
        elif sub in ("set","up","down"):
            iface = args[1] if len(args)>1 else ""
            action= args[2] if len(args)>2 else sub
            if iface in self.w.local_interfaces:
                self.w.local_interfaces[iface]["up"] = (action == "up")
                print(ok(f"  {iface}: {action}"))

    def _ip_neigh(self):
        print(info("\n  ARP cache:"))
        for iface, info in self.w.local_interfaces.items():
            if info["mac"] and info["mac"] != "N/A" and info["up"]:
                print(f"  {info['ip']}  dev {iface}  lladdr {info['mac']}  REACHABLE")
        print()

    def _route_table(self):
        print()
        print(info(f"  {'Destination':<20} {'Gateway':<16} {'Genmask':<16} {'Iface'}"))
        print(dim("  " + "─" * 60))
        for r in self.w.routing_table:
            gw = r["gw"] if r["gw"] != "0.0.0.0" else "*"
            mask = "0.0.0.0" if "0.0.0.0/0" in r["dest"] else "255.255.255.0"
            print(f"  {r['dest']:<20} {gw:<16} {mask:<16} {r['iface']}")
        print()

    def ifconfig(self, args):
        iface = args[0] if args else None
        ifaces = self.w.local_interfaces
        if iface and iface in ifaces:
            info_d = ifaces[iface]
            state = "UP RUNNING" if info_d["up"] else "DOWN"
            print(f"\n  {iface}: flags=4163<{state}> mtu 1500")
            print(f"          inet {info_d['ip']}  netmask 255.255.255.0  broadcast 192.168.1.255")
            print(f"          ether {info_d['mac']}  txqueuelen 1000")
            print(f"          RX packets {random.randint(10000,99999)}  bytes {random.randint(1,50)}MB")
            print(f"          TX packets {random.randint(5000,50000)}   bytes {random.randint(1,20)}MB")
        else:
            for iface, info_d in ifaces.items():
                state = "UP RUNNING" if info_d["up"] else "DOWN"
                print(f"\n  {iface}: flags=4163<{state}> mtu 1500")
                print(f"          inet {info_d['ip']}  netmask 255.255.255.0")
                print(f"          ether {info_d['mac']}")
        print()

    def traceroute(self, args):
        host = args[0] if args else None
        if not host:
            print(warn("  Usage: traceroute <host>")); return

        peer = self.w.peers.get(host)
        dest_ip = peer["ts_ip"] if peer else host

        print(f"\n  traceroute to {host} ({dest_ip}), 30 hops max, 60 byte packets")
        hops = [
            ("192.168.1.1",  "gateway",    round(random.uniform(0.5,2.0),3)),
            ("100.64.0.1",   "ts-relay",   round(random.uniform(1.0,5.0),3)),
            (dest_ip,        host,         round(random.uniform(2.0,8.0),3)),
        ]
        for i, (ip, name, ms) in enumerate(hops, 1):
            print(f"  {i:2}  {ip} ({name})  {ms} ms  {ms+0.1} ms  {ms+0.2} ms")
            time.sleep(0.25)
        print()
        self.s.add_xp(5,"traceroute")

    def dig(self, args):
        domain = args[0] if args else "example.com"
        rtype  = args[1] if len(args)>1 else "A"
        print(f"\n  ; <<>> DiG 9.18.24 <<>> {domain} {rtype}")
        print(f"  ;; QUESTION SECTION:")
        print(f"  ;{domain}.    IN  {rtype}")
        print(f"\n  ;; ANSWER SECTION:")
        if rtype == "A":
            ip = f"93.184.{random.randint(1,254)}.{random.randint(1,254)}"
            print(f"  {domain}.   300  IN  A  {ip}")
        elif rtype == "MX":
            print(f"  {domain}.   3600  IN  MX  10  mail.{domain}.")
        elif rtype == "TXT":
            print(f'  {domain}.   300   IN  TXT  "v=spf1 include:_spf.google.com ~all"')
        elif rtype == "CNAME":
            print(f"  www.{domain}.  300  IN  CNAME  {domain}.")
        print(f"\n  ;; Query time: {random.randint(10,80)} msec")
        print(f"  ;; SERVER: 1.1.1.1#53(1.1.1.1) (UDP)")
        print()
        self.s.add_xp(4,"dig")

    def nslookup(self, args):
        domain = args[0] if args else "example.com"
        ip = f"93.184.{random.randint(1,254)}.{random.randint(1,254)}"
        print(f"\n  Server:    1.1.1.1")
        print(f"  Address:   1.1.1.1#53\n")
        print(f"  Non-authoritative answer:")
        print(f"  Name:    {domain}")
        print(f"  Address: {ip}")
        print()

    def curl(self, args):
        if not args:
            print(warn("  Usage: curl [options] <url>")); return

        verbose = "-v" in args or "--verbose" in args
        head    = "-I" in args or "--head" in args
        output  = None
        url     = None
        for i, a in enumerate(args):
            if a in ("-o","--output") and i+1<len(args): output = args[i+1]
            elif not a.startswith("-") and not output: url = a

        if not url:
            print(warn("  Specify a URL")); return

        spinner(f"Connecting to {url[:50]}", 0.7)

        if verbose:
            print(dim(f"  * Connected to {url.split('/')[2] if '/' in url else url}"))
            print(dim(f"  * SSL handshake complete (TLS 1.3)"))
            print(dim(f"  > GET / HTTP/1.1"))
            print(dim(f"  > Host: {url.split('/')[2] if '/' in url else url}"))
            print(dim(f"  < HTTP/1.1 200 OK"))
            print(dim(f"  < Content-Type: application/json"))

        if head:
            print(f"  HTTP/1.1 200 OK")
            print(f"  Server: nginx/1.25.3")
            print(f"  Content-Type: text/html; charset=UTF-8")
            print(f"  X-Frame-Options: SAMEORIGIN")
            print(f"  Strict-Transport-Security: max-age=31536000")
        else:
            fake_json = '{"status":"ok","service":"sysops-api","version":"1.0.0"}'
            if output:
                print(ok(f"  ✓ Response saved to {output}"))
            else:
                print(f"  {fake_json}")
        print()
        self.s.add_xp(4,"curl")

    def wget(self, args):
        url = next((a for a in args if not a.startswith("-")), None)
        if not url:
            print(warn("  Usage: wget <url>")); return
        fname = url.split("/")[-1] or "index.html"
        spinner(f"Connecting to {url[:50]}", 0.5)
        progress_bar(fname, round(random.uniform(1,50),1), speed_mb=8)
        print(ok(f"  ✓ Saved: {fname}"))

    def arp(self, args):
        print(info("\n  ARP table:"))
        print(f"  {'IP Address':<18} {'HW Type':<10} {'HW Address':<20} Interface")
        print(dim("  " + "─" * 58))
        for iface, info_d in self.w.local_interfaces.items():
            if info_d["mac"] != "N/A" and info_d["up"]:
                from core.world import fake_mac
                print(f"  {info_d['ip']:<18} {'ether':<10} {fake_mac():<20} {iface}")
        print()

    def nload(self, args):
        iface = args[0] if args else "eth0"
        print(info(f"  [nload — {iface} bandwidth monitor]"))
        print(dim("  Ctrl+C to exit (press Enter to stop simulation)\n"))
        try:
            for _ in range(6):
                rx = round(random.uniform(40, 115), 1)
                tx = round(random.uniform(5, 30), 1)
                bar_rx = "█" * int(rx/4) + "░" * (30 - int(rx/4))
                bar_tx = "█" * int(tx/4) + "░" * (30 - int(tx/4))
                print(f"  IN  [{BGREEN}{bar_rx}{R}] {rx:6.1f} MB/s")
                print(f"  OUT [{BCYAN}{bar_tx}{R}] {tx:6.1f} MB/s")
                print(f"  {'─'*50}")
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        print(dim("  [nload exited]"))

    def iftop(self, args):
        print(info("  [iftop — simulated per-connection bandwidth]"))
        print(dim("  Press Enter to exit\n"))
        me = self.w.local_interfaces.get("eth0",{}).get("ip","192.168.1.42")
        rows = []
        for peer_name, peer in self.w.peers.items():
            if peer.get("status") == "online":
                bw = round(random.uniform(10,90),1)
                rows.append((me, peer["ts_ip"], bw))
        for _ in range(5):
            for src, dst, bw in rows:
                bw += random.uniform(-5,5)
                bw = max(1, bw)
                print(f"  {src:>18} <=> {dst:<18}  {BCYAN}{bw:6.1f} Mb/s{R}")
            print(f"  {'─'*55}")
            time.sleep(0.45)
