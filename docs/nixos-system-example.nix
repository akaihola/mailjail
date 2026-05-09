# NixOS system-wide configuration for mailjail
#
# Use this if you want to run mailjail as a system service
# rather than a user service. This is useful for:
# - Running mailjail for multiple users
# - Persistent availability across user logins
# - Integration with other system services
#
# Add this to your /etc/nixos/configuration.nix or a module it imports.

{ config, pkgs, lib, ... }:

{
  # Option 1: System service (runs as root or dedicated user)
  systemd.services.mailjail = {
    description = "mailjail — JMAP-shaped read-only IMAP proxy";
    documentation = [ "https://github.com/akaihola/mailjail" ];
    after = [ "network.target" ];
    wantedBy = [ "multi-user.target" ];

    serviceConfig = {
      Type = "simple";
      WorkingDirectory = "/opt/mailjail";
      ExecStart = "${pkgs.uv}/bin/uv run python -m mailjail";
      Restart = "on-failure";
      RestartSec = 10;

      # Run as dedicated mailjail user
      User = "mailjail";
      Group = "mailjail";

      # Security hardening
      PrivateTmp = true;
      NoNewPrivileges = true;
      ProtectSystem = "strict";
      ProtectHome = true;
      ReadWritePaths = [
        "/etc/mailjail"
        "/var/cache/mailjail"
        "/home"  # To access user Thunderbird profiles
      ];

      # Resource limits
      MemoryMax = "512M";
      CPUQuota = "100%";

      # Logging
      StandardOutput = "journal";
      StandardError = "journal";
      SyslogIdentifier = "mailjail";
    };

    path = with pkgs; [ python3 uv ];
  };

  # Create the dedicated user and group
  users.users.mailjail = {
    description = "mailjail IMAP proxy user";
    isSystemUser = true;
    group = "mailjail";
    home = "/var/lib/mailjail";
    createHome = true;
  };

  users.groups.mailjail = {};

  # System-wide configuration file
  environment.etc."mailjail/config.toml" = {
    mode = "0440";
    group = "mailjail";
    text = ''
      # mailjail system-wide configuration
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
    '';
  };

  # Optional: Expose mailjail to the network if needed
  networking.firewall.allowedTCPPorts = [ 8895 ];

  # For accessing Thunderbird profiles, ensure proper permissions
  security.pam.services.mailjail = {};
}
