# Translation API

Local translation server with an HTTP API for applications and browser extensions.
Run it on the same computer as your client. It uses Ollama with the
`translategemma:4b` model.

## Before you start

Install and start [Ollama](https://ollama.com/download), then download the model:

```sh
ollama pull translategemma:4b
```

If Ollama is not running in the background, keep `ollama serve` running in a
separate terminal. See Ollama's installation documentation for operating-system
and GPU requirements.

## Windows

Install Python 3.11 or newer and Git. In PowerShell, clone the repository and
open its folder:

```powershell
git clone git@github.com:tomasmark79/translation-api.git
cd translation-api
```

Install the dependencies and start the server:

```powershell
py -m pip install -r requirements.txt
py server.py
```

Alternatively, keep dependencies in a project-local virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe server.py
```

Use the same Python executable to install dependencies and start the server.
The virtual-environment commands do not require activation.

## Linux or macOS

Install [Nix](https://nixos.org/download/) with the `nix-command` and `flakes`
experimental features enabled, then run:

```sh
nix run 'git+ssh://git@github.com/tomasmark79/translation-api?ref=main'
```

The Nix package supports Linux, Intel macOS and Apple Silicon macOS.
Ollama and the model must be installed separately as described above.

## Connect your client

Keep the server terminal open while using your client. Set the client's
translation API address to `http://127.0.0.1:5001` if it is not already the
default. Stop the server with Ctrl+C.

Check availability from another terminal. On Windows:

```powershell
Invoke-RestMethod http://127.0.0.1:5001/health
```

On Linux or macOS:

```sh
curl http://127.0.0.1:5001/health
```

The response should include `"status": "ready"`. Then request a translation
in your client to verify that Ollama and the model work together.

Run only one API instance on a given port.

## Credits
  Thank you to colleagues Kozel and Hendrys for their help with testing the prealpha versions.

## Further documentation

- [Deployment options](docs/deployment.md): persistent installation, configuration
  and automatic startup with Home Manager or NixOS.
- [HTTP API](docs/api.md): endpoints and limits for client developers.
- [Development and validation](docs/development.md): tests, CI, a Czech book sample
  for comparing translations and the optional NLLB backend.

## License

Translation API is licensed under the GNU General Public License, version 3 or
any later version (SPDX: `GPL-3.0-or-later`). See [LICENSE](LICENSE).
The literary test sample in [samples](samples/README.md) remains public domain.
