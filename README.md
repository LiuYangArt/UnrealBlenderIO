download

[https://github.com/LiuYangArt/UnrealBlenderIO/blob/main/Addon/UBIO.zip](https://github.com/LiuYangArt/UnrealBlenderIO/releases)

how to install:
1. install blender addon.
2. install ue tool widget from blender addon preference.
3. run widget in ue.
4. plugin language follows Blender interface language automatically (English / 简体中文).

如何安装:
1. 安装blender插件。
1. 在blender插件的设置页内安装到对应的ue工程。
1. 在ue内右键运行工具widget。
1. 插件文案会跟随 Blender 界面语言自动切换（English / 简体中文）。

本地化维护规范:
1. 新增用户可见文案时，先在 `i18n/en_US.json` 与 `i18n/zh_HANS.json` 增加同名 key。
1. 代码内优先使用 `msgid("...")`（静态 UI）或 `tr("...")`（运行时提示）。
 
<img width="724" height="602" alt="image" src="https://github.com/user-attachments/assets/0f471047-7be6-41fd-a686-b58a2a932b79" />
<img width="999" height="511" alt="image" src="https://github.com/user-attachments/assets/f557dff1-5191-4609-a41e-3e209c440c14" />

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.
