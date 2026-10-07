self:
{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.services.translation-api;
  command = [
    (lib.getExe cfg.package)
    "--port"
    (toString cfg.port)
    "--model"
    cfg.model
    "--ollama-url"
    cfg.ollamaUrl
  ];
in
{
  imports = [ (import ./options.nix self) ];
  config = lib.mkIf cfg.enable (
    lib.mkMerge [
      { home.packages = [ cfg.package ]; }
      (lib.mkIf pkgs.stdenv.isLinux {
        systemd.user.services.translation-api = {
          Unit.Description = "Local translation API backed by Ollama";
          Install.WantedBy = [ "default.target" ];
          Service = {
            ExecStart = lib.escapeShellArgs command;
            Environment = [ "PYTHONUNBUFFERED=1" ];
            Restart = "on-failure";
            RestartSec = 5;
            UMask = "0077";
          };
        };
      })
      (lib.mkIf pkgs.stdenv.isDarwin {
        home.activation.translationApiLogs = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
          run mkdir -p ${lib.escapeShellArg "${config.home.homeDirectory}/Library/Logs"}
        '';
        launchd.agents.translation-api = {
          enable = true;
          config = {
            ProgramArguments = command;
            EnvironmentVariables.PYTHONUNBUFFERED = "1";
            RunAtLoad = true;
            KeepAlive = true;
            ThrottleInterval = 5;
            Umask = 63;
            StandardOutPath = "${config.home.homeDirectory}/Library/Logs/translation-api.log";
            StandardErrorPath = "${config.home.homeDirectory}/Library/Logs/translation-api-error.log";
          };
        };
      })
    ]
  );
}
