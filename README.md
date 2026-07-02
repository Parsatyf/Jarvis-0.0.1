# Jarvis

Jarvis is a small autonomous coding assistant prototype for Windows. It is designed to:
- inspect files and directories
- read and modify project files
- run commands safely inside the project sandbox
- keep local state and logs in a private folder

## Repository structure

- `jarvis.py` - main agent loop
- `config.py` - runtime and safety configuration
- `tools.py` - file, directory, and command utilities
- `memory.py` - persistent agent state storage
- `logger.py` - JSON log writer
- `prompts.py` - system and user prompt templates
- `json_validation.py` - model output extraction and validation
- `retry_loop.py` - command retry helper
- `requirements.txt` - Python dependency list
- `test.py` - simple Ollama connectivity test
- `test_tools_safety.py` - regression test for command safety
- `.env.example` - placeholder example environment file
- `.gitignore` - repository ignore rules

## Setup

1. Create a virtual environment:

```powershell
python -m venv venv
```

2. Activate it:

```powershell
venv\Scripts\Activate.ps1
```

3. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Configuration

`config.py` is the main settings file.

Important default behaviors:
- `workspace_root` is automatically set to this project folder
- `allow_read_anywhere = False`
- `allow_write_anywhere = False`
- `enable_command_execution = True`
- `default_command_cwd` is set to the project folder

This means the agent is safe by default and only works inside the `jarvis` project unless you explicitly relax those settings.

## Secrets and sensitive values

This repository does not contain any real passwords or API keys.

The only placeholder secret file is:
- `.env.example` - contains `OPENAI_API_KEY=Change_me`

If you need a local environment file, copy `.env.example` to `.env` and fill in your secrets locally.

> `.env` is ignored by `.gitignore` and should never be committed with real keys.

## GitHub readiness

This repo is prepared for GitHub with these ignored paths:
- `agent_state/` - local runtime state and logs
- `__pycache__/` and `*.pyc` - Python caches
- `venv/`, `.venv/` - virtual environment files
- `.vscode/` - editor settings
- `.env` - local environment secrets

## Running Jarvis

Run the agent with:

```powershell
python jarvis.py
```

Then type a goal at the prompt. Use `exit`, `quit`, or `q` to stop.

## Testing

Run the existing safety regression test:

```powershell
python -m unittest test_tools_safety.py
```

## Notes

- The project currently uses `requests` and local Ollama by default.
- There is no hardcoded API key or password in tracked source files.
- If you want to add provider-specific secrets, use environment variables and do not commit the `.env` file.
