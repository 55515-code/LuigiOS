# Base OS decision

Status: accepted

LuigiOS derives directly from CachyOS and its official Archiso tooling. The
target is x86-64-v3, matching the optimized CachyOS repository tier used by the
reference workstation.

This gives the product current kernels, performance-tuned packages, pacman,
Arch's developer ecosystem, and the same operational model as the installed
development host. COSMIC is composed as the sole desktop rather than carrying a
second environment or compatibility shell.

The decision is enforced in code by the upstream commit pin, product manifest,
forbidden-package list, dependency lock, and CI tests. Changing the base,
microarchitecture tier, or desktop requires a new recorded architecture
decision and a regenerated dependency lock.
