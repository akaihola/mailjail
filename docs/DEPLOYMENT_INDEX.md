# mailjail Deployment Files Index

This directory contains deployment configuration examples for running mailjail as a service.

## Quick Reference

| File | Use Case | Best For |
|------|----------|----------|
| **[mailjail.service](mailjail.service)** | Direct systemd user service | Non-NixOS systems, simple setup |
| **[home-manager-simple-example.nix](home-manager-simple-example.nix)** | NixOS home-manager setup | Most NixOS users, development |
| **[home-manager-example.nix](home-manager-example.nix)** | Full declarative NixOS setup | Advanced users, full Nix integration |
| **[nixos-system-example.nix](nixos-system-example.nix)** | NixOS system service | Multi-user or always-on deployments |
| **[DEPLOYMENT.md](DEPLOYMENT.md)** | Complete deployment guide | All setup methods, troubleshooting |

## Getting Started

### For Non-NixOS Users

1. Copy `mailjail.service` to `~/.config/systemd/user/`
2. Create `~/.config/mailjail/config.toml`
3. Run `systemctl --user daemon-reload && systemctl --user start mailjail`
4. See [DEPLOYMENT.md](DEPLOYMENT.md#systemd-user-service) for details

### For NixOS with home-manager (Recommended)

1. Use `home-manager-simple-example.nix`
2. Add to your home-manager configuration
3. Run `home-manager switch`
4. See [DEPLOYMENT.md](DEPLOYMENT.md#simple-setup-recommended) for details

### For Full NixOS Integration

1. For user service: `home-manager-example.nix`
2. For system service: `nixos-system-example.nix`
3. See [DEPLOYMENT.md](DEPLOYMENT.md) for complete guide

## File Descriptions

### mailjail.service

Standard systemd user service file for any Linux system with systemd.

**Features:**
- Type=simple for single-process service
- Restart=on-failure with 10-second retry
- Security hardening (PrivateTmp, ProtectSystem, NoNewPrivileges)
- Resource limits (256M RAM, 50% CPU)
- Read-write access to config, cache, and Thunderbird profiles

**Setup:**
```bash
mkdir -p ~/.config/systemd/user
cp mailjail.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now mailjail
```

### home-manager-simple-example.nix

Minimal home-manager configuration using local mailjail repository.

**Features:**
- Uses `uv run` to execute mailjail
- Minimal boilerplate
- Creates `~/.config/mailjail/config.toml`
- Adds convenience bash/zsh aliases
- Automatic restart on config changes

**Setup:**
1. Clone mailjail to `~/src/mailjail` (or adjust path in config)
2. Copy example into home-manager configuration
3. Run `home-manager switch`

### home-manager-example.nix

Full declarative home-manager configuration with optional features.

**Features:**
- Builds mailjail as a Nix package
- Includes socket activation (optional)
- Enhanced security settings
- Multi-account configuration examples
- Management script at `~/.local/bin/mailjail-ctl`
- Complete documentation

**Best for:** Advanced NixOS users who want full declarative control

### nixos-system-example.nix

NixOS system service configuration for system-wide deployment.

**Features:**
- Runs as dedicated `mailjail` system user
- Always available (doesn't depend on user login)
- System firewall integration
- Multi-user access scenarios
- Shared Thunderbird profile access

**Setup:**
1. Add module to `/etc/nixos/configuration.nix`
2. Run `nixos-rebuild switch`
3. Service starts automatically on boot

## Common Tasks

### Install and Start

**Systemd (non-NixOS):**
```bash
cp mailjail.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now mailjail
```

**Home-manager:**
```bash
# Add example to ~/home-manager/home.nix, then:
home-manager switch
systemctl --user start mailjail
```

### Check Status

```bash
# View service status
systemctl --user status mailjail

# Check IMAP connectivity
curl http://127.0.0.1:8895/healthz | jq .

# Follow logs
journalctl --user -u mailjail -f
```

### Restart After Config Changes

```bash
# Manually
systemctl --user restart mailjail

# Or (if using home-manager with onChange):
home-manager switch
```

### Test JMAP Access

```bash
# Get session info
curl -s http://127.0.0.1:8895/.well-known/jmap | jq .

# List accounts
curl -s http://127.0.0.1:8895/.well-known/jmap | jq .accounts

# Query mailboxes
curl -s http://127.0.0.1:8895/jmap \
  -H 'Content-Type: application/json' \
  -d '{
    "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
    "methodCalls": [["Mailbox/get", {"accountId": "personal"}, "c1"]]
  }' | jq .
```

## Security Notes

All configurations include security hardening:

- **Credential isolation**: Passwords stored in `~/.config/mailjail/` (mode 600)
- **System hardening**: ProtectSystem, PrivateTmp, NoNewPrivileges
- **Resource limits**: Memory and CPU quotas to prevent runaway processes
- **Access control**: Restricted file access via ReadWritePaths

For production use:
- Consider running as a dedicated user (not your main account)
- Use a separate Thunderbird profile for mailjail
- Restrict network access with firewall rules if not needed system-wide
- Regularly back up `~/.config/mailjail/`

## Troubleshooting

See [DEPLOYMENT.md#troubleshooting](DEPLOYMENT.md#troubleshooting) for:
- Service fails to start
- IMAP connection failures
- Configuration changes not taking effect
- High memory/CPU usage
- Credential issues

## See Also

- [README.md](../README.md) — Quick start and overview
- [DESIGN.md](../DESIGN.md) — Architecture and security model
- [DEPLOYMENT.md](DEPLOYMENT.md) — Comprehensive deployment guide
- [../docs/plans/](./plans/) — Implementation tasks and status
