# mailjail Deployment — Quick Start

## 🚀 Choose Your Setup

### Option A: Non-NixOS (systemd)
```bash
mkdir -p ~/.config/systemd/user
cp mailjail.service ~/.config/systemd/user/

# Create config
mkdir -p ~/.config/mailjail
cat > ~/.config/mailjail/config.toml <<'EOF'
primary_account = "personal"
[server]
host = "127.0.0.1"
port = 8895
[accounts.personal]
host = "imap.example.com"
port = 993
ssl = true
username = "you@example.com"
[accounts.personal.auth]
provider = "thunderbird"
thunderbird_dir = "$HOME/.thunderbird"
thunderbird_profile = "default"
[accounts.personal.pool]
size = 3
EOF

# Start
systemctl --user daemon-reload
systemctl --user enable --now mailjail
```

### Option B: NixOS + home-manager (Recommended)

Use the **official home-manager module**:

```bash
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
  };
}

# Apply
home-manager switch

# Start
systemctl --user start mailjail
```

See [DEPLOYMENT.md](DEPLOYMENT.md#using-the-official-module-recommended) for full instructions and package options.

### Option C: NixOS System Service
```bash
# Add to /etc/nixos/configuration.nix:
imports = [ (import "${mailjail}/docs/nixos-system-example.nix") ];

# Apply
sudo nixos-rebuild switch
```

## 📋 Essential Commands

```bash
# Status
systemctl --user status mailjail

# Logs
journalctl --user -u mailjail -f

# Health check (accounts & IMAP connectivity)
curl http://127.0.0.1:8895/healthz | jq .

# Test JMAP
curl -s http://127.0.0.1:8895/.well-known/jmap | jq .accounts
```

## 📁 Configuration File

Location: `~/.config/mailjail/config.toml`

```toml
primary_account = "personal"

[server]
host = "127.0.0.1"
port = 8895

# Add accounts
[accounts.personal]
host = "imap.gmail.com"
port = 993
ssl = true
username = "you@gmail.com"
drafts_folder = "[Gmail]/Drafts"

[accounts.personal.auth]
provider = "thunderbird"
thunderbird_dir = "/home/you/.thunderbird"
thunderbird_profile = "default"

[accounts.personal.pool]
size = 3
```

## 🔧 Troubleshooting

| Issue | Solution |
|-------|----------|
| Port already in use | Change port in config.toml |
| "Command not found" | Update ExecStart path in service file |
| IMAP connection failed | Run `curl http://127.0.0.1:8895/healthz \| jq .` to see which accounts are disconnected |
| Auth failed | Verify credentials in Thunderbird; Gmail needs app-specific password |
| Config not picked up | Restart: `systemctl --user restart mailjail` |

## 📖 Full Documentation

- **Setup guide**: [DEPLOYMENT.md](DEPLOYMENT.md)
- **File descriptions**: [DEPLOYMENT_INDEX.md](DEPLOYMENT_INDEX.md)
- **Architecture**: [../DESIGN.md](../DESIGN.md)
- **Overview**: [../README.md](../README.md)

## ✅ Verify It Works

```bash
# Should show "ok" status
curl http://127.0.0.1:8895/healthz | jq .status

# Should list your accounts
curl http://127.0.0.1:8895/.well-known/jmap | jq '.accounts | keys'

# Test with your first account (replace "personal" if different)
curl -s http://127.0.0.1:8895/jmap \
  -H 'Content-Type: application/json' \
  -d '{
    "using": ["urn:ietf:params:jmap:core","urn:ietf:params:jmap:mail"],
    "methodCalls": [["Mailbox/get",{"accountId":"personal"},"m"]]
  }' | jq .methodResponses[0][1].list[0].name
```

If you see a mailbox name (like "INBOX"), mailjail is working! 🎉
