---
name: unreal-python-api-lookup
description: Look up Unreal Engine Python API names, signatures, local probe patterns, and tiny reusable editor scripts in this project before writing or running Unreal Python automation. Use when the task mentions `import unreal`, `unreal.*`, `Intermediate\PythonStub\unreal.py`, editor subsystems, `EditorLevelLibrary`, `EditorAssetLibrary`, asset loading, class loading, or a UE Python probe.
---

# Unreal Python API Lookup

Use this skill to answer UE Python API questions in this project with the smallest proven pattern.

## Workflow
1. Search `Intermediate\PythonStub\unreal.py` first for class names, function names, signatures, and nearby docstrings.
2. Search project docs and existing probes second.
3. Reuse a tiny script from `scripts\` when it already matches the need.
4. Return one minimal pattern plus one smallest confirming probe.
5. If runtime behavior is uncertain, validate by running a tiny probe in Editor and reading `Saved\Logs\AS_Shooter.log`.

## What `Intermediate\PythonStub\unreal.py` is good for
- Find whether `unreal.<name>` exists in this local engine build.
- Find class names such as `EditorLevelLibrary`, `EditorAssetLibrary`, `EditorUtilityLibrary`, `AssetToolsHelpers`.
- Find top-level helpers such as `load_object`, `load_class`, `find_object`, `get_editor_subsystem`, `log`, `log_warning`, `log_error`.
- Inspect rough signatures and parameter names before writing a probe.

## What it is not good for
- Do not treat the stub as proof that a call works in the current Editor state.
- Do not assume every stubbed symbol is usable in PIE, commandlet, or current plugin state.
- Do not read the whole file into context. It is large; search first, then read a small nearby slice.

## Search order
1. `Intermediate\PythonStub\unreal.py`
2. `scripts\*.py`
3. `docs\probes\*.py`
4. `docs\2026-04-29-output-log-visibility.md`
5. other project docs under `docs\`
6. `UnrealMCP` only as an Editor automation helper, not as proof of Python runtime behavior

## Reusable scripts
- `scripts\probe_unreal_symbol.py`: check whether a top-level `unreal.<name>` symbol exists and can be called if zero-arg.
- `scripts\probe_editor_subsystem.py`: resolve an editor subsystem class and report whether `get_editor_subsystem(...)` succeeds.
- `scripts\probe_load_target.py`: try `load_object`, `load_class`, and `find_object` against a supplied path.

Run them inside Unreal Editor Python or adapt their core function into an existing probe.
Always keep probes small and log through `unreal.log(...)`.

## Answer format
- exact API name or signature fragment
- one short example
- one confidence note if behavior still needs live confirmation
- one smallest probe to run next

## References
- Read `references/search-patterns.md` for the recommended search commands.