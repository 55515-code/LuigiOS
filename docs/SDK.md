# LuigiOS SDK

The LuigiOS SDK is a defining product feature alongside decentralized
networking. Its purpose is to make OS development unusually approachable:
contributors should be able to understand, customize, test, and propose a
change without learning undocumented maintainer rituals or granting a build
container unrestricted access to their host.

## What exists now

`tools/sdk` remains the canonical entrypoint. It already provides:

- dependency and workstation diagnostics;
- pinned CachyOS source bootstrap;
- exact package-lock generation;
- verified package-cache fetching;
- Archiso profile preparation and offline staging;
- product and contract validation;
- rootless, network-disconnected VM image assembly;
- development-image assembly;
- completed-ISO inspection and checksum generation.

These capabilities must be extended rather than replaced. Release construction
and workstation customization are different workflows and should not be
collapsed into one unsafe command.

## Contributor contract

Every SDK surface should be:

- discoverable through `tools/sdk help` and task-specific help;
- rootless by default, using a container or VM where isolation is useful;
- declarative and reviewable before it changes a system;
- deterministic whenever inputs can be pinned;
- safe to rerun;
- explicit about host, image, VM, and remote deployment targets;
- capable of producing a machine-readable report;
- tested by the same validation path used in CI.

Normal contribution should not require a terminal `sudo` workflow. An
unavoidable host-level operation must be isolated, explained in advance, and
requested through a graphical PolicyKit flow.

## Stretch goal: customization and deployment

The stretch SDK adds a shared, versioned workstation-profile schema with three
separate consumers:

1. **Image customization** composes an ISO or installed-system overlay.
2. **Local setup** plans and applies a profile to a LuigiOS workstation.
3. **Deployment** delivers the same reviewed profile to a VM or managed
   workstation.

The profile should cover package intents, system and user services, COSMIC
settings, icons and branding, terminal and Code OSS configuration, container
defaults, security policy, and opt-in decentralized services. Generated state
must not silently overwrite hand-maintained user files.

A proposed command model is:

```text
tools/sdk init NAME
tools/sdk profile validate PROFILE
tools/sdk profile plan PROFILE --target vm
tools/sdk profile test PROFILE
tools/sdk profile apply PROFILE --target local
tools/sdk deploy PROFILE --target TARGET
tools/sdk report PATH
```

`plan` and `test` are mandatory gates before `apply` or `deploy`. Local host
application is never implied by building an image.

## Implementation phases

### Phase 1 — inviting contributions

- Stable help output and command documentation.
- A contributor template with a minimal profile and tests.
- One command that runs formatting, schemas, contracts, and focused tests.
- Actionable diagnostics that identify the exact missing dependency or stale
  generated input.

### Phase 2 — profile model

- JSON Schema for the workstation profile.
- Canonical normalization and a human-readable plan.
- Conflict detection for packages, services, and owned configuration files.
- Dry-run fixtures covering COSMIC, terminal, icons, Code OSS, Podman, and
  security defaults.

### Phase 3 — isolated application

- Rootless Podman test environment for filesystem/configuration operations.
- UEFI VM integration test for changes affecting boot, services, or the
  desktop session.
- Snapshot-aware local application with rollback metadata.

### Phase 4 — deployment

- VM deployment first, followed by explicitly enrolled physical workstations.
- Signed profile bundles and provenance tied to LuigiOS release authority.
- Transport independent of authorization: HTTPS, OCI, or peer delivery may
  move bytes, but cannot make a profile trusted.
- Fleet reports that expose drift without enabling telemetry by default.

## Non-goals

- Replacing established tools such as Archiso, pacman, Podman, systemd,
  Calamares, or configuration-format parsers.
- Turning the SDK into an always-running privileged daemon.
- Hiding destructive actions behind a one-click setup command.
- Coupling profile trust to BitTorrent, OCI, Syncthing, or any other transport.
