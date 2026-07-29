# Architecture

LuigiOS is an Archiso composition layered on the official CachyOS Live ISO
source at the immutable commit in `sdk/versions.env`.

The source flow is:

1. `tools/sdk bootstrap` checks out the exact upstream commit.
2. `tools/sdk prepare` copies the upstream Archiso profile and replaces its
   package roots, product metadata, overlay, services, and desktop payload.
3. `tools/package-lock` resolves the entire pacman dependency graph and records
   package versions, repositories, filenames, URLs, and SHA-256 digests.
4. `tools/sdk fetch` creates a content-verified package cache.
5. `tools/sdk stage` proves that the locked cache alone resolves the entire
   image, creates its repository database, and embeds it into the live profile.
6. `tools/sdk image` invokes `mkarchiso` from that staged profile with a pinned
   `SOURCE_DATE_EPOCH`; it performs no source checkout or package resolution.

The image has one graphical stack: COSMIC plus `cosmic-greeter`. Product
configuration is declarative in `product/cachyos`; installed files are supplied
through its `overlay` tree. First boot enables only the audited service set and
applies system branding. Each user's first COSMIC login applies desktop, icon,
terminal, and Code - OSS defaults without replacing unrelated editor settings.

Release reproducibility has three boundaries: an immutable upstream Git commit,
hashed repository databases, and a content-addressed package closure. A build
from moving mirrors is useful for development but is never a release artifact.

Decentralized networking is a separate product plane. TUF metadata authorizes
release objects; peers, web seeds, and OCI registries only deliver untrusted
bytes. The opt-in peer is confined to a dedicated cache and unprivileged account.
Personal Syncthing operation is deliberately separate from release distribution.
