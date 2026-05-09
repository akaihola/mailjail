# Development setup: Using the official module with local mailjail repo
#
# This shows how to use the official module when developing mailjail.
# It uses `uv run` to execute from the source directory.
#
# Prerequisites:
#   - mailjail cloned at ~/prg/mailjail (or adjust path below)
#   - uv installed

{ config, pkgs, lib, ... }:

let
  mailjailSrc = "${config.home.homeDirectory}/prg/mailjail";
in {
  imports = [ "${mailjailSrc}/nix/home-manager-module.nix" ];

  services.mailjail = {
    enable = true;
    # Package wraps `uv run` to execute from the repo directory
    package = pkgs.runCommand "mailjail-dev" { nativeBuildInputs = [ pkgs.uv ]; } ''
      mkdir -p $out/bin
      cat > $out/bin/python <<'EOF'
      #!/usr/bin/env bash
      cd "${mailjailSrc}"
      exec ${pkgs.uv}/bin/uv run python "$@"
      EOF
      chmod +x $out/bin/python
    '';
    serverHost = "127.0.0.1";
    serverPort = 8895;
    logLevel = "INFO";
  };

  # Configuration file
  home.file.".config/mailjail/config.toml" = {
    text = ''
      # mailjail configuration
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
    mj-test = "curl -s http://127.0.0.1:8895/.well-known/jmap | ${pkgs.jq}/bin/jq .";
  };

  programs.zsh.shellAliases = {
    mj-status = "systemctl --user status mailjail";
    mj-logs = "journalctl --user -u mailjail -f";
    mj-test = "curl -s http://127.0.0.1:8895/.well-known/jmap | ${pkgs.jq}/bin/jq .";
  };
}
