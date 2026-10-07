# Deployment options

[Back to the quick start](../README.md).

## Persistent Nix command and configuration

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

Windows users can pass the same options to `py server.py`, for example:

```powershell
py server.py --port 5002 --model translategemma:4b
```

When changing the API port, update the client settings to match. The API has no
remote-access authentication; the default loopback address is intended for
clients on the same computer.

## Automatic startup with Home Manager

Add the input to your flake:

```nix
inputs.translation-api = {
  url = "git+ssh://git@github.com/tomasmark79/translation-api?ref=main";
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
On macOS, inspect the agent with `launchctl list | grep translation-api`; logs are in
`~/Library/Logs/translation-api.log` and `~/Library/Logs/translation-api-error.log`.
On Linux, use `systemctl --user status translation-api` and
`journalctl --user -u translation-api`.

For NixOS without Home Manager, import `translation-api.nixosModules.default`
and set `services.translation-api.enable = true`. It creates a user systemd
service with the same options. Enable only one module for a given user and port.


## Nix input compatibility

The lock file uses nixpkgs 26.05, the last nixpkgs release supporting Intel
macOS. Keep that constraint in mind when updating nixpkgs or making this input
follow a host configuration's nixpkgs.

If you make this input follow your host configuration's nixpkgs, use a version
that supports your platform.
