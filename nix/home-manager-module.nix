# Home Manager module for the mailjail user service.
#
# Wire this into your Home Manager configuration with e.g.::
#
#     imports = [ /path/to/mailjail/nix/home-manager-module.nix ];
#     services.mailjail = {
#       enable = true;
#       package = pkgs.callPackage ./. { };  # or your own derivation
#       configFile = "${config.xdg.configHome}/mailjail/config.toml";
#     };
#
# The unit listens on 127.0.0.1 only and is sandboxed with the strongest
# systemd hardening flags that still allow outbound IMAPS.
{ config, lib, pkgs, ... }:

let
  cfg = config.services.mailjail;
in
{
  options.services.mailjail = {
    enable = lib.mkEnableOption "mailjail JMAP-over-IMAP proxy";

    package = lib.mkOption {
      type = lib.types.package;
      description = "The mailjail package to run.";
    };

    configFile = lib.mkOption {
      type = lib.types.str;
      default = "${config.xdg.configHome}/mailjail/config.toml";
      description = ''
        Path to the TOML configuration file. The file must contain at
        least one [accounts.<id>] section and a primary_account key.
      '';
    };

    serverHost = lib.mkOption {
      type = lib.types.str;
      default = "127.0.0.1";
      description = ''
        Bind host. Overrides server_host in the TOML via the
        MAILJAIL_SERVER_HOST environment variable. Keep this as
        127.0.0.1 unless you know what you are exposing.
      '';
    };

    serverPort = lib.mkOption {
      type = lib.types.port;
      default = 8895;
      description = ''
        Bind port. Overrides server_port in the TOML via the
        MAILJAIL_SERVER_PORT environment variable.
      '';
    };

    logLevel = lib.mkOption {
      type = lib.types.enum [ "DEBUG" "INFO" "WARNING" "ERROR" ];
      default = "INFO";
      description = "Python logging level for the service.";
    };
  };

  config = lib.mkIf cfg.enable {
    systemd.user.services.mailjail = {
      Unit = {
        Description = "mailjail JMAP-over-IMAP proxy";
        Documentation = "https://github.com/akaihola/mailjail";
        After = [ "network-online.target" ];
        Wants = [ "network-online.target" ];
      };

      Service = {
        Type = "simple";
        ExecStart = "${cfg.package}/bin/python -m mailjail";
        Restart = "on-failure";
        RestartSec = 5;

        Environment = [
          "MAILJAIL_CONFIG=${cfg.configFile}"
          "MAILJAIL_SERVER_HOST=${cfg.serverHost}"
          "MAILJAIL_SERVER_PORT=${toString cfg.serverPort}"
          "PYTHONUNBUFFERED=1"
          "LOG_LEVEL=${cfg.logLevel}"
        ];

        # Sandboxing — relax only what's actually needed (TLS to IMAPS).
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = "read-only";
        PrivateTmp = true;
        PrivateDevices = true;
        ProtectKernelTunables = true;
        ProtectKernelModules = true;
        ProtectControlGroups = true;
        RestrictAddressFamilies = "AF_INET AF_INET6 AF_UNIX";
        RestrictNamespaces = true;
        LockPersonality = true;
        MemoryDenyWriteExecute = true;
        SystemCallArchitectures = "native";
      };

      Install = {
        WantedBy = [ "default.target" ];
      };
    };
  };
}
