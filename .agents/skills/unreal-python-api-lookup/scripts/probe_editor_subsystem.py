import sys
import unreal


def log(message: str) -> None:
    unreal.log(f"[UEPyProbe] {message}")


def main() -> None:
    class_name = sys.argv[1] if len(sys.argv) > 1 else "LevelEditorSubsystem"
    subsystem_cls = getattr(unreal, class_name, None)
    if subsystem_cls is None:
        raise RuntimeError(f"Missing unreal.{class_name}")

    subsystem = unreal.get_editor_subsystem(subsystem_cls)
    if subsystem is None:
        raise RuntimeError(f"get_editor_subsystem({class_name}) returned None")

    log(f"Resolved editor subsystem {class_name}: {subsystem}")


if __name__ == "__main__":
    main()