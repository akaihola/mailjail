# Home-manager configuration example for mailjail
#
# ⚠️  DEPRECATED: Use the official home-manager module instead
#     See: nix/home-manager-module.nix
#
# This example is provided for reference only. The official module provides:
# - Proper Nix packaging
# - Stronger security hardening
# - Flexible configuration options
# - Better maintenance
#
# See DEPLOYMENT.md for instructions on using the official module.

{ config, pkgs, lib, ... }:

{
  imports = [ ../nix/home-manager-module.nix ];

  services.mailjail = {
    enable = true;
    package = pkgs.callPackage ../nix/default.nix {};  # Requires a default.nix
    serverHost = "127.0.0.1";
    serverPort = 8895;
    logLevel = "INFO";
  };

  # Create the configuration file
  home.file.".config/mailjail/config.toml" = {
    text = ''
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

  # Shell aliases for convenience
  programs.bash.shellAliases = {
    mj-status = "systemctl --user status mailjail";
    mj-logs = "journalctl --user -u mailjail -f";
  };
}
