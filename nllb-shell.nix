{
  pkgs ? import <nixpkgs> { },
}:
pkgs.mkShell {
  packages = [
    (pkgs.python3.withPackages (
      ps: with ps; [
        torch
        transformers
        sentencepiece
        protobuf
        langdetect
      ]
    ))
  ];
}
