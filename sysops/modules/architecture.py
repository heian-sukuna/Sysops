"""
modules/architecture.py — Architecture pillar.

Two halves of the same job: describing infrastructure as code (`terraform`)
and being able to *see* the system you're describing (`diagram`).

Everything is a simulation — no cloud resources are created. The terraform
workflow (init → plan → apply → destroy) mirrors the real tool, and `diagram`
renders reference topologies as ASCII art so design ideas stay legible.
"""

import random
from core.ui import *

# A representative 3-tier web stack — the contents of the simulated `main.tf`.
# (resource address, one-line summary)
TF_RESOURCES = [
    ("aws_vpc.main",           "VPC  10.0.0.0/16"),
    ("aws_subnet.public_a",    "public subnet  10.0.1.0/24  (az-a)"),
    ("aws_subnet.public_b",    "public subnet  10.0.2.0/24  (az-b)"),
    ("aws_subnet.private_a",   "private subnet 10.0.10.0/24 (az-a)"),
    ("aws_subnet.private_b",   "private subnet 10.0.11.0/24 (az-b)"),
    ("aws_security_group.web", "SG  allow 80,443 from 0.0.0.0/0"),
    ("aws_lb.app",             "application load balancer (HTTPS :443)"),
    ("aws_instance.web_a",     "EC2 t3.small  web-1"),
    ("aws_instance.web_b",     "EC2 t3.small  web-2"),
    ("aws_db_instance.main",   "RDS postgres 16  (Multi-AZ)"),
]

TF_OUTPUTS = {
    "lb_dns_name": "app-1a2b3c.eu-west-1.elb.amazonaws.com",
    "db_endpoint": "main.cluster-xyz.eu-west-1.rds.amazonaws.com:5432",
    "vpc_id":      "vpc-0a1b2c3d4e5f",
}


