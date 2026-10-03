# Native CarpetBomb v0.5.1-menu-perf2

Native hidden CarpetBomb (↑ → ↑ → ↑ →), automatically carried alongside Resupply without occupying a chosen slot. This version adapts the field-tested v0.5.1 runtime to Bingus ModOptionsMenu API 1 / version 2. Requires Bingus Shared Loader v18; the in-game MODS menu is a separate dependency. Supported Steam build: 25480438 / EXE 1.8.46015.0.

The menu provides a per-mod Chinese/English language choice, an enable toggle, charges, interval between calls, shared Eagle rearm cooldown, bomb selection, and forward target offset. Each parameter can follow its deployed manager preset or use an independent override. Quantity remains fixed at 20 bombs per aircraft. Stable addresses and hash slots are cached after their first successful lookup. Delayed payload loading no longer allocates repeatedly; unpublished allocations are freed on failure. Engine-owned payload memory stays alive until process exit. See [performance audit](PERFORMANCE_AUDIT.md) and [recovery and build audit](RELIABILITY_AUDIT.md).

Import `NativeCarpetBomb_v0.5.1-menu-perf2.zip` with Arsenal / HD2MM, replacing the older package. Deploy with the loader's documented priority. Apply menu changes to save them to `CarpetBombNative.cfg`. After changing the mod language, close and reopen the Esc menu. Bomb changes require a restart and a new mission to load the selected resources; charges and running timers may require a new mission. Forward changes affect future aircraft only.

Thirty-seven offline test groups cover the existing runtime and menu integration. On 2026-10-04, the user reported completing an in-game test with good performance. No CPU/FPS measurements or detailed scenario results were supplied; earlier v0.5.1 field tests refer to the original version. Multiplayer remains unverified. v0.5.2 was withdrawn after a user-reported regression.

See [menu instructions](README_MODS菜单.md), [Chinese runtime instructions](README_中文.md), [validation](validation/report.json), and [credits](CREDITS.md).

Build: `python tools/build.py` (output under `dist`, ignored by Git). Validate: `python tests/test_runtime.py`. Install development requirements from `requirements-dev.txt`. Tests use an API contract fixture by default; set `HD2_MOD_OPTIONS_MENU_SOURCE` to the external version2 provider's Lua source to run the same checks against its real API. No third-party menu source is distributed here, and tests do not install its native UI hook.
