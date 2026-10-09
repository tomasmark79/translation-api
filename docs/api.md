# HTTP API

- `GET /health`: returns `status`, `version`, `backend`, `model` and `device`.
  `version` identifies the running API release (currently `0.2.0`); older servers
  may omit it. It is independent of the Ollama version.
- `POST /translate`: accepts `{"q":"Hello","source":"auto","target":"cs"}`;
  returns HTTP 202 with `jobId` and `status: pending`.
- `GET /translations/<jobId>`: returns `pending` with `partialText`, `done` with
  `translatedText` and `detectedLanguage`, `failed` with `error`, or `cancelled`.
- `DELETE /translations/<jobId>`: cancels a queued translation. Returns HTTP 200
  with `{"status":"cancelled"}`; repeating cancellation has the same result.
  Running or completed jobs return HTTP 409; unknown jobs return HTTP 404.

## Queue state and cancellation

Submission and pending poll responses include `state` and `queuePosition`:

```json
{"status":"pending","state":"queued","queuePosition":2,"partialText":""}
```

`state: "queued"` means waiting; `queuePosition` is one-based among waiting jobs
(1 is next to start). `state: "running"` means the worker has started the job;
its `queuePosition` is 0 and `partialText` contains available translation progress.
Positions change as jobs start or are cancelled. The `status` remains `pending`
for both states so existing clients continue polling without changes. A submission
also contains `jobId`; clients should poll until `done`, `failed` or `cancelled`.

Cancel a waiting job using its ID:

```sh
curl -X DELETE http://127.0.0.1:5001/translations/JOB_ID
```

Cancellation immediately frees a queue slot and prevents the text being sent to
the model. If the worker has already picked up the job, cancellation returns 409
and the translation continues. A cancelled job remains queryable under the same
retention policy as completed jobs. Disconnecting a client does not cancel a job.
Jobs and results are held in memory and are lost when the API process restarts.

## Limits and retention

`source` defaults to `auto`, `target` to `cs`. Supported language codes are listed
in `LANGUAGES` in [`server.py`](../server.py). Text is limited to 10,000 characters. One worker
processes up to eight queued/running jobs in order. Completed, failed and cancelled results
expire ten minutes after completion or cancellation when another job is submitted, and retained
jobs are capped at 128. Queued and running jobs do not expire.

Ollama connections allow up to ten minutes for a blocking network operation,
including waiting for the next stream data. This is not a total translation limit:
long texts are translated in chunks and can take several minutes. Clients should
allow at least fifteen minutes for a job, including time spent in the queue.

Invisible editor placeholders U+FEFF and U+200B are removed from otherwise blank
lines before language detection and translation. Spaces and line breaks are
preserved by this normalization; characters within nonempty text and language
joiners such as U+200C are kept. Input containing only whitespace and these
placeholders is rejected. The 10,000-character limit applies before normalization.

## Choosing the target language

Every client can choose the target independently in each `POST /translate` request.
Use `source: "auto"`, or omit `source`, for automatic source detection. `target`
accepts language codes such as `cs` (Czech), `en` (English), `de` (German), `fr`
(French), `es` (Spanish) and `pl` (Polish). Omitting `target` keeps the default `cs`;
`target: "auto"` is invalid. Explicit source codes remain available to existing
clients.

For example, an external program can request German output with automatic detection:

```sh
curl -H 'Content-Type: application/json' \
  -d '{"q":"Good morning!","source":"auto","target":"de"}' \
  http://127.0.0.1:5001/translate
```

Poll `GET /translations/<jobId>` using the returned `jobId` until `status` is
`done`, `failed` or `cancelled`. The target belongs to that job; it is not a server-wide setting.
Ollama prompts use human-readable names for all supported language codes.

The listener defaults to loopback; `--host` (or the service's `host` option)
changes the listening address. Web page origins are rejected. Chrome extensions
(`chrome-extension://<extension-id>`) call it from their service workers;
Firefox extensions (`moz-extension://<uuid>`) call it from background scripts.
Native local clients can call it without an
Origin header. It has no remote-access authentication. Request text and
translations are not written to HTTP logs.


[Back to the quick start](../README.md).
