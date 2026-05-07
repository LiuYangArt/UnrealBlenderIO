import sys
import unreal


def log(message: str) -> None:
    unreal.log(f"[UEPyProbe] {message}")


def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "load_object"
    obj = getattr(unreal, symbol, None)
    if obj is None:
        raise RuntimeError(f"Missing unreal.{symbol}")

    log(f"Found unreal.{symbol}: {type(obj).__name__}")

    if callable(obj):
        try:
            obj()
            log(f"Called unreal.{symbol}() successfully")
        except TypeError as exc:
            log(f"unreal.{symbol} exists but needs args: {exc}")
        except Exception as exc:
            log(f"unreal.{symbol} exists but call failed: {exc}")


if __name__ == "__main__":
    main()