class ArchitectureModule:
    def __init__(self, world, save):
        self.w = world
        self.s = save

    # ══════════════════════════════════════════════════════════════════════════
    # TERRAFORM  —  infrastructure as code
    # ══════════════════════════════════════════════════════════════════════════

    def terraform(self, args):
        if not args:
            self.help(); return
        sub = args[0].lower()
        tf  = self.w.tf_state

        if sub in ("-help", "--help", "help"):
            self.help()

        elif sub == "init":
            spinner("Initializing the backend", 0.8)
            spinner("Installing provider plugins (hashicorp/aws)", 1.0)
            tf["initialized"] = True
            print(ok("\n  Terraform has been successfully initialized!"))
            print(dim("  Next: terraform plan"))
            lvl = self.s.add_xp(10, "terraform init"); self._xp(10, "terraform init", lvl)

        elif sub in ("fmt", "format"):
            print(ok("  ✓ main.tf  (formatted)"))

        elif sub == "validate":
            if not tf["initialized"]:
                print(err("  ✗ Not initialized. Run: terraform init")); return
            print(ok("  Success! The configuration is valid."))
            self.s.add_xp(3, "terraform validate")

        elif sub == "plan":
            if not tf["initialized"]:
                print(err("  ✗ Not initialized. Run: terraform init")); return
            self._print_plan()
            tf["planned"] = True
            lvl = self.s.add_xp(12, "terraform plan"); self._xp(12, "terraform plan", lvl)

        elif sub == "apply":
            if not tf["initialized"]:
                print(err("  ✗ Not initialized. Run: terraform init")); return
            if not tf["planned"]:
                print(info("  No saved plan — generating one now…\n"))
                self._print_plan()
                tf["planned"] = True
            print()
            section("TERRAFORM APPLY")
            applied = []
            for addr, _summary in TF_RESOURCES:
                print(f"  {cyan(addr)}: {DIM}Creating...{R}")
                pause(0.18)
                secs = round(random.uniform(1.0, 9.0), 0)
                print(f"  {cyan(addr)}: {ok('Creation complete')} {DIM}after {secs:.0f}s{R}")
                applied.append(addr)
            tf["applied"] = applied
            print(ok(f"\n  Apply complete! Resources: {len(applied)} added, 0 changed, 0 destroyed."))
            self._print_outputs()
            print(dim(f"\n  Tip: visualize what you built →  {get_theme()['cmd']}diagram{R}"))
            lvl = self.s.add_xp(40, "terraform apply"); self._xp(40, "terraform apply", lvl)

        elif sub == "destroy":
            if not tf["applied"]:
                print(info("  Nothing to destroy — no resources are applied.")); return
            print()
            section("TERRAFORM DESTROY")
            for addr in reversed(tf["applied"]):
                print(f"  {cyan(addr)}: {DIM}Destroying...{R}  {warn('Destruction complete')}")
                pause(0.10)
            n = len(tf["applied"])
            tf["applied"] = []
            tf["planned"] = False
            print(warn(f"\n  Destroy complete! Resources: {n} destroyed."))
            self.s.add_xp(8, "terraform destroy")

        elif sub == "output":
            if not tf["applied"]:
                print(info("  No outputs — apply the configuration first.")); return
            self._print_outputs()
            self.s.add_xp(3, "terraform output")

        elif sub in ("show", "state"):
            # `terraform show` and `terraform state list`
            if not tf["applied"]:
                print(info("  No state yet — run terraform apply.")); return
            print()
            section("TERRAFORM STATE")
            for addr in tf["applied"]:
                summary = dict(TF_RESOURCES).get(addr, "")
                print(f"  {ok('●')} {cyan(addr):<40} {DIM}{summary}{R}")
            print(dim(f"\n  {len(tf['applied'])} resources tracked in state."))
            self.s.add_xp(3, "terraform state")

        else:
            print(warn(f"  Unknown terraform subcommand: {sub}"))
            print(dim("  Try: init · validate · plan · apply · output · show · destroy"))

    def _print_plan(self):
        print()
        section("TERRAFORM PLAN")
        print(dim("  Terraform will perform the following actions:\n"))
        for addr, summary in TF_RESOURCES:
            print(f"  {ok('+')} {cyan(addr):<40} {DIM}{summary}{R}")
        print(f"\n  {B}Plan:{R} {ok(str(len(TF_RESOURCES)) + ' to add')}, "
              f"0 to change, 0 to destroy.")

    def _print_outputs(self):
        print()
        print(info("  Outputs:"))
        for k, v in TF_OUTPUTS.items():
            print(f"    {cyan(k)} = {DIM}\"{v}\"{R}")

    # ══════════════════════════════════════════════════════════════════════════
    # DIAGRAM  —  ASCII system-design topologies
    # ══════════════════════════════════════════════════════════════════════════

    def diagram(self, args):
        kind = (args[0].lower() if args else "")
        if kind in ("", "infra", "state"):
            if self.w.tf_state.get("applied"):
                self._diagram_web("Your provisioned infrastructure (from terraform state)")
            else:
                print(info("  No infrastructure applied yet — showing the reference 3-tier web stack."))
                print(dim(f"  (run {get_theme()['cmd']}terraform apply{R}{DIM} to build it, or try "
                          f"{get_theme()['cmd']}diagram k8s{R}{DIM} / {get_theme()['cmd']}diagram vpc{R}{DIM})"))
                self._diagram_web("Reference: 3-tier web architecture")
        elif kind in ("web", "3tier", "3-tier"):
            self._diagram_web("3-tier web architecture")
        elif kind in ("k8s", "kubernetes", "kube"):
            self._diagram_k8s()
        elif kind in ("vpc", "network", "net"):
            self._diagram_vpc()
        else:
            print(warn(f"  Unknown diagram: {kind}"))
            print(dim("  Available: web · k8s · vpc   (or no argument for your live infra)"))

    def _render(self, title, art):
        bc = get_theme()["box_border"]
        ac = get_theme()["accent"]
        print()
        section(title)
        for line in art:
            print(f"  {bc}{line}{R}")
        print()

    def _diagram_web(self, title):
        art = [
            "                 ☁  Internet",
            "                       │",
            "                       ▼",
            "              ┌──────────────────┐",
            "              │    Route 53  DNS │",
            "              └────────┬─────────┘",
            "                       ▼",
            "             ╔═══════════════════╗",
            "             ║  Application LB   ║   :443  TLS",
            "             ╚════╦═════════╦════╝",
            "                  ║         ║",
            "             ┌────▼───┐ ┌───▼────┐",
            "             │ web-1  │ │ web-2  │   app tier · t3.small",
            "             │ :8080  │ │ :8080  │",
            "             └────┬───┘ └───┬────┘",
            "                  └────╦────┘",
            "                       ▼",
            "               ┌───────────────┐",
            "               │  RDS  (pg 16) │   data tier · Multi-AZ",
            "               │ primary + rep │",
            "               └───────────────┘",
        ]
        self._render(title, art)

    def _diagram_k8s(self):
        art = [
            "  ┌──────────────── Ingress ────────────────┐",
            "  │            app.example.com  :443         │",
            "  └─────────────────────┬────────────────────┘",
            "                        ▼",
            "              ┌──────── Service ────────┐",
            "              │   ClusterIP   :80→8080  │",
            "              └──┬─────────┬─────────┬──┘",
            "                 ▼         ▼         ▼",
            "            ┌────────┐ ┌────────┐ ┌────────┐",
            "            │ pod-1  │ │ pod-2  │ │ pod-3  │   Deployment",
            "            └────────┘ └────────┘ └────────┘   replicas = 3",
            "                 │         │         │",
            "                 └─────────┼─────────┘",
            "                           ▼",
            "                  ┌─────────────────┐",
            "                  │  PersistentVol  │",
            "                  └─────────────────┘",
        ]
        self._render("Kubernetes: ingress → service → deployment", art)

    def _diagram_vpc(self):
        art = [
            "┌────────────────────── VPC 10.0.0.0/16 ──────────────────────┐",
            "│                                                              │",
            "│   ┌──── AZ-a ──────────────┐  ┌──── AZ-b ──────────────┐     │",
            "│   │ public  10.0.1.0/24    │  │ public  10.0.2.0/24    │     │",
            "│   │   └─ web-1 · NAT-gw    │  │   └─ web-2             │     │",
            "│   │                        │  │                        │     │",
            "│   │ private 10.0.10.0/24   │  │ private 10.0.11.0/24   │     │",
            "│   │   └─ RDS primary       │  │   └─ RDS standby       │     │",
            "│   └────────────────────────┘  └────────────────────────┘     │",
            "│                                                              │",
            "│   Internet GW ── route table ── ALB (public) ── ASG (private)│",
            "└──────────────────────────────────────────────────────────────┘",
        ]
        self._render("AWS VPC: multi-AZ subnet layout", art)

    # ══════════════════════════════════════════════════════════════════════════
    # HELP / XP
    # ══════════════════════════════════════════════════════════════════════════

    def help(self):
        th = get_theme()
        lines = [
            f"  {bold('Infrastructure as Code')}",
            f"  {cyan('terraform init')}        download providers, prep backend",
            f"  {cyan('terraform validate')}    check the configuration",
            f"  {cyan('terraform plan')}        preview what will be created",
            f"  {cyan('terraform apply')}       provision the infrastructure",
            f"  {cyan('terraform show')}        list resources in state",
            f"  {cyan('terraform output')}      show output values (DNS, endpoints)",
            f"  {cyan('terraform destroy')}     tear it all down",
            "",
            f"  {bold('System-design diagrams')}",
            f"  {cyan('diagram')}               your live infra (or the reference stack)",
            f"  {cyan('diagram web')}           3-tier web architecture",
            f"  {cyan('diagram k8s')}           kubernetes ingress/service/deployment",
            f"  {cyan('diagram vpc')}           AWS VPC multi-AZ subnet layout",
            "",
            dim("  Key idea: describe infrastructure declaratively, plan before you"),
            dim("  apply, and keep the topology legible. IaC + a clear diagram is how"),
            dim("  architecture stays reviewable instead of living in someone's head."),
        ]
        box("Architecture — IaC & Design Reference", lines, width=72,
            style="round", border_color=th["box_border"])

    def _xp(self, pts, reason, level_diff):
        xp_flash(pts, reason)
        if level_diff > 0:
            from core.save import LEVEL_TITLES, level_for_xp
            lvl = level_for_xp(self.s.get("xp", 0))
            title = LEVEL_TITLES[min(lvl, len(LEVEL_TITLES)-1)]
            print(f"\n  {BYELLOW}{B}★ LEVEL UP! You are now level {lvl} — {title}{R}\n")
