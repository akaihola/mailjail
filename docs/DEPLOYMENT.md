# mailjail Deployment Guide

This guide covers deploying mailjail as a systemd user service using home-manager (for NixOS) or direct systemd configuration.

## Table of Contents

- [systemd User Service](#systemd-user-service)
- [home-manager Integration](#home-manager-integration)
  - [Simple Setup (Recommended)](#simple-setup-recommended)
  - [Full Nix Package Setup](#full-nix-package-setup)
- [Configuration](#configuration)
- [Management](#management)
- [Troubleshooting](#troubleshooting)

## systemd User Service

### Installation

Copy the systemd service file to your user systemd directory:

```bash
mkdir -p ~/.config/systemd/user
cp docs/mailjail.service ~/.config/systemd/user/
```

### Configuration

Edit the service file if needed. The default paths assume:
- mailjail code at `~/.local/share/mailjail/`
- Configuration at `~/.config/mailjail/config.toml`
- Thunderbird profiles at `~/.thunderbird/`

To use a custom venv location, replace `%h/.local/share/mailjail/venv/bin/python` with your Python path:

```bash
which python  # If you have a venv activated
```

### Starting the Service

```bash
# Reload systemd daemon to pick up new service
systemctl --user daemon-reload

# Start the service
systemctl --user start mailjail

# Enable auto-start on login
systemctl --user enable mailjail

# Check status
systemctl --user status mailjail

# View logs
journalctl --user -u mailjail -f
```

## home-manager Integration

### Using the Official Module (Recommended)

The canonical way to integrate mailjail is using the official home-manager module at `nix/home-manager-module.nix`. This provides proper security hardening, flexible configuration options, and is actively maintained.

**Prerequisites:** You need to provide a mailjail package. Choose one:

**Development (using `uv run` from source):**

```nix
# ~/.config/home-manager/home.nix
{
  imports = [ /path/to/mailjail/nix/home-manager-module.nix ];

  services.mailjail = {
    enable = true;
    package = pkgs.runCommand "mailjail-dev" { nativeBuildInputs = [ pkgs.uv ]; } ''
      mkdir -p $out/bin
      cat > $out/bin/python <<'EOF'
      #!/usr/bin/env bash
      cd "$HOME/prg/mailjail"
      exec ${pkgs.uv}/bin/uv run python "$@"
      EOF
      chmod +x $out/bin/python
    '';
    serverHost = "127.0.0.1";
    serverPort = 8895;
    logLevel = "INFO";
  };
}
```

**From nixpkgs (when available):**

```nix
services.mailjail = {
  enable = true;
  package = pkgs.mailjail;
};
```

**From a flake input:**

```nix
services.mailjail = {
  enable = true;
  package = inputs.mailjail.packages.${pkgs.system}.mailjail;
};
```

Then apply:

```bash
home-manager switch
systemctl --user start mailjail
```

### Example Configurations

See the docs for reference implementations:
- `home-manager-simple-example.nix` — Development setup with local source
- `home-manager-example.nix` — Full module usage example

## Configuration

### Basic config.toml

Create `~/.config/mailjail/config.toml`:

```toml
primary_account = "personal"

[server]
host = "127.0.0.1"
port = 8895

[accounts.personal]
host = "imap.example.com"
port = 993
ssl = true
username = "user@example.com"
drafts_folder = "Drafts"

[accounts.personal.auth]
provider = "thunderbird"
thunderbird_dir = "/home/user/.thunderbird"
thunderbird_profile = "default"

[accounts.personal.pool]
size = 3
```

### Multi-Account Setup

Add multiple account sections:

```toml
primary_account = "work"

[accounts.work]
host = "mail.company.com"
port = 993
ssl = true
username = "you@company.com"
drafts_folder = "Drafts"

[accounts.work.auth]
provider = "thunderbird"
thunderbird_dir = "/home/user/.thunderbird"
thunderbird_profile = "default"

[accounts.personal]
host = "imap.gmail.com"
port = 993
ssl = true
username = "you@gmail.com"
drafts_folder = "[Gmail]/Drafts"

[accounts.personal.auth]
provider = "thunderbird"
thunderbird_dir = "/home/user/.thunderbird"
thunderbird_profile = "default"
```

For more details, see [DESIGN.md](../DESIGN.md) §9 (Authentication).

## Management

### Using systemd Commands

```bash
# Start/stop
systemctl --user start mailjail
systemctl --user stop mailjail
systemctl --user restart mailjail

# View status
systemctl --user status mailjail

# View logs
journalctl --user -u mailjail -f           # Follow logs
journalctl --user -u mailjail --since="1 hour ago"  # Last hour
journalctl --user -u mailjail -e           # Jump to end

# Enable/disable auto-start
systemctl --user enable mailjail
systemctl --user disable mailjail
```

### health endpoint

Check account IMAP connectivity:

```bash
curl http://127.0.0.1:8895/healthz | jq .
```

Example output:

```json
{
  "status": "ok",
  "accounts": {
    "work": {"imap": "connected"},
    "personal": {"imap": "connected"}
  }
}
```

### JMAP Testing

Test JMAP access (requires `jq` and `curl`):

```bash
# Get session info
curl -s http://127.0.0.1:8895/.well-known/jmap | jq .

# List mailboxes for an account
curl -s http://127.0.0.1:8895/jmap \
  -H 'Content-Type: application/json' \
  -d '{
    "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
    "methodCalls": [["Mailbox/get", {"accountId": "work"}, "c1"]]
  }' | jq .
```

## Troubleshooting

### Service fails to start

Check the error:

```bash
systemctl --user status mailjail
journalctl --user -u mailjail -e
```

Common issues:

**"Command not found: python"**
- Update the `ExecStart` path in the service file
- Run `which python` to find the correct path
- If using a venv, use the venv's Python

**"Address already in use"**
- mailjail is already running on port 8895
- Stop the existing service: `systemctl --user stop mailjail`
- Or use a different port in `config.toml` and update systemd/home-manager config

**"No such file or directory: ~/.config/mailjail/config.toml"**
- Create the config file: `mkdir -p ~/.config/mailjail`
- Add a valid `config.toml` with at least one account

### IMAP Connection Failures

Check account status:

```bash
curl http://127.0.0.1:8895/healthz | jq .accounts
```

Common issues and solutions:

**"DISCONNECTED"**
- Check `config.toml` for correct hostname/port/username
- Verify Thunderbird can connect to the account
- Check firewall rules (port 993 for IMAPS)
- Review logs: `journalctl --user -u mailjail -e`

**"SSL: SSLV3_ALERT_HANDSHAKE_FAILURE"**
- Server may not support the configured TLS version
- Try disabling TLS temporarily for testing (not recommended for production)
- Check if server requires a non-standard port

**"Authentication failed"**
- Verify credentials in Thunderbird
- If using Gmail: may require an app-specific password
- Check if Thunderbird NSS decryption is working

### Configuration Changes Not Taking Effect

After editing `config.toml`:

```bash
systemctl --user restart mailjail
journalctl --user -u mailjail -e  # Check for errors
```

### High Memory Usage

mailjail has default limits:
- `MemoryMax=256M` in systemd service
- `CPUQuota=50%` (half of one core)

Adjust these in the service file or home-manager config if needed:

```bash
# For systemd: edit ~/.config/systemd/user/mailjail.service
# For home-manager: set systemd.user.services.mailjail.Service.MemoryMax
```

## Security Considerations

The systemd service includes security hardening:

- `PrivateTmp`: Isolated /tmp
- `ProtectSystem=strict`: Read-only /usr, /etc
- `ProtectHome=true`: Read-only home (except config paths)
- `NoNewPrivileges=true`: Cannot gain new capabilities
- `MemoryMax=256M`: Memory limit prevents runaway processes

Credentials are:
- Stored in `~/.config/mailjail/` (mode 600)
- Decrypted on-demand from Thunderbird profiles
- Never exposed in environment variables
- Only accessible to the user running the service

For production deployments, consider:
- Running as a dedicated user (not your main account)
- Using a separate Thunderbird profile for mailjail
- Restricting network access with firewall rules
- Regular backups of `~/.config/mailjail/`

## See Also

- [DESIGN.md](../DESIGN.md) — Architecture and security model
- [README.md](../README.md) — Quick start guide
- [Configuration documentation](../DESIGN.md#9-credential-management) — Detailed config options
