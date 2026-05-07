import sys
import unreal


def log(message: str) -> None:
    unreal.log(f"[UEPyProbe] {message}")


def try_call(name: str, *args):
    fn = getattr(unreal, name, None)
    if fn is None:
        log(f"Missing unreal.{name}")
        return None
    try:
        result = fn(*args)
        log(f"unreal.{name} succeeded: {result}")
        return result
    except Exception as exc:
        log(f"unreal.{name} failed: {exc}")
        return None


def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else "/Script/Engine.Actor"
    result = None
    for fn_name in ["load_class", "find_object", "load_object"]:
        result = try_call(fn_name, None, target)
        if result is not None:
            break

    if result is None:
        raise RuntimeError(f"Could not resolve target: {target}")

    if hasattr(result, "get_path_name"):
        log(f"Resolved path: {result.get_path_name()}")


if __name__ == "__main__":
    main()