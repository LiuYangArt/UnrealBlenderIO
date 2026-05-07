# Search patterns

Use filename search first, then read only a local slice.

## Core commands

Find a class:

```powershell
rg -n "^class EditorLevelLibrary|^class EditorAssetLibrary|^class EditorUtilityLibrary" Intermediate\PythonStub\unreal.py
```

Find a top-level helper:

```powershell
rg -n "^def load_object|^def load_class|^def find_object|^def get_editor_subsystem|^def log\(|^def log_warning\(|^def log_error\(" Intermediate\PythonStub\unreal.py
```

Find subsystem-related APIs:

```powershell
rg -n "Subsystem|get_editor_subsystem|get_engine_subsystem" Intermediate\PythonStub\unreal.py
```

Read a small nearby slice after locating a hit:

```powershell
Select-String -Path "Intermediate\PythonStub\unreal.py" -Pattern "^class EditorLevelLibrary|^def get_editor_subsystem" -Context 3,20
```

## Project-local evidence
- Existing probe: `docs\probes\probe_script_class.py`
- Skill probes: `scripts\probe_unreal_symbol.py`, `scripts\probe_editor_subsystem.py`, `scripts\probe_load_target.py`
- Log chain note: `docs\2026-04-29-output-log-visibility.md`
- Runtime verification entry: `tools\verify.ps1`

## Probe guidance
- Prefer a tiny probe that only checks one API family at a time.
- Log through `unreal.log(...)` so the result lands in `Saved\Logs\AS_Shooter.log`.
- If a symbol exists in the stub but fails at runtime, report that explicitly instead of adding fallback guesses.
- Prefer Python scripts over PowerShell for reusable probe logic in this project.