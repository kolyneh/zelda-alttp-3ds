# 简体中文 3DS fork

本 fork 固定使用 [sxunix/zelda3](https://github.com/sxunix/zelda3) 的
`eb61ac5e5224580b126d00203dfd2da2ede022d1`，通过可重复应用的补丁保留
EstebanPdN 3DS 移植版的双屏、地图、触控、存档及 Old/New 3DS 渲染适配。
版本为 `3.2.1`。中文范围是游戏对白；设置界面沿用原版。

## 安装和升级

1. 安装 `zelda3-3ds-v3.2.1.cia`，或用 Homebrew Launcher 启动同名 `.3dsx`。
2. 将自己提供的标准 **USA、无 copier header** ROM 放入
   `sdmc:/3ds/Zelda 3DS/`。推荐命名 `zelda3.sfc`，也接受其他 `.sfc` / `.smc` 名称。
3. 首次启动选择该 ROM，按 A 进行本地资源提取。程序会自动合并中文对白和字体，
   将该 profile 的语言设为 `cn`。无需中文 ROM 或另行复制字库。
4. 音频需要 `sdmc:/3ds/dspfirm.cdc`；可通过 Rosalina 从自己的设备导出 DSP firmware。

CIA 沿用 `0004000005a13e00`，会覆盖相同身份的已有安装。更新前保存游戏，
备份 `sdmc:/3ds/Zelda 3DS/`，保留 ROM 文件名。已有 profile 的资产会补入或更新中文；
存档和其他设置沿用原路径。迁移成功后只设置一次默认中文。

更新器从 [kolyneh/zelda-alttp-3ds 的 releases](https://github.com/kolyneh/zelda-alttp-3ds/releases)
读取 Stable / Pre-release。空发布频道正常显示无可用版本。构建产物可从此仓库
Actions 的 `zelda3-3ds-v3.2.1-cn` artifact 下载；artifact 不是正式发布。

## 中文和英文切换

退出游戏后，找到当前 profile 的配置文件：

```text
sdmc:/3ds/Zelda 3DS/profiles/<ROM 文件名和 hash>/zelda3.ini
```

当前 profile 可在根目录 `selected_rom.ini` 的 `ActiveProfile` 中确认。
修改 `[General]` 下已有的 `Language` 项，然后重启：

```ini
[General]
Language = cn
```

英文用 `Language = us`。迁移后的再次启动会保留该选择。
根目录 `zelda3.ini` 是 profile 配置的运行副本；启动会从 profile 复制它，
因此持久修改应写入 profile 配置。

## 排查

查看 `sdmc:/3ds/Zelda 3DS/setup-progress.txt`：

- `Chinese profile assets: updated`：已合并或升级中文资源。
- `Chinese profile assets: current`：中文缓存与内置载荷一致。
- `Profile language: cn` / `us`：采用的 profile 语言。

迁移失败时同一日志会记录原因。保留 `.cn.bak` 文件，让下次启动自动恢复。
游戏内可按 `L + R + A` 保存诊断到 `sdmc:/3ds/Zelda 3DS/dumps/`；
`runtime.log` 记录当前 profile 与渲染路径。

## 构建

需要 Python 3 + Pillow、devkitARM/libctru/3ds-cmake、CMake 和宿主构建工具。
CI 使用锁定摘要的 devkitPro 镜像以及校验过 SHA-256 的工具和依赖源码。
以下工具准备命令面向 Linux x86_64 宿主：

```sh
git submodule update --init --recursive
python3 tools/3ds/fetch_build_inputs.py
export UPDATE_DEPS_ROOT="$PWD/build-3ds/update-prefix"
export ZELDA3_TOOLS_ROOT="$PWD/build-3ds/tools"
bash tools/3ds/build_update_dependencies.sh
bash platform/3ds/build.sh
python3 tools/3ds/package_release.py
```

`build.sh` 会先校验并准备 sxunix 引擎，再生成中文载荷。直接调用 CMake 前也需要
运行 `prepare_engine.py` 和 `build_cn_pack.py`，避免使用旧的生成目录。
最终产物位于 `build-3ds/release/`，包含安装包、许可证、构建来源及 `SHA256SUMS`。
打包检查验证 CIA title ID、内容散列及两种安装包内资源的一致性。
CI 和中文载荷生成不读取 ROM，分发包不含 ROM 或完整游戏资产。

## 来源和验证范围

- 中文使用 sxunix 提供的 397 条对白、1118 个汉字及 16 个中文标点。
- 字体来源与版权见包内 `chinese-font-notice.txt`；完整 SIL OFL 见 `chinese-font-OFL.txt`。
- 为适配 13 像素汉字宽度，字形按墨迹左对齐，35 个较宽字形用最近邻缩窄。
  两条过长对白只调整换行控制，文字保持原样。
- 主机测试覆盖所有对白的编码往返、实际引擎解码/姓名与数值替换、首末字形像素、
  损坏输入、资产迁移、文件操作失败恢复、英文回退、更新校验及 PPU 回归。
- 主机上的存档与重启测试使用合成数据。当前没有用户 ROM 或设备运行证据；
  开场、长对白、选项、保存重启和 Old/New 3DS 真机表现仍需实际运行验证。

3DS 原作者及已有贡献者署名保留。引擎、SDL2、更新依赖和字体许可证随分发包提供。
