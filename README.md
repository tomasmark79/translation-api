# Translation API

Local asynchronous translation API for DiMeTrans, CzEn Composer and TranslatePlace.
The Nix package runs on Linux, Intel macOS (`x86_64-darwin`) and Apple Silicon
macOS (`aarch64-darwin`). It provides the `translation-api` command and optional
NixOS and Home Manager service modules.

The lock file uses nixpkgs 26.05, the last nixpkgs release supporting Intel
macOS. Keep that constraint in mind when updating nixpkgs or making this input
follow a host configuration's nixpkgs.

The repository is private. Every user needs GitHub access to it and an SSH key
registered with GitHub. The commands below use authenticated Git over SSH;
they do not require storing a GitHub token in a Nix configuration.

## Start on Linux or macOS

Install [Nix](https://nixos.org/download/) with the `nix-command` and `flakes`
experimental features enabled. Install and start [Ollama](https://ollama.com/download)
separately, then download the translation model:

```sh
ollama pull translategemma:4b
ollama list
nix run 'git+ssh://git@github.com/tomasmark79/translation-api?ref=main'
```

The API listens on `127.0.0.1:5001` by default. Keep the command running while using a client.
If Ollama is installed as a CLI without a background service, first run
`ollama serve` in another terminal. The package does not install Ollama, download
models, select a GPU backend or change system permissions.

Ollama's current macOS requirements are macOS 14 or newer. Apple M series supports
CPU and GPU inference; Intel uses CPU inference. These are requirements of the
Ollama backend, rather than the Python API. See the
[official macOS documentation](https://docs.ollama.com/macos).

Install the command persistently:

```sh
nix profile add 'git+ssh://git@github.com/tomasmark79/translation-api?ref=main'
translation-api
```

Select a different Ollama server, model, listening address or port:

```sh
translation-api --ollama-url http://127.0.0.1:11434 --model translategemma:4b --port 5001
translation-api --help
curl http://127.0.0.1:5001/health
```

To listen on all IPv4 interfaces at `0.0.0.0:5001`:

```sh
translation-api --host 0.0.0.0 --port 5001
# Or pass arguments directly through nix run:
nix run 'git+ssh://git@github.com/tomasmark79/translation-api?ref=main' -- --host 0.0.0.0 --port 5001
```

Run only one API instance on a given port. All job state lives in memory;
restarting the API discards pending jobs and results.

## Automatic startup with Home Manager

Add the input to your flake:

```nix
inputs.translation-api = {
  url = "git+ssh://git@github.com/tomasmark79/translation-api?ref=main";
  inputs.nixpkgs.follows = "nixpkgs";
};
```

Add the module to your Home Manager modules and enable the service:

```nix
modules = [
  translation-api.homeManagerModules.default
  {
    services.translation-api = {
      enable = true;
      model = "translategemma:4b";
      ollamaUrl = "http://127.0.0.1:11434";
      host = "127.0.0.1"; # Use "0.0.0.0" to listen on all IPv4 interfaces.
      port = 5001;
    };
  }
];
```

Home Manager creates a user systemd service on Linux and a user launchd agent on
macOS. Ollama must still be configured and the model downloaded independently.
The service retries if Ollama is not ready at login. On macOS, inspect the agent
with `launchctl list | grep translation-api`; logs are in
`~/Library/Logs/translation-api.log` and `~/Library/Logs/translation-api-error.log`.
On Linux, use `systemctl --user status translation-api` and
`journalctl --user -u translation-api`.

For NixOS without Home Manager, import `translation-api.nixosModules.default`
and set `services.translation-api.enable = true`. It creates a user systemd
service with the same options. Enable only one module for a given user and port.

## HTTP API

- `GET /health`: returns `status`, `backend`, `model` and `device`.
- `POST /translate`: accepts `{"q":"Hello","source":"en","target":"cs"}`;
  returns HTTP 202 with `jobId` and `status: pending`.
- `GET /translations/<jobId>`: returns `pending` with `partialText`, `done` with
  `translatedText` and `detectedLanguage`, or `failed` with `error`.

`source` defaults to `auto`, `target` to `cs`. Supported language codes are listed
in `LANGUAGES` in `server.py`. Text is limited to 10,000 characters. One worker
processes up to eight queued/running jobs in order. Results expire after ten
minutes when another job is submitted, and retained jobs are capped at 128.

The listener defaults to loopback; `--host` (or the service's `host` option)
changes the listening address. Web page origins are rejected; Chrome extensions
call it from their service workers. Native local clients can call it without an
Origin header. It has no remote-access authentication. Request text and
translations are not written to HTTP logs.

## Development and validation

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
