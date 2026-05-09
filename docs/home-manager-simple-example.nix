# Simpler Nix home-manager configuration for mailjail
#
# This example assumes you have mailjail cloned at ~/src/mailjail
# and uses `uv run` to execute it (no packaging required).
#
# This is recommended for development or if you prefer to manage
# mailjail updates separately from home-manager.

{ config, pkgs, lib, ... }:

{
  # Systemd user service using local mailjail repository
  systemd.user.services.mailjail = {
    Unit = {
      Description = "mailjail — JMAP-shaped read-only IMAP proxy";
      After = [ "network.target" ];
      Documentation = "https://github.com/akaihola/mailjail";
    };

    Service = {
      Type = "simple";
      # Using uv run directly from the mailjail directory
      WorkingDirectory = "%h/src/mailjail";
      ExecStart = "${pkgs.uv}/bin/uv run python -m mailjail";
      Restart = "on-failure";
      RestartSec = 10;

      # Security hardening
      PrivateTmp = true;
      NoNewPrivileges = true;
      ProtectSystem = "strict";
      ProtectHome = true;
      ReadWritePaths = [
        "${config.home.homeDirectory}/.config/mailjail"
        "${config.home.homeDirectory}/.cache/mailjail"
        "${config.home.homeDirectory}/.thunderbird"
      ];

      # Resource limits
      MemoryMax = "256M";
      CPUQuota = "50%";

      # Logging
      StandardOutput = "journal";
      StandardError = "journal";
      SyslogIdentifier = "mailjail";
    };

    Install = {
      WantedBy = [ "default.target" ];
    };
  };

  # Configuration file
  home.file.".config/mailjail/config.toml" = {
    text = ''
      # mailjail configuration
      # For Thunderbird account examples, see:
      # https://github.com/akaihola/mailjail/blob/main/DESIGN.md

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
      thunderbird_dir = "${config.home.homeDirectory}/.thunderbird"
      thunderbird_profile = "default"

      [accounts.personal.pool]
      size = 3
    '';
  };

  # Convenience aliases
  programs.bash.shellAliases = {
    mj-status = "systemctl --user status mailjail";
    mj-logs = "journalctl --user -u mailjail -f";
    mj-restart = "systemctl --user restart mailjail";
    mj-test = "curl -s http://127.0.0.1:8895/.well-known/jmap | jq .";
  };

  # Optional: zsh aliases
  programs.zsh.shellAliases = {
    mj-status = "systemctl --user status mailjail";
    mj-logs = "journalctl --user -u mailjail -f";
    mj-restart = "systemctl --user restart mailjail";
    mj-test = "curl -s http://127.0.0.1:8895/.well-known/jmap | jq .";
  };
}
