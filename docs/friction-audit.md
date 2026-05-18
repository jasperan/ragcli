# ragcli Friction Audit

## Goal

Reduce setup and daily-use friction for new users while making the Rust TUI more useful from both source checkouts and installed packages.

## Findings

- Packaging advertised `ragcli` commands, but `setup.py` had no `console_scripts` entry.
- Runtime dependencies used by the CLI and tests were present in `requirements.txt` but missing from `setup.py`.
- `setup.py` also pulled in unused heavyweight packages, increasing fresh install time.
- The one-command installer installed requirements but did not install the package entry point.
- Docker defaulted to `ragcli web`, which is not a registered command.
- Docker Compose healthcheck used `curl`, but the slim Python image did not install it.
- Docker builds sent a large local context because there was no `.dockerignore`.
- Default Compose host ports can collide with other local Oracle/API/Ollama stacks.
- Oracle Free's built-in `PDBADMIN` user connected but did not have the table creation privileges needed by `ragcli db init`.
- The TUI only knew how to start `python ragcli.py` from a repo root.
- TUI Query, Documents, and System views had UI shells but limited live API wiring.
- The System view did not match the API's `connected`/`disconnected` status vocabulary.
- Documents deletion was a one-key action with no explicit confirmation.

## Decisions

- Keep `setup.py` as the packaging source for now and add the missing console script and runtime dependencies there.
- Prune unused Python runtime dependencies from package metadata and keep directly imported libraries declared.
- Add `ragcli doctor` as a safe first-run diagnostic that can run before Oracle or Ollama are fully working.
- Use Python's standard library for the Docker API healthcheck and remove unused Compose volumes.
- Add `.dockerignore` and make published host ports configurable with `RAGCLI_API_PORT`, `ORACLE_HOST_PORT`, and `OLLAMA_HOST_PORT`.
- Create a `RAGCLI` Oracle app user from a Compose startup script, grant the schema privileges needed by ragcli, and point the API at that user by default.
- Make the TUI start from a source checkout when possible and fall back to the installed `ragcli` command otherwise.
- Add `RAGCLI_API_URL` for users who already run the API.
- Wire Query, Documents, and System views to concrete API calls and clear error/loading states.
- Render System service cards from real API status messages and accept `connected`, `ok`, or `healthy` as available states.
- Make document deletion require pressing `d` twice, with `Esc` to cancel.
- Move the TUI palette/status palette toward a calmer teal/blue theme instead of a purple-dominant palette.

## Remaining Backlog

- Add packaged distribution for the Rust TUI binary.
- Add snapshot-style TUI rendering tests for narrow terminals.
- Add streaming SSE support in the Query view instead of only non-streaming query responses.
- Add live CPU/RAM sampling to the System view.
- Decide whether `requirements.txt` should be generated from packaging metadata or retained as the source install path.
