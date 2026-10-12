# API-only phone installation

This checkout installs the upstream Mobile-Agent-v3.5 mobile runner with a small,
isolated Python environment. It does not install PyTorch, training tools, local
model weights, a background service, or a Codex skill.

## Install and configure

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements-api.lock
chmod +x bin/mobile-agent
bin/mobile-agent doctor
cp .env.example .env
chmod 600 .env
```

Set `MOBILE_AGENT_API_KEY` in `.env` or the process environment. For the default
`gui-plus-2026-02-26`, use a Beijing-region Bailian API key. An existing compatible
GUI-Owl endpoint can be selected with `MOBILE_AGENT_BASE_URL` and
`MOBILE_AGENT_MODEL`. Credentials, APKs, screenshots and run traces are ignored by
Git. An API task sends phone screenshots to the configured inference provider.

```sh
bin/mobile-agent capture local/screen.png
bin/mobile-agent run '在小红书搜索奥克兰租房' --max-steps 20
```

The phone needs an authorized ADB connection and the official ADB Keyboard.
Text input temporarily switches the input method, sends UTF-8 using base64 and
restores the previous default and enabled-keyboard state afterwards.

## Local fixes

- Removed the unused `qwen_vl_utils` import: this file already defines its own
  resize function, and API inference needs no Torch dependency.
- Decode local `file://` image references before opening them.
- Map normalized model coordinates onto the actual ADB screen, including edge
  clamping, instead of the model's resized image dimensions.
- Parse `tool_call` JSON with or without line breaks.
- Report ADB failures and invoke ADB without a host shell.
- Take and validate screenshots from ADB bytes and create a distinct trace
  directory for every run without deleting earlier evidence.
- Read API secrets from the environment rather than requiring command-line keys.

`doctor` reports installation and configuration readiness. It is not proof of
model inference or task success. The upstream runner still relies on the model's
termination signal; acceptance needs an independent check of the actual screen.

## Recovery

This installation is isolated in its checkout. Removing the launcher and virtual
environment reverses the host installation. ADB Keyboard can be uninstalled if it
was newly installed. The captured prior IME state and APK provenance are retained
in `local/` for device recovery. Source changes are committed separately from the
upstream revision.
