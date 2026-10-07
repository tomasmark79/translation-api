self:
{ config, lib, ... }:
let
  cfg = config.services.translation-api;
in
{
  imports = [ (import ./options.nix self) ];
  config = lib.mkIf cfg.enable {
    systemd.user.services.translation-api = {
      description = "Local translation API backed by Ollama";
      wantedBy = [ "default.target" ];
      after = [ "network.target" ];
      serviceConfig = {
        ExecStart = lib.escapeShellArgs [
          (lib.getExe cfg.package)
          "--port"
          (toString cfg.port)
          "--model"
          cfg.model
          "--ollama-url"
          cfg.ollamaUrl
        ];
        Environment = "PYTHONUNBUFFERED=1";
        Restart = "on-failure";
        RestartSec = 5;
        UMask = "0077";
      };
    };
  };
}
