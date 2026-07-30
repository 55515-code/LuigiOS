# Distribution and updates

Release artifacts are ISO images produced by `tools/sdk image` from the verified
package cache. Publish the ISO, SHA-256 digest, package lock, upstream commit,
source commit, and test report together.

Installed systems use normal CachyOS full-system upgrades:

```sh
sudo pacman -Syu
```

Partial upgrades are unsupported. Snapper and `snap-pac` create recovery points
around package transactions, while `limine-snapper-sync` exposes suitable
snapshots through the boot path. Flatpak remains available for sandboxed
desktop applications, but it is not used to provide core workstation services.

## Decentralized delivery

The machine-readable trust and privacy boundary is
`profiles/distribution-v2.json`; the accepted design is
`docs/adr/0001-decentralized-distribution.md`.

Peer transport is initially disabled. After reviewing its public-IP and
bandwidth implications, an administrator can opt in with:

```sh
luigios-network enable-peer
```

The peer can write only its content-addressed object cache. DHT, peer exchange,
automatic port forwarding, battery seeding, and metered-network seeding remain
off in the shipped policy. Enabling transport does not bypass package signatures
or authorize installation.
