# Zelda A Link to the Past 3DS — 简体中文 fork

This fork pins the sxunix engine and includes Simplified Chinese dialogue and
fonts. See [中文安装、升级与语言切换](platform/3ds/CHINESE.md) for setup and
the current validation limits. Game dialogue defaults to Chinese; settings
retain the existing interface.

<img width="1672" height="941" alt="alttp" src="https://github.com/user-attachments/assets/6fc340f1-7d18-4e75-9a1a-bf8986d490dc" />

Nintendo 3DS dual-screen port of Zelda3, built with help from Codex.

This project is based on open-source work from:

- Original reverse-engineered Zelda3 engine: https://github.com/snesrev/zelda3
- Pinned Chinese engine dependency: https://github.com/sxunix/zelda3
- Android port base: https://github.com/Waterdish/zelda3-android
- Dual-screen Android branch used as the 3DS source base:
  https://github.com/samyost1/zelda3-android

No ROM or extracted game asset package is distributed in this repository. Each
user must provide their own legally obtained USA, unheadered ROM on their own
3DS SD card.

## Discord
https://discord.gg/SMW49UMkw

## Features

- Top screen: 400x240 gameplay.
- Bottom screen: 320x240 live map, dungeon map, gear view, item selection and
  touch settings.
- First launch extracts `zelda3_assets.dat` locally from the user's ROM.
- Display modes: wide mod, stretched original and original aspect.
- Turbo speed: off, x2, x3, x4 or x5.
- New 3DS: ZL or C-stick can hold turbo when turbo is enabled.
- Quick diagnostics: press `L + R + A` to create a dump with memory files,
  physical 400x240/320x240 screen captures, raw display framebuffers and a
  validated `load-state.bin` checkpoint. Audio pauses during capture and a
  `DUMP SAVED` notice confirms complete success on the top screen.
- Developer settings can load the newest dump checkpoint for the active ROM
  profile and optionally show the current FPS on the top screen.
- PICA200/Citro2D presentation for both screens with nearest-neighbor sampling
  and RGB565 display output.
- PICA200 GPU rendering on Old 3DS, with automatic software fallback for
  unsupported effects. New 3DS uses its existing CPU renderer.
- Native 400x240 WIDE mode, fixed-camera edge corrections and persistent
  per-ROM display, zoom, turbo and control settings.
- Responsive map controls and independent heart updates on Old 3DS.
- Fixed-step 60 Hz gameplay timing with bounded catch-up instead of making
  game speed depend on when a VBlank wait returns.
- Parallel PPU scanline rendering on Core 0 and Core 1, plus Core 2 on New 3DS,
  with persistent tile-row caches and frame-time diagnostics in quick dumps.
- HOME Menu banner uses a lightweight custom CGFX 3D logo model with the
  supplied hover sound converted to a short PCM WAV.

## Installation

Install the CIA, then create this directory on the SD card:

```text
sdmc:/3ds/Zelda 3DS/
```

Place a legally obtained USA, unheadered ROM there. The preferred filename is
`zelda3.sfc`, but the setup also accepts other `.sfc` or `.smc` filenames.

On first launch, press A to validate the ROM and extract the assets. The ROM is
read locally and is never copied into the CIA.

For this fork's Chinese dialogue, select the clean USA ROM. The bundled Chinese
increment is merged locally after extraction; a Chinese patched ROM is not required.

Audio requires:

```text
sdmc:/3ds/dspfirm.cdc
```

Luma3DS can create this file from the console's own firmware through Rosalina's
`Dump DSP firmware` command.

## Releases

Fork releases are listed at [kolyneh/zelda-alttp-3ds](https://github.com/kolyneh/zelda-alttp-3ds/releases).
The build workflow uploads verified CIA/3DSX packages, licenses and checksums as
Actions artifacts. A successful build does not imply device runtime validation.

See [CHANGELOG.md](CHANGELOG.md) for the changes since v2.8.

## Bug reports

Press `L + R + A` while the issue is visible and attach the resulting dump from:

`sdmc:/3ds/Zelda 3DS/dumps/`

## Building

Requirements:

- devkitARM, libctru and 3ds-cmake under `DEVKITPRO`
- `makerom` and `bannertool` for CIA packaging
- Python 3 and Pillow for the standalone Chinese resource pack
- the pinned `vendor/zelda3` submodule and vendored SDL2 source in `app/jni/SDL2`
- `banner.cgfx` is prebuilt in `platform/3ds/assets`; it was generated from
  the supplied 2.0 Blender logo model.

Build:

```sh
git submodule update --init --recursive
bash platform/3ds/build.sh
```

The script builds the 3DSX and CIA under `build-3ds/game/`. See
[CHINESE.md](platform/3ds/CHINESE.md#构建) for the pinned updater-library and
packaging-tool preparation used by CI.

## License and legal notice

The Zelda3 engine retains the **MIT license** and copyright notices in
[vendor/zelda3/LICENSE.txt](vendor/zelda3/LICENSE.txt), which also contains the Opus notice.
SDL2, SDL2_mixer and other dependencies retain their own licenses. These
component licenses do not grant rights to Nintendo game content.

This repository contains only source code, build scripts, redistributable port
assets and patch/extraction logic. It does not include a ROM, extracted game
assets, or `zelda3_assets.dat`.

Users are responsible for providing their own legally obtained compatible ROM.

## Credits

Thanks to [@999sian](https://github.com/999sian) for her Old 3DS optimization
work, [arth78](https://github.com/arth78) for the WIDE display contribution,
and [Archaistic](https://github.com/Archaistic) for the WIDE height and
Triforce improvements.

Logo work by [Phibonacci](https://github.com/Phibonacci), based on the original
3D model by [TiraArt](https://sketchfab.com/TiraArt).

See [3DS controls and diagnostics](platform/3ds/README.md).

## Updates

In Settings > Update, choose Stable or Pre-release. Tap the release name to
read its changelog on the top screen, with Prev/Next below for more pages.
Choose Download Update and confirm installation, then reopen the game.
Save in-game before installing. Startup checks also indicate newer releases.

Updates use this fork's release feed. An empty Stable or Pre-release channel
shows no available release. The version in this branch is 3.2.1; CIA identity
and per-ROM profile paths match the original port.

Settings is Screen, Turbo Speed, Developer, Update, Restart. Restart opens
the ROM selector and starts the selected ROM fresh; existing saves remain.

Version 3.1 uses the native HID contact flag for touch press and release detection,
including startup and releases with residual coordinates. Physical coordinates
remain protected from SDL viewport transforms. The last 32 touch selections
are included in diagnostic dumps. Use the FBI QR if touch controls prevent
opening Update.
