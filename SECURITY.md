# Security policy

Report vulnerabilities privately to the project maintainers before public
disclosure. Include affected version, reproducible steps, impact, and a minimal
proof of concept. Do not attach credentials, private keys, tokens, or personal
logs.

High-priority areas are release authorization, signature or rollback bypass,
package-lock substitution, privilege escalation, sandbox escape, peer cache
exposure, stable identity leakage, and unauthorized user-file access.

Release transports are untrusted. A peer, tracker, mirror, web seed, or OCI
registry must not decide what the system installs. Current system updates retain
CachyOS/pacman signature verification; the planned decentralized release client
must pass TUF integration and recovery qualification before it can stage updates.
