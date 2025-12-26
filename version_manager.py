#!/usr/bin/env python3
"""
version_manager.py - blender_manifest.toml 版本管理工具

用于读取和更新 blender_manifest.toml 中的版本号，支持 SemVer 语义化版本。
"""

import re
import sys
from pathlib import Path

MANIFEST_FILE = "blender_manifest.toml"


def read_version() -> str:
    """
    从 blender_manifest.toml 读取当前版本号。

    Returns:
        str: 当前版本号字符串，例如 "1.0.0"
    """
    manifest = Path(MANIFEST_FILE)
    if not manifest.exists():
        raise FileNotFoundError(f"找不到 {MANIFEST_FILE}")

    content = manifest.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if not match:
        raise ValueError(f"在 {MANIFEST_FILE} 中未找到 version 字段")

    return match.group(1)


def parse_version(version_str: str) -> tuple[int, int, int]:
    """
    解析版本号字符串为元组。

    Args:
        version_str: 版本号字符串，例如 "1.2.3"

    Returns:
        tuple[int, int, int]: (major, minor, patch) 元组
    """
    parts = version_str.split(".")
    if len(parts) != 3:
        raise ValueError(f"无效的版本号格式: {version_str}")
    return int(parts[0]), int(parts[1]), int(parts[2])


def format_version(major: int, minor: int, patch: int) -> str:
    """
    将版本元组格式化为字符串。

    Args:
        major: 主版本号
        minor: 次版本号
        patch: 补丁版本号

    Returns:
        str: 格式化的版本号字符串
    """
    return f"{major}.{minor}.{patch}"


def bump_version(version_str: str, bump_type: str) -> str:
    """
    根据升级类型计算新版本号。

    Args:
        version_str: 当前版本号字符串
        bump_type: 升级类型 ("patch", "minor", "major")

    Returns:
        str: 新版本号字符串
    """
    major, minor, patch = parse_version(version_str)

    if bump_type == "patch":
        patch += 1
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    else:
        raise ValueError(f"无效的升级类型: {bump_type}")

    return format_version(major, minor, patch)


def update_version(bump_type: str) -> str:
    """
    更新 blender_manifest.toml 中的版本号。

    Args:
        bump_type: 升级类型 ("patch", "minor", "major")

    Returns:
        str: 新版本号字符串
    """
    current = read_version()
    new_version = bump_version(current, bump_type)

    manifest = Path(MANIFEST_FILE)
    content = manifest.read_text(encoding="utf-8")
    new_content = re.sub(
        r'^(version\s*=\s*)"[^"]+"',
        f'\\1"{new_version}"',
        content,
        flags=re.MULTILINE
    )
    manifest.write_text(new_content, encoding="utf-8")
    print(f"版本已更新: {current} -> {new_version}")
    return new_version


def show_info():
    """
    显示版本信息并输出给 bat 脚本使用。
    """
    current = read_version()
    major, minor, patch = parse_version(current)

    # 输出给 bat 脚本的版本信息
    with open("versions.bat", "w", encoding="utf-8") as f:
        f.write(f"set CURRENT_VERSION={current}\n")
        f.write(f"set NEXT_PATCH={format_version(major, minor, patch + 1)}\n")
        f.write(f"set NEXT_MINOR={format_version(major, minor + 1, 0)}\n")
        f.write(f"set NEXT_MAJOR={format_version(major + 1, 0, 0)}\n")


def get_current():
    """
    获取当前版本并输出给 bat 脚本。
    """
    current = read_version()
    with open("new_version.bat", "w", encoding="utf-8") as f:
        f.write(f"set NEW_VERSION={current}\n")


def main():
    if len(sys.argv) < 2:
        print("用法: python version_manager.py <command> [args]")
        print("命令:")
        print("  info        - 显示版本信息")
        print("  get         - 获取当前版本")
        print("  update TYPE - 更新版本 (patch/minor/major)")
        sys.exit(1)

    command = sys.argv[1]

    if command == "info":
        show_info()
    elif command == "get":
        get_current()
    elif command == "update":
        if len(sys.argv) < 3:
            print("错误: update 命令需要指定类型 (patch/minor/major)")
            sys.exit(1)
        update_version(sys.argv[2])
    else:
        print(f"未知命令: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
