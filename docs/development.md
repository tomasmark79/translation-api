# Development and validation

```sh
nix develop
python -m unittest discover -s tests -p 'test_*.py'
nix flake check -L
nix build
python tests/smoke.py result/bin/translation-api
```

Package checks run unit tests without a real model. The installed-command smoke
test starts a local Ollama stub and verifies startup, health, asynchronous HTTP
translation and the trailing-whitespace regression. CI runs these checks on
Linux, Intel macOS and Apple Silicon macOS. It does not measure real model speed
or prove GPU acceleration.

The optional NLLB CPU backend remains a development option:
`nix-shell nllb-shell.nix --run 'python server.py --backend nllb'`.
Its PyTorch/Transformers dependencies are separate from the portable Ollama
package and are not covered by the cross-platform CI.

Run these commands from the repository root. Windows startup through
`server.py` has been manually confirmed by a user; Windows is not covered by
the current CI checks.

[Back to the quick start](../README.md).
