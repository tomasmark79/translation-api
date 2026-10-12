# Deployment options

[Back to the quick start](../README.md).

## Linux installation

The Bash installer uses Python 3.11+ and installs the default Ollama backend in
a user-owned virtual environment. It does not install Ollama, models, GPU drivers
or the optional NLLB backend. Install Ollama and download the model as described
in the [quick start](../README.md#before-you-start).

Install prerequisites with your distribution's package manager:

```sh
# Debian 12+ / Ubuntu 24.04+
sudo apt update
sudo apt install python3 python3-venv python3-pip git

# Fedora
sudo dnf install python3 python3-pip git

# Arch Linux / Manjaro
sudo pacman -S --needed python python-pip git
```

On other distributions, install the equivalent packages and check that
`python3 --version` reports 3.11 or newer. Then, as your regular user:

```sh
git clone https://github.com/tomasmark79/translation-api.git
cd translation-api
bash install-linux.sh
~/.local/bin/translation-api
```

Installation needs internet access to download Python dependencies. The installer
does not use sudo or modify system Python. Add `~/.local/bin` to your shell's
`PATH` to use the short command `translation-api`:

```sh
export PATH="$HOME/.local/bin:$PATH"
```

Add that line to your shell profile to keep it for future sessions.

### Configuration and automatic startup

The application is installed in `~/.local/share/translation-api/`. Its launcher
reads `~/.config/translation-api/arguments`, with one command-line argument per
line. For example, the last two lines of the default file are:

```text
--ollama-url
http://127.0.0.1:11434
```

Use no shell quoting in this file. Blank lines and lines starting with `#` are
ignored. Manual command-line options override the corresponding saved options.
The installer respects `XDG_DATA_HOME` and `XDG_CONFIG_HOME` when set; use the
same values for installation, updates and uninstalling. Keep the installation
at its original path because Python virtual environments are not portable.
Installation paths must not contain dollar signs, which Python packaging treats
as variable substitutions.

For automatic startup, run from a regular login session with user systemd:

```sh
bash install-linux.sh --service
systemctl --user status translation-api.service
journalctl --user -u translation-api.service -n 50
curl http://127.0.0.1:5001/health
```

The service starts when your user systemd session starts, normally at login.
After editing the arguments file, restart it with
`systemctl --user restart translation-api.service`. Ollama must be available
with the configured model; the API retries startup through systemd if needed.
The installer reports completion separately from API readiness: check `/health`
and request a translation in your client. Run only one API instance per port.

### Update or uninstall

From your checkout:

```sh
git pull --ff-only
bash install-linux.sh --update
```

Updates preserve configuration and restart an active service created by this
installer. A manually started process needs to be stopped and started again.
Use `--update --service` to enable the service during an update.

```sh
bash install-linux.sh --uninstall
```

Uninstalling stops and disables the installer's user service and removes its
launcher and virtual environment. It preserves the arguments file, Git checkout,
Ollama and models. The installer refuses to overwrite an existing launcher or
service managed by another installation method. When migrating from Nix, first
disable the previous API service through the configuration that created it.

## Enable Nix commands and flakes

The Nix instructions in this project require both `nix-command` and `flakes`.
If Nix reports that either experimental feature is disabled, enable them using
the instructions for your system below.

### NixOS

Add this setting to your NixOS configuration, usually
`/etc/nixos/configuration.nix`, inside the module's existing attribute set:

```nix
nix.settings.experimental-features = [ "nix-command" "flakes" ];
```

If this list already exists, add the two entries to it, keeping any other enabled
features. Apply the configuration:

```sh
sudo nixos-rebuild switch
```

If you already manage NixOS with a flake, use your usual rebuild command instead.

### Other Linux distributions and macOS

Install [Nix](https://nixos.org/download/) first if it is not already available.
Create `~/.config/nix/` if needed and add this line to `~/.config/nix/nix.conf`:

```text
extra-experimental-features = nix-command flakes
```

If `XDG_CONFIG_HOME` is set, use `$XDG_CONFIG_HOME/nix/nix.conf` instead. The
`extra-` prefix preserves features enabled by the installer or system configuration.
If an `extra-experimental-features` line already exists, add the names to that
line. These user settings apply to subsequent Nix commands without a system rebuild.

For a single command, you can enable both features without changing configuration:

```sh
nix --extra-experimental-features 'nix-command flakes' run . -- --version
```

Run this example from the `translation-api` checkout. See the
[Nix configuration reference](https://nix.dev/manual/nix/stable/command-ref/conf-file.html)
and [NixOS flakes documentation](https://wiki.nixos.org/wiki/Flakes) for details.

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

## Updating a profile-based systemd service on Debian

For a system service with `User=kozel` and
`ExecStart=/home/kozel/.nix-profile/bin/translation-api ...`, update that exact
user profile before restarting the service. Pulling a Git checkout or updating
root's profile does not change this executable. A running process also keeps its
old code until restarted, even after the profile has been upgraded.

Open a login shell as the service user and inspect the installed entry:

```sh
sudo -iu kozel
nix profile list --profile /home/kozel/.nix-profile
```

Find the entry whose flake URL points to `translation-api`. Replace
`API_PROFILE_NAME` below with its `Name` from the list (older Nix versions may
show a numeric index instead):

```sh
nix profile upgrade --refresh --profile /home/kozel/.nix-profile API_PROFILE_NAME
/home/kozel/.nix-profile/bin/translation-api --version
```

Check the original flake URL too: an entry tracking `main` can fetch a newer
commit, while an explicitly pinned revision cannot. If the entry points to a
local checkout, update that checkout first. `--refresh` refreshes cached source
lookups; it does not change the entry's configured source or branch.

After the profile command reports the intended API version, leave the service
user's shell, restart the system service, and check the running API:

```sh
exit
sudo systemctl restart translation-api.service
sudo systemctl status translation-api.service --no-pager
curl http://127.0.0.1:5001/health
```

Restart after active translations have finished: restarting discards jobs and
results. The `/health` response should now include the same `version` as the
profile executable. `systemctl daemon-reload` is needed only if the unit file
was changed; it does not upgrade a Nix package.

If the local health check is current but the public URL is not, check whether
the reverse proxy or tunnel points to a different API instance. For startup
errors, inspect `sudo journalctl -u translation-api.service -n 50 --no-pager`.
See the [Nix profile upgrade reference](https://nix.dev/manual/nix/stable/command-ref/new-cli/nix3-profile-upgrade.html)
for package selection and pinned-reference behavior.

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
