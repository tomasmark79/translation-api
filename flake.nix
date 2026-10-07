{
  description = "Local translation API for Linux and macOS";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
    in
    {
      packages = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        rec {
          translation-api = pkgs.callPackage ./package.nix { };
          default = translation-api;
        }
      );
      apps = forAllSystems (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/translation-api";
          meta.description = "Local translation API backed by Ollama";
        };
      });
      checks = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        {
          package = self.packages.${system}.default;
          api =
            pkgs.runCommand "translation-api-smoke"
              {
                nativeBuildInputs = [ pkgs.python3 ];
              }
              ''
                python ${./tests/smoke.py} ${self.packages.${system}.default}/bin/translation-api
                touch "$out"
              '';
        }
      );
      devShells = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        {
          default = pkgs.mkShell {
            packages = [
              (pkgs.python3.withPackages (ps: [
                ps.langdetect
                ps.setuptools
              ]))
            ];
          };
        }
      );
      nixosModules.default = import ./modules/nixos.nix self;
      homeManagerModules.default = import ./modules/home-manager.nix self;
    };
}
