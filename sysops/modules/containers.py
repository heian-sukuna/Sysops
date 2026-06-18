"""
modules/containers.py — docker, docker compose, nginx
"""

import time, random
from core.ui import *

class ContainerModule:
    def __init__(self, world, save):
        self.w = world
        self.s = save

    # ─── DOCKER ───────────────────────────────────────────────────────────────

    def docker(self, args):
        if not args:
            self._docker_help(); return
        sub = args[0].lower()
        rest = args[1:]

        dispatch = {
            "ps":        self._ps,
            "images":    self._images,
            "pull":      self._pull,
            "run":       self._run,
            "stop":      self._stop,
            "start":     self._start,
            "restart":   self._restart,
            "rm":        self._rm,
            "rmi":       self._rmi,
            "logs":      self._logs,
            "exec":      self._exec,
            "build":     self._build,
            "inspect":   self._inspect,
            "stats":     self._stats,
            "network":   self._network,
            "volume":    self._volume,
            "system":    self._system,
            "compose":   self._compose,
        }
        fn = dispatch.get(sub)
        if fn:
            fn(rest)
        else:
            print(err(f"  Unknown: docker {sub}"))
            self._docker_help()

    def docker_compose(self, args):
        self._compose(args)

    def _ps(self, args):
        all_flag = "-a" in args
        print()
        print(info(f"  {'CONTAINER ID':<14} {'IMAGE':<22} {'STATUS':<12} {'PORTS':<22} NAME"))
        print(dim("  " + "─" * 80))
        shown = False
        for name, c in self.w.docker_containers.items():
            if not all_flag and c["status"] != "running":
                continue
            shown = True
            cid   = (name + "abc123")[:12]
            st    = ok("running") if c["status"] == "running" else dim("exited")
            ports = c.get("ports","")
            print(f"  {cid:<14} {c['image']:<22} {st:<19} {ports:<22} {name}")
        if not shown:
            print(dim(f"  (no containers{'  —  run with -a to show all' if not all_flag else ''})"))
        print()

    def _images(self, args):
        print()
        print(info(f"  {'REPOSITORY':<28} {'TAG':<10} {'IMAGE ID':<14} {'CREATED':<14} SIZE"))
        print(dim("  " + "─" * 75))
        if not self.w.docker_images:
            print(dim("  (no images — run: docker pull <image>)"))
        for img in self.w.docker_images:
            fake_id = (img.replace("/","").replace(":","") + "abc")[:12]
            size    = f"{random.randint(80,400)}MB"
            print(f"  {img:<28} {'latest':<10} {fake_id:<14} {'2 days ago':<14} {size}")
        print()

    def _pull(self, args):
        img = args[0] if args else None
        if not img:
            print(warn("  Usage: docker pull <image>")); return
        spinner(f"Pulling {img} from registry", 1.4)
        layers = [f"  {(img+str(i))[:12]}:  Pull complete" for i in range(random.randint(3,6))]
        for l in layers:
            print(dim(l)); time.sleep(0.09)
        if img not in self.w.docker_images:
            self.w.docker_images.append(img)
        print(ok(f"\n  ✓ {img} pulled successfully"))
        lvl = self.s.add_xp(8,"docker pull"); xp_flash(8,"docker pull")

    def _run(self, args):
        # Parse docker run flags
        name, ports, envs, vols, img = None, "", [], [], None
        detach = False
        i = 0
        while i < len(args):
            a = args[i]
            if a in ("-d","--detach"):      detach = True
            elif a in ("--name",) and i+1 < len(args): name = args[i+1]; i+=1
            elif a == "-p" and i+1 < len(args):  ports = args[i+1]; i+=1
            elif a == "-e" and i+1 < len(args):  envs.append(args[i+1]); i+=1
            elif a == "-v" and i+1 < len(args):  vols.append(args[i+1]); i+=1
            elif not a.startswith("-") and not img: img = a
            i += 1

        if not img:
            print(warn("  Usage: docker run [-d] [--name n] [-p host:cont] <image>")); return

        # Auto-pull if needed
        if img not in self.w.docker_images:
            print(warn(f"  Image '{img}' not local — pulling..."))
            self._pull([img])

        name = name or (img.split("/")[-1].split(":")[0] + "_1")
        if name in self.w.docker_containers:
            print(err(f"  ✗ Name '{name}' already in use. Remove first: docker rm {name}")); return

        self.w.docker_containers[name] = {
            "image": img, "status": "running",
            "ports": ports, "env": envs, "volumes": vols,
        }

        cid = (name + "deadbeef")[:12]
        if detach:
            print(ok(f"  ✓ {cid}  ({name} running detached)"))
        else:
            print(ok(f"  ✓ Container '{name}' started"))
        if envs:  print(dim(f"  ENV  : {', '.join(envs)}"))
        if vols:  print(dim(f"  VOL  : {', '.join(vols)}"))
        if ports: print(dim(f"  PORT : {ports}"))

        # Nginx awareness
        if "nginx" in img:
            self.w.nginx_running = True
            print(info("  Nginx is now running inside this container."))

        lvl = self.s.add_xp(10,"docker run"); xp_flash(10,"docker run")

    def _stop(self, args):
        name = args[0] if args else None
        if not name:
            print(warn("  Usage: docker stop <name>")); return
        if name not in self.w.docker_containers:
            print(err(f"  ✗ No container: {name}")); return
        self.w.docker_containers[name]["status"] = "exited"
        print(ok(f"  {name}"))
        self.s.add_xp(3,"docker stop")

    def _start(self, args):
        name = args[0] if args else None
        if not name or name not in self.w.docker_containers:
            print(err(f"  ✗ Container not found")); return
        self.w.docker_containers[name]["status"] = "running"
        print(ok(f"  {name}"))

    def _restart(self, args):
        name = args[0] if args else None
        if not name or name not in self.w.docker_containers:
            print(err(f"  ✗ Container not found")); return
        self.w.docker_containers[name]["status"] = "running"
        print(ok(f"  {name} restarted"))

    def _rm(self, args):
        names = [a for a in args if not a.startswith("-")]
        force = "-f" in args
        for name in names:
            if name not in self.w.docker_containers:
                print(err(f"  ✗ No container: {name}")); continue
            if self.w.docker_containers[name]["status"] == "running" and not force:
                print(err(f"  ✗ Running container. Stop first or use -f")); continue
            del self.w.docker_containers[name]
            print(ok(f"  {name}"))
        self.s.add_xp(4,"docker rm")

    def _rmi(self, args):
        img = args[0] if args else None
        if not img or img not in self.w.docker_images:
            print(err("  ✗ Image not found")); return
        in_use = [n for n,c in self.w.docker_containers.items() if c["image"]==img]
        if in_use:
            print(err(f"  ✗ In use by: {', '.join(in_use)}. Remove containers first."))
            return
        self.w.docker_images.remove(img)
        print(ok(f"  Untagged: {img}"))
        print(ok(f"  Deleted: sha256:{img[:8]}abc..."))

    def _logs(self, args):
        follow = "-f" in args
        name   = next((a for a in args if not a.startswith("-")), None)
        if not name or name not in self.w.docker_containers:
            print(err("  ✗ Container not found")); return
        c = self.w.docker_containers[name]
        print(dim(f"  [log stream: {name} | {c['image']}]"))
        entries = [
            f"Starting {c['image']}...",
            "Configuration loaded",
            "Listening on 0.0.0.0:80",
            f"GET / 200 1.2ms",
            f"GET /health 200 0.3ms",
        ]
        for i, e in enumerate(entries):
            ts = time.strftime(f"%Y-%m-%dT%H:0{i}:00Z")
            print(f"  {dim(ts)}  {e}")
            time.sleep(0.07)
        if follow:
            print(dim("  (following — press Ctrl+C to stop)"))
            try:
                while True:
                    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ")
                    print(f"  {dim(ts)}  GET /api/status 200 {random.randint(1,9)}ms")
                    time.sleep(1.5)
            except KeyboardInterrupt:
                print(dim("\n  [log stream ended]"))

    def _exec(self, args):
        inter = "-it" in args or "-i" in args
        name  = next((a for a in args if not a.startswith("-")), None)
        if not name or name not in self.w.docker_containers:
            print(err("  ✗ Container not found")); return
        if self.w.docker_containers[name]["status"] != "running":
            print(err(f"  ✗ '{name}' is not running.")); return
        cmd_i = args[args.index(name)+1:]
        cmd_s = " ".join(cmd_i) if cmd_i else "sh"
        if inter and not cmd_i:
            print(ok(f"  [exec shell in {name}]"))
            print(dim("  Type 'exit' to return"))
            while True:
                try:
                    ln = input(f"  root@{name[:8]}:/# ")
                except (EOFError, KeyboardInterrupt):
                    print(); break
                if ln in ("exit","quit"): break
                elif ln == "ps aux":
                    print(f"  PID   CMD\n  1     {self.w.docker_containers[name]['image']}\n  12    sh")
                elif ln == "env":
                    for e in self.w.docker_containers[name].get("env",[]):
                        print(f"  {e}")
                else:
                    print(dim(f"  (exec) {ln}"))
        else:
            print(ok(f"  [exec in {name}]: {cmd_s}"))
            print(dim("  (simulated output)"))

    def _build(self, args):
        tag = None
        ctx = "."
        for i, a in enumerate(args):
            if a == "-t" and i+1 < len(args): tag = args[i+1]
            elif not a.startswith("-") and a != tag: ctx = a
        if not tag:
            print(warn("  Usage: docker build -t <name:tag> <context>")); return
        steps = [
            "FROM node:20-alpine",
            "WORKDIR /app",
            "COPY package*.json ./",
            "RUN npm ci --only=production",
            "COPY . .",
            "EXPOSE 3000",
            'CMD ["node","server.js"]',
        ]
        print(info(f"\n  Building image: {tag}"))
        for i, step in enumerate(steps, 1):
            print(f"  Step {i}/{len(steps)} : {dim(step)}")
            time.sleep(0.16)
        if tag not in self.w.docker_images:
            self.w.docker_images.append(tag)
        print(ok(f"\n  ✓ Successfully built {tag}"))
        lvl = self.s.add_xp(14,"docker build"); xp_flash(14,"docker build")

    def _inspect(self, args):
        name = args[0] if args else None
        if not name or name not in self.w.docker_containers:
            print(err("  ✗ Not found")); return
        c = self.w.docker_containers[name]
        print(info(f"\n  [{name}]"))
        print(f"  Image   : {c['image']}")
        print(f"  Status  : {ok(c['status']) if c['status']=='running' else dim(c['status'])}")
        print(f"  Ports   : {c.get('ports','(none)')}")
        print(f"  Env     : {', '.join(c.get('env',[])) or '(none)'}")
        print(f"  Volumes : {', '.join(c.get('volumes',[])) or '(none)'}")
        print(f"  Network : bridge")
        print()

    def _stats(self, args):
        print(info(f"\n  {'CONTAINER':<18} {'CPU%':>6} {'MEM':>10} {'MEM%':>6} {'NET I/O':>14}"))
        print(dim("  " + "─" * 60))
        if not self.w.docker_containers:
            print(dim("  (no running containers)")); return
        for name, c in self.w.docker_containers.items():
            if c["status"] != "running": continue
            cpu = round(random.uniform(0.1, 12.0), 1)
            mem_mb = random.randint(30, 512)
            mem_pct = round(mem_mb/15360*100, 1)
            net = f"{random.randint(1,50)}MB / {random.randint(1,20)}MB"
            print(f"  {name:<18} {cpu:>5}%  {mem_mb:>6}MiB  {mem_pct:>5}%  {net:>14}")
        print()

    def _network(self, args):
        sub = args[0] if args else "ls"
        if sub == "ls":
            print(info(f"\n  {'NETWORK ID':<14} {'NAME':<20} {'DRIVER':<10} SCOPE"))
            print(dim("  " + "─" * 52))
            for net in self.w.docker_networks:
                nid = (net+"000000")[:12]
                driver = "overlay" if "swarm" in net else "bridge"
                print(f"  {nid:<14} {net:<20} {driver:<10} local")
            print()
        elif sub == "create":
            name   = args[1] if len(args)>1 else "mynet"
            driver = "bridge"
            for i, a in enumerate(args):
                if a == "-d" and i+1<len(args): driver = args[i+1]
            self.w.docker_networks.append(name)
            print(ok(f"  Network '{name}' created (driver: {driver})"))
        elif sub in ("rm","remove"):
            name = args[1] if len(args)>1 else ""
            if name in self.w.docker_networks:
                self.w.docker_networks.remove(name)
                print(ok(f"  Deleted: {name}"))
            else:
                print(err(f"  ✗ Network not found: {name}"))
        elif sub == "inspect":
            name = args[1] if len(args)>1 else ""
            if name in self.w.docker_networks:
                print(info(f"\n  [{name}]"))
                print(f"  Driver  : bridge")
                print(f"  Subnet  : 172.{random.randint(17,31)}.0.0/16")
                print(f"  Gateway : 172.18.0.1")
            else:
                print(err(f"  ✗ Not found: {name}"))

    def _volume(self, args):
        sub = args[0] if args else "ls"
        if sub == "ls":
            print(info(f"\n  {'DRIVER':<8} VOLUME NAME"))
            print(dim("  " + "─" * 30))
            if not self.w.docker_volumes:
                print(dim("  (no volumes)"))
            for v in self.w.docker_volumes:
                print(f"  local    {v}")
            print()
        elif sub == "create":
            name = args[1] if len(args)>1 else "myvol"
            self.w.docker_volumes.append(name)
            print(ok(f"  {name}"))
        elif sub in ("rm","remove"):
            name = args[1] if len(args)>1 else ""
            if name in self.w.docker_volumes:
                self.w.docker_volumes.remove(name); print(ok(f"  {name}"))
            else: print(err(f"  ✗ Volume not found"))
        elif sub == "inspect":
            name = args[1] if len(args)>1 else ""
            print(info(f"\n  Volume: {name}"))
            print(f"  Driver: local")
            print(f"  Mountpoint: /var/lib/docker/volumes/{name}/_data")

    def _system(self, args):
        sub = args[0] if args else "df"
        if sub == "df":
            used = sum(1 for c in self.w.docker_containers.values())
            print(info("\n  Docker disk usage:"))
            print(f"  Images     : {len(self.w.docker_images)} ({len(self.w.docker_images)*180}MB)")
            print(f"  Containers : {used}")
            print(f"  Volumes    : {len(self.w.docker_volumes)}")
            print(f"  Build cache: 12 items (240MB)")
            print()
        elif sub == "prune":
            stopped = [n for n,c in self.w.docker_containers.items() if c["status"]!="running"]
            for n in stopped:
                del self.w.docker_containers[n]
            print(ok(f"  Removed {len(stopped)} stopped containers"))
            print(ok(f"  Reclaimed: {len(stopped)*45}MB"))

    def _compose(self, args):
        sub = args[0] if args else "up"
        services = ["nginx", "frontend", "backend"]

        if sub == "up":
            detach = "-d" in args
            print(info("  Starting services from docker-compose.yml..."))
            images_needed = {
                "nginx": "nginx:alpine",
                "frontend": "my-portfolio_frontend",
                "backend": "my-portfolio_backend",
            }
            for svc in services:
                img = images_needed[svc]
                if img not in self.w.docker_images:
                    self.w.docker_images.append(img)
                if svc not in self.w.docker_containers:
                    ports = "80:80" if svc == "nginx" else ("3000:3000" if svc == "frontend" else "4000:4000")
                    self.w.docker_containers[svc] = {
                        "image": img, "status": "running",
                        "ports": ports, "env": [], "volumes": [],
                    }
                print(ok(f"  ✓ {svc:<12} started"))
                time.sleep(0.18)
            self.w.nginx_running = True
            print(info("\n  Network: app-net (bridge)"))
            print(dim("  All services connected on private bridge network"))
            lvl = self.s.add_xp(18,"compose up"); xp_flash(18,"compose up")

        elif sub == "down":
            v_flag = "-v" in args
            for svc in services:
                if svc in self.w.docker_containers:
                    self.w.docker_containers[svc]["status"] = "exited"
                    print(ok(f"  Stopping {svc}..."))
            if v_flag:
                print(ok("  Removing volumes..."))
            print(ok("  ✓ Done"))

        elif sub in ("ps","status"):
            self._ps([])

        elif sub == "logs":
            svc = args[1] if len(args)>1 else services[0]
            self._logs([svc])

        elif sub == "restart":
            svc = args[1] if len(args)>1 else ""
            if svc in self.w.docker_containers:
                self.w.docker_containers[svc]["status"] = "running"
                print(ok(f"  ✓ {svc} restarted"))
            else:
                print(err(f"  ✗ Service '{svc}' not found"))

        elif sub == "build":
            print(info("  Building images from docker-compose.yml..."))
            for svc in services:
                spinner(f"Building {svc}", 0.8)
            print(ok("  ✓ All images built"))

        elif sub == "exec":
            svc = args[1] if len(args)>1 else ""
            self._exec([svc] + args[2:])

        elif sub == "pull":
            for svc in services:
                spinner(f"Pulling {svc}", 0.5)
            print(ok("  ✓ All images updated"))

        else:
            print(warn(f"  Unknown: docker compose {sub}"))

    def _docker_help(self):
        lines = [
            f"  {cyan('docker ps [-a]')}          list containers (all)",
            f"  {cyan('docker images')}            list local images",
            f"  {cyan('docker pull <img>')}        download image",
            f"  {cyan('docker run [flags] <img>')} start container",
            f"    {dim('-d')} detach  {dim('--name n')}  {dim('-p h:c')} port  {dim('-e K=V')} env  {dim('-v s:d')} volume",
            f"  {cyan('docker stop / start / restart <n>')}",
            f"  {cyan('docker rm [-f] <n>')}       remove container",
            f"  {cyan('docker rmi <image>')}        remove image",
            f"  {cyan('docker logs [-f] <n>')}      view logs (follow)",
            f"  {cyan('docker exec -it <n> sh')}   shell into container",
            f"  {cyan('docker inspect <n>')}        detailed info",
            f"  {cyan('docker stats')}              live resource usage",
            f"  {cyan('docker build -t <tag> .')}  build from Dockerfile",
            f"  {cyan('docker network ls/create/rm')}",
            f"  {cyan('docker volume ls/create/rm')}",
            f"  {cyan('docker system df/prune')}   disk usage / cleanup",
            f"  {cyan('docker compose up [-d]')}   start all services",
            f"  {cyan('docker compose down [-v]')} stop + optionally remove volumes",
            f"  {cyan('docker compose logs [-f] <svc>')}",
        ]
        box("docker — Full Reference", lines, border_color=BBLUE)

    # ─── NGINX ────────────────────────────────────────────────────────────────

    def nginx(self, args):
        if not args:
            self._nginx_help(); return
        sub = args[0].lower()

        if sub == "status":
            if self.w.nginx_running:
                print(ok("  ● nginx is active (running)"))
                print(dim("  Loaded: /etc/nginx/nginx.conf"))
                print(dim("  Listening: 0.0.0.0:80, 0.0.0.0:443"))
            else:
                print(warn("  ○ nginx is inactive (stopped)"))
                print(dim("  Tip: docker run -d -p 80:80 --name nginx nginx"))

        elif sub == "start":
            if not self.w.nginx_running:
                self.w.nginx_running = True
                print(ok("  ✓ nginx started"))
            else:
                print(info("  nginx already running"))

        elif sub == "stop":
            self.w.nginx_running = False
            print(ok("  nginx stopped"))

        elif sub == "reload":
            if not self.w.nginx_running:
                print(err("  ✗ nginx not running")); return
            spinner("Reloading nginx configuration", 0.8)
            print(ok("  ✓ nginx reloaded — zero downtime"))

        elif sub == "test" or sub == "-t":
            spinner("Testing nginx configuration", 0.6)
            if self.w.nginx_configs:
                print(ok("  nginx: configuration file /etc/nginx/nginx.conf test is successful"))
            else:
                print(ok("  nginx: the configuration file /etc/nginx/nginx.conf syntax is ok"))
                print(ok("  nginx: configuration file /etc/nginx/nginx.conf test is successful"))

        elif sub == "config" or sub == "site":
            self._nginx_config(args[1:])

        elif sub == "logs":
            logtype = args[1] if len(args)>1 else "access"
            self._nginx_logs(logtype)

        elif sub == "explain":
            self._nginx_explain()

        else:
            print(err(f"  Unknown nginx subcommand: {sub}"))
            self._nginx_help()

    def _nginx_config(self, args):
        action = args[0] if args else "show"
        site   = args[1] if len(args)>1 else "default"

        if action == "create":
            print(info(f"\n  Creating nginx site config: {site}"))
            domain = site if "." in site else f"{site}.example.com"
            conf = f"""server {{
    listen 80;
    server_name {domain};

    location / {{
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}

    location /static/ {{
        alias /var/www/html/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }}

    # Security headers
    add_header X-Frame-Options SAMEORIGIN;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Referrer-Policy strict-origin-when-cross-origin;
}}"""
            self.w.nginx_configs[site] = conf
            self.w.fs.setdefault("server",{})
            self.w.fs["server"][f"/etc/nginx/sites-available/{site}"] = {"size_mb":0.001,"type":"file"}
            print(ok(f"  ✓ Config written to /etc/nginx/sites-available/{site}"))
            print(dim("  Enable with: nginx config enable " + site))
            print()
            print(dim(conf))
            lvl = self.s.add_xp(15,"nginx config create"); xp_flash(15,"nginx config")

        elif action == "enable":
            if site in self.w.nginx_configs:
                self.w.fs.setdefault("server",{})
                self.w.fs["server"][f"/etc/nginx/sites-enabled/{site}"] = {"size_mb":0,"type":"file"}
                print(ok(f"  ✓ Enabled: /etc/nginx/sites-enabled/{site} → sites-available/{site}"))
                print(dim("  Run: nginx reload to apply"))
            else:
                print(err(f"  ✗ Config '{site}' not found. Create it first."))

        elif action == "show":
            if self.w.nginx_configs:
                for name, conf in self.w.nginx_configs.items():
                    print(info(f"\n  ── {name} ──"))
                    print(dim(conf))
            else:
                print(dim("  No custom configs yet. Run: nginx config create <site>"))

        elif action == "ssl":
            domain = args[1] if len(args)>1 else site+".example.com"
            print(info(f"\n  Adding SSL config for {domain}"))
            print(dim("  (In production: use certbot --nginx -d " + domain + ")"))
            ssl_block = f"""
    # SSL section (Certbot managed)
    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_stapling on;
    ssl_stapling_verify on;

    # Redirect HTTP → HTTPS
    if ($scheme != "https") {{
        return 301 https://$host$request_uri;
    }}"""
            print(ok("  ✓ SSL block (simulated):"))
            print(dim(ssl_block))
            lvl = self.s.add_xp(20,"nginx SSL"); xp_flash(20,"nginx SSL")

    def _nginx_logs(self, logtype):
        print(dim(f"\n  /var/log/nginx/{logtype}.log"))
        print(dim("  " + "─" * 60))
        entries = [
            '192.168.1.10 - - [24/Apr/2026:10:01:01 +0000] "GET / HTTP/1.1" 200 1234',
            '100.64.1.10 - - [24/Apr/2026:10:01:05 +0000] "GET /api/status HTTP/1.1" 200 42',
            '192.168.1.55 - - [24/Apr/2026:10:01:09 +0000] "POST /login HTTP/1.1" 302 0',
            '10.0.0.1 - - [24/Apr/2026:10:01:15 +0000] "GET /admin HTTP/1.1" 403 150',
            '100.64.1.20 - - [24/Apr/2026:10:01:20 +0000] "GET /static/main.js HTTP/1.1" 304 0',
        ]
        if logtype == "error":
            entries = [
                '2026/04/24 10:00:01 [warn] 15#15: *3 upstream server not available',
                '2026/04/24 10:00:45 [error] 15#15: *12 connect() failed (111: Connection refused)',
                '2026/04/24 10:01:03 [notice] 1#1: signal process started',
            ]
        for e in entries:
            print(f"  {dim(e)}")
        print()

    def _nginx_explain(self):
        lines = [
            bold("nginx as a Reverse Proxy") + " — the most common use case",
            "",
            dim("Client → [nginx :80/:443] → [your app :3000]"),
            "",
            f"  {ok('proxy_pass')}         forward requests to backend",
            f"  {ok('proxy_set_header')}   pass real client IP / protocol to app",
            f"  {ok('location /api/')}     route specific paths differently",
            f"  {ok('ssl_certificate')}    TLS termination — encrypt at nginx level",
            f"  {ok('add_header')}         inject security headers (HSTS, CSP, etc.)",
            f"  {ok('expires / Cache')}    tell browsers to cache static files",
            "",
            dim("  Common pattern: nginx + docker compose"),
            dim("  nginx container on :80/:443 → frontend :3000 → backend :4000"),
            "",
            f"  {cyan('Commands: nginx config create <site> | nginx config ssl <domain>')}",
            f"  {cyan('          nginx test | nginx reload | nginx logs access')}",
        ]
        box("nginx — Concepts & Usage", lines, border_color=BGREEN)

    def _nginx_help(self):
        lines = [
            f"  {cyan('nginx status')}                check if running",
            f"  {cyan('nginx start / stop / reload')} control server",
            f"  {cyan('nginx test')}                  validate config syntax",
            f"  {cyan('nginx config create <site>')}  generate site config",
            f"  {cyan('nginx config enable <site>')}  symlink to sites-enabled",
            f"  {cyan('nginx config ssl <domain>')}   add SSL/TLS block",
            f"  {cyan('nginx config show')}           display current configs",
            f"  {cyan('nginx logs access/error')}     view log files",
            f"  {cyan('nginx explain')}               concepts & reverse proxy guide",
        ]
        box("nginx — Command Reference", lines, border_color=BGREEN)
