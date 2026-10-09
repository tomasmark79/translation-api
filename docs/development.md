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
translation, trailing whitespace and invisible editor placeholders on blank lines. CI runs these checks on
Linux, Intel macOS and Apple Silicon macOS. It does not measure real model speed
or prove GPU acceleration.

## Translate the Czech book sample

The repository includes a public-domain Czech excerpt from Božena Němcová's
*Babička*, below the 10,000-character API limit. Its source and public-domain status
are recorded in [samples/README.md](../samples/README.md).

From the project directory, translate it into English:

```sh
nix develop --command python scripts/translate_sample.py
```

Choose another Ollama server or installed model:

```sh
nix develop --command python scripts/translate_sample.py \
  --ollama-url http://192.168.1.50:11434 --model translategemma:4b
```

With the Python dependencies already installed, use
`python scripts/translate_sample.py` (or `py scripts/translate_sample.py` on Windows)
with the same options. `--file path/to/text.txt` accepts another Czech UTF-8 text
within the same character limit.

To test a running Translation API server instead, use `--api-url`:

```sh
nix develop --command python scripts/translate_sample.py \
  --api-url https://translations.kozelgaming.cz
```

This mode submits a Czech-to-English job and polls for its result for up to 15
minutes, including queue time. It reports the backend and model from `/health`.
The model and upstream Ollama address are configured on that server; `--model`
cannot override them. `--ollama-url` is for an actual Ollama endpoint exposing
`/api/tags` and `/api/chat`, whereas `--api-url` uses `/health`, `/translate` and
`/translations/<jobId>`.

With `--ollama-url`, the command connects directly to Ollama using the API server's translation code,
including its prompts, chunking and network timeout. A running translation API
service is not required. It reports the input length, Ollama address, model and
elapsed time on stderr. The translated text is hidden to keep server timing
comparisons readable. To inspect it, uncomment the `print(result["translatedText"],
flush=True)` line in `scripts/translate_sample.py`. Interactive terminals also show
generated-character progress. Long samples may take several minutes; Ctrl+C cancels
the local command (a submitted API job continues on the server). This is a manual quality and timing check, not an assertion that
a translation is linguistically correct.

## Optional NLLB backend

The optional NLLB CPU backend remains a development option:
`nix-shell nllb-shell.nix --run 'python server.py --backend nllb'`.
Its PyTorch/Transformers dependencies are separate from the portable Ollama
package and are not covered by the cross-platform CI.

Run these commands from the repository root. Windows startup through
`server.py` has been manually confirmed by a user; Windows is not covered by
the current CI checks.

[Back to the quick start](../README.md).
