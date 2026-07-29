#!/usr/bin/env bash
set -euo pipefail

install -m 0644 /usr/share/calamares/settings_online.conf \
    /etc/calamares/settings.conf
exec pkexec-wrapper calamares -D6
