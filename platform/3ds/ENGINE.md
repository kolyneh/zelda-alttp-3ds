# Engine dependency

The 3DS target uses `sxunix/zelda3` at the commit recorded in
`engine.lock.json`. Initialize it with:

```sh
git submodule update --init --recursive
python3 tools/3ds/prepare_engine.py
```

Preparation copies the dependency into `build-3ds/engine`, normalizes source
line endings, and applies the checksum-verified `patches/sxunix-3ds.patch`.
The patch retains the existing port's PPU, dual-screen, storage, widescreen and
diagnostic interfaces alongside sxunix's Chinese decoding and rendering.
CMake and the 3DS host harnesses use that generated engine. The historical
`app/jni/src` checkout remains for the Android target; it is not a 3DS fallback.

Run preparation before the 3DS host tests. Never edit generated files as the
only copy of a change: update the reviewed patch and its SHA-256 in the lock
file, then regenerate and test. Dependency upgrades require updating the Git
submodule commit and lock together, rebasing the patch, and running the 3DS
regressions. The preparation script rejects dirty or mismatched dependencies.

The pinned engine's `LICENSE.txt`, third-party notices and the original port's
credits remain applicable. Chinese font attribution is described in CHINESE.md.
