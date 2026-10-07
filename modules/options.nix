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
    host = lib.mkOption {
      type = lib.types.str;
      default = "127.0.0.1";
      description = "Address to listen on; use 0.0.0.0 for all IPv4 interfaces.";
    };
    port = lib.mkOption {
      type = lib.types.port;
      default = 5001;
      description = "Port to listen on.";
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
