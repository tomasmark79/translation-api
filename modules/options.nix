self:
{ lib, pkgs, ... }:
{
  options.services.translation-api = {
    enable = lib.mkEnableOption "the local translation API";
    package = lib.mkOption {
      type = lib.types.package;
      default = self.packages.${pkgs.stdenv.hostPlatform.system}.default;
      description = "Translation API package to run.";
    };
    port = lib.mkOption {
      type = lib.types.port;
      default = 5001;
      description = "Port on 127.0.0.1; the API stays local.";
    };
    model = lib.mkOption {
      type = lib.types.str;
      default = "translategemma:4b";
      description = "Model already downloaded in the Ollama server.";
    };
    ollamaUrl = lib.mkOption {
      type = lib.types.str;
      default = "http://127.0.0.1:11434";
      description = "URL of an independently managed Ollama server.";
    };
  };
}
