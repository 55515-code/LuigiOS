# Secure implementation

New network-facing or privileged components should use Rust or another
memory-safe implementation where practical. Native code remains available for
drivers, debugging, and upstream compatibility, with hardening inherited from
CachyOS packaging.

Required boundaries:

- package signatures or TUF metadata authorize installation, never a transport;
- release peers use a dedicated account and cache with systemd sandboxing;
- peer participation, DHT, port forwarding, and personal synchronization are
  explicit independent choices;
- SSH and telemetry are off, UFW is on, and firmware/audit tooling is installed;
- full pacman transactions and Snapper recovery replace partial upgrades;
- secrets stay outside images, provenance, logs, peer discovery, and caches;
- release source, repository state, packages, checksums, SBOM, and provenance
  are reviewable.

Hardening must be tested against developer workflows. Avoid controls that break
debuggers or containers globally; apply stricter policies to individual services.
