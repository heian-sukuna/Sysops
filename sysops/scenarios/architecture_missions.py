"""
scenarios/architecture_missions.py — Architecture pillar missions.

Infrastructure-as-Code workflow + reading/visualizing system topologies.
Step checks follow the project convention: verify real world state where it
changes, otherwise confirm the command ran via scenarios.checks (never
`lambda w, s: True`).
"""

from scenarios.checks import ran, ran_any

ARCH_MISSIONS = [
    {
        "id": "arch01",
        "title": "Blueprint",
        "category": "architecture: terraform",
        "difficulty": 2,
        "tags": ["ARCHITECTURE", "IAC", "TERRAFORM", "MEDIUM"],
        "story": (
            "The team keeps clicking around the cloud console and nobody can "
            "reproduce the staging environment. Your job: codify it. There's a "
            "main.tf describing a 3-tier web stack — initialize Terraform, "
            "preview the plan, apply it, then visualize what you built so the "
            "next person can actually see the architecture."
        ),
        "steps": [
            ("Initialize Terraform (providers + backend)",
             lambda w, s: bool(w.tf_state.get("initialized")),
             "terraform init"),
            ("Preview the changes before touching anything",
             lambda w, s: bool(w.tf_state.get("planned")),
             "terraform plan"),
            ("Provision the infrastructure",
             lambda w, s: len(w.tf_state.get("applied", [])) > 0,
             "terraform apply"),
            ("Visualize the topology you just built",
             ran("diagram"),
             "diagram"),
        ],
        "xp_reward": 90,
    },
    {
        "id": "arch02",
        "title": "Reading the Topology",
        "category": "architecture: design",
        "difficulty": 2,
        "tags": ["ARCHITECTURE", "MEDIUM"],
        "story": (
            "Before the design review you need to speak all three dialects of "
            "'how is this deployed': a classic web tier, a Kubernetes rollout, "
            "and the underlying network. Pull up each reference diagram, then "
            "confirm the live endpoints from Terraform's outputs."
        ),
        "steps": [
            ("Show the 3-tier web architecture",
             ran("diagram", "web"),
             "diagram web"),
            ("Show the Kubernetes ingress → service → deployment flow",
             ran("diagram", "k8s"),
             "diagram k8s"),
            ("Show the VPC multi-AZ subnet layout",
             ran("diagram", "vpc"),
             "diagram vpc"),
            ("Confirm the live endpoints (LB DNS, DB endpoint)",
             ran_any("terraform output", "terraform show", "terraform state"),
             "terraform output"),
        ],
        "xp_reward": 80,
    },
]
