# ADR 0001: decentralized distribution

Status: accepted

Decentralized networking is a defining LuigiOS capability. Peers may provide
storage, discovery, and bandwidth, but never installation authority.

Release authorization follows TUF's threshold roles, expiration, consistent
snapshots, and rollback protection. BitTorrent v2 is the preferred immutable
bulk transport; HTTPS web seeds and OCI Distribution are independent fallbacks.
Every reconstructed target must match its authorized digest before pacman or an
installer can consume it.

Build attestations use SLSA provenance, Sigstore bundles, and SPDX SBOMs. A
release is promoted between channels by retaining the same artifact digest,
never by rebuilding it.

Peer participation is off by default. Enabling it never implies anonymity:
public DHT and peer exchange remain separate explicit choices. Seeding is off on
battery and metered links, uses rotating per-swarm identities, and cannot
include stable hardware or account identifiers.

The peer runs as `luigios-peer` with a read-only system, no home access, reduced
kernel and privilege surfaces, and one writable content-addressed cache at
`/var/cache/luigios/objects`. It cannot scan arbitrary user files. Personal
device synchronization uses a distinct, user-controlled Syncthing process and
never shares the release cache or trust root.

The initial rebase ships the confined transport and supply-chain tools. Release
installation continues through signed CachyOS/pacman full transactions until
the TUF client, metadata repository, and promotion ceremony pass integration
qualification; transport must not get ahead of the authorization boundary.
