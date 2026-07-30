# Contributing

LuigiOS is a CachyOS-derived COSMIC developer workstation with secure,
decentralized distribution.

Before sending a change:

1. Keep `product/cachyos/product.json`, package roots, services, and docs aligned.
2. Regenerate `sdk/package-lock.json` after intentional package changes.
3. Preserve the rule that transports provide bytes but never installation authority.
4. Keep peer features opt-in, resource-bounded, privacy-explicit, and confined.
5. Prefer memory-safe implementations for new privileged or network-facing code.
6. Run `./tools/ci-check` and include hardware validation for relevant changes.

Use signed commits and follow the Developer Certificate of Origin in `DCO`.
Do not add a second desktop, partial-upgrade workflow, unpinned release input, or
network daemon enabled without a documented threat model.
