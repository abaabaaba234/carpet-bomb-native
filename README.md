# Native CarpetBomb v0.5.6-diagnostic

Diagnostic build for the reported rear/front landing offset. This build has not fixed the landing issue: it adds only bounded internal flight logging and retains the v0.5.5 bombing parameters. It logs at most 12 first native-aircraft observations, plus 3 changed unmatched-descriptor groups, using the reads already performed by target handling. No external process-memory reader is used. 44 offline groups check the runtime and bounded diagnostics; gameplay and multiplayer remain unverified.

To isolate the issue: select CarpetBomb 200 kg, front/back approach, forward offset 0 m, and Apply; restart the game so its selected bomb resources load, enter a new mission and call it once. Report whether the bombs land behind the beacon or near it. The mod writes the observation to the existing CarpetBombNative.log. Preserve this log before restarting again.

v0.5.5 fixes the startup refusal in v0.5.4: the angle-read and angle-conversion instructions are at separate RVAs (+0x89F1A6 and +0x89F1B5). The old concatenated expectation stopped the mod before granting CarpetBomb. Runtime checks remain enabled. Tests now use independently captured code windows, reproduce the old failure and pass after the fix. No fresh in-process or gameplay verification has been performed.

Native hidden CarpetBomb (↑ → ↑ → ↑ →), automatically carried alongside Resupply without occupying a chosen slot. Includes Eagle Cluster, Napalm and Gas payloads, and a left/right or front/back approach selector. Requires Bingus Shared Loader v18 / API 1. The optional MODS menu requires separate Bingus ModOptionsMenu API 1 / version 2+. Supported Steam build: 25480438 / EXE 1.8.46015.0; offline tests run LuaJIT 2.1 (`lupa.luajit21`, lupa 2.8).

| Setting | Choices |
| --- | --- |
| Bomb | Airstrike (default), CarpetBomb 200 kg, Eagle 500 kg, Eagle Cluster, Eagle Napalm, Eagle Gas |
| Approach | Left/right across the throw (default), front/back along the throw |
| Other settings | Enable, charges, call interval, shared Eagle rearm cooldown, forward target offset |

Each parameter can follow its manager preset or use an independent override. Titles, labels and choices support Chinese (default) and English; descriptions always display both languages. Quantity stays at 20 primary bombs per aircraft. Cluster uses native projectile 286, which releases 8 secondary bomblets per primary bomb through explosion 417, increasing projectile/effect load. Napalm and Gas retain their native fire/status definitions. The selected native loadout package supplies the corresponding resources. Other Eagle records, projectile damage and ship upgrade definitions remain untouched. See the [historical performance audit](PERFORMANCE_AUDIT.md) and [recovery audit](RELIABILITY_AUDIT.md).

Import `NativeCarpetBomb_v0.5.6-diagnostic.zip` with Arsenal / HD2MM, replacing the older package. Purge and Deploy with the loader's documented priority, restart, and enter a new mission. Open Esc → MODS → Native CarpetBomb, then Apply to save. Bomb changes require a restart and a new mission to load resources; charges and running timers may require a new mission. Approach changes affect newly spawned aircraft; aircraft already in flight keep their copied settings. Forward offset follows the selected flight axis. Close and reopen Esc after a language change.

Config and log: `%LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\CarpetBombNative.cfg` / `CarpetBombNative.log`. Use `bomb=170/192/239/286/141/188`, `direction=90/180`, or `manager`. Old configs missing direction use the manager choice, normally left/right. Existing settings are retained; comments and unknown keys survive saves. Disable restores owned settings and stops future shifts; component aliases remain allocated until process exit to keep existing aircraft references valid.

In v0.5.5, 43 offline groups covered all six payloads, dependency references, both approach values, menu persistence and bilingual refresh, conflicts, partial failures, restoration, caching and package integrity. 46 preset modules represent 70,200 selectable combinations, not individual gameplay tests. **v0.5.5 has not been tested in game or multiplayer.** Original-data snapshot verification passed on 2026-10-16; equivalence of the older decoded reference to current originals remains NOT ESTABLISHED. Runtime identity and code guards remain enabled. Dependency evidence: `tests/fixtures/bomb_variants_build25480438.json`.

Historical evidence: on 2026-10-04 the user reported good performance for v0.5.1-menu-perf2, without CPU/FPS measurements. Earlier 200 kg / forward 80 m and 500 kg / forward 0 m results belong to v0.5.1. v0.5.2 was withdrawn after a reported regression. These results do not verify the new payloads or approach selector.

See [menu instructions](README_MODS菜单.md), [Chinese runtime instructions](README_中文.md), [validation](validation/report.json), and [credits](CREDITS.md).

Build with Python 3.12 and `python -m pip install -r requirements-dev.txt`, then `python tools/build.py` (output under `dist`, ignored by Git). Validate: `python tests/test_runtime.py`. Build gates reject stale or failed reports. Tests use a menu API contract fixture by default; set `HD2_MOD_OPTIONS_MENU_SOURCE` to the external version2 provider's Lua source to test its real API in isolation. No third-party menu source or game assets are distributed, and tests do not install the native UI hook or interact with the game.
