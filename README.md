# Native CarpetBomb v0.5.7-diagnostic

Cluster-only diagnostic follow-up. The user tested v0.5.6-diagnostic on 2026-10-16: 200 kg front/back at +80 m covered the beacon as intended; Napalm and Gas were usable, and the other tested choices were reported usable. Cluster remained invisible with the same settings. Its first flight observations already had attacked=1 at 773–842 m, so the existing forward adjustment was skipped. This does not establish where its projectiles spawned or split.

This build adds read-only observations of recent projectile-ring slots: primary and secondary signatures, positions, velocities, delay and raw field +0x34. At most two windows of 40 samples inspect up to 512 recent slots and retain six examples per sample. Sampling runs only after a new native flight is observed with Cluster selected, including after the original 12-flight log limit. Other cluster strikes may appear in these samples; source IDs are raw metadata, not proof of native-aircraft ownership. No projectile, fuse, damage or bombing parameter changes are made. 47 offline groups pass; the new diagnostics and multiplayer remain unverified.

Close the game, import and deploy NativeCarpetBomb_v0.5.7-diagnostic.zip, retain Cluster / front-back / +80 m, restart and enter a new mission. Call it once and wait about 15 seconds; preserve CarpetBombNative.log before restarting. This is a diagnostic package, not a cluster fix.

v0.5.5 fixes the startup refusal in v0.5.4: the angle-read and angle-conversion instructions are at separate RVAs (+0x89F1A6 and +0x89F1B5). The old concatenated expectation stopped the mod before granting CarpetBomb. Runtime checks remain enabled. Tests now use independently captured code windows, reproduce the old failure and pass after the fix. No fresh in-process or gameplay verification has been performed.

Native hidden CarpetBomb (↑ → ↑ → ↑ →), automatically carried alongside Resupply without occupying a chosen slot. Includes Eagle Cluster, Napalm and Gas payloads, and a left/right or front/back approach selector. Requires Bingus Shared Loader v18 / API 1. The optional MODS menu requires separate Bingus ModOptionsMenu API 1 / version 2+. Supported Steam build: 25480438 / EXE 1.8.46015.0; offline tests run LuaJIT 2.1 (`lupa.luajit21`, lupa 2.8).

| Setting | Choices |
| --- | --- |
| Bomb | Airstrike (default), CarpetBomb 200 kg, Eagle 500 kg, Eagle Cluster, Eagle Napalm, Eagle Gas |
| Approach | Left/right across the throw (default), front/back along the throw |
| Other settings | Enable, charges, call interval, shared Eagle rearm cooldown, forward target offset |

Each parameter can follow its manager preset or use an independent override. Titles, labels and choices support Chinese (default) and English; descriptions always display both languages. Quantity stays at 20 primary bombs per aircraft. Cluster uses native projectile 286, which releases 8 secondary bomblets per primary bomb through explosion 417, increasing projectile/effect load. Napalm and Gas retain their native fire/status definitions. The selected native loadout package supplies the corresponding resources. Other Eagle records, projectile damage and ship upgrade definitions remain untouched. See the [historical performance audit](PERFORMANCE_AUDIT.md) and [recovery audit](RELIABILITY_AUDIT.md).

Import `NativeCarpetBomb_v0.5.7-diagnostic.zip` with Arsenal / HD2MM, replacing the older package. Purge and Deploy with the loader's documented priority, restart, and enter a new mission. Open Esc → MODS → Native CarpetBomb, then Apply to save. Bomb changes require a restart and a new mission to load resources; charges and running timers may require a new mission. Approach changes affect newly spawned aircraft; aircraft already in flight keep their copied settings. Forward offset follows the selected flight axis. Close and reopen Esc after a language change.

Config and log: `%LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\CarpetBombNative.cfg` / `CarpetBombNative.log`. Use `bomb=170/192/239/286/141/188`, `direction=90/180`, or `manager`. Old configs missing direction use the manager choice, normally left/right. Existing settings are retained; comments and unknown keys survive saves. Disable restores owned settings and stops future shifts; component aliases remain allocated until process exit to keep existing aircraft references valid.

In v0.5.5, 43 offline groups covered all six payloads, dependency references, both approach values, menu persistence and bilingual refresh, conflicts, partial failures, restoration, caching and package integrity. 46 preset modules represent 70,200 selectable combinations, not individual gameplay tests. **v0.5.5 has not been tested in game or multiplayer.** Original-data snapshot verification passed on 2026-10-16; equivalence of the older decoded reference to current originals remains NOT ESTABLISHED. Runtime identity and code guards remain enabled. Dependency evidence: `tests/fixtures/bomb_variants_build25480438.json`.

Historical evidence: on 2026-10-04 the user reported good performance for v0.5.1-menu-perf2, without CPU/FPS measurements. Earlier 200 kg / forward 80 m and 500 kg / forward 0 m results belong to v0.5.1. v0.5.2 was withdrawn after a reported regression. These results do not verify the new payloads or approach selector.

See [menu instructions](README_MODS菜单.md), [Chinese runtime instructions](README_中文.md), [validation](validation/report.json), and [credits](CREDITS.md).

Build with Python 3.12 and `python -m pip install -r requirements-dev.txt`, then `python tools/build.py` (output under `dist`, ignored by Git). Validate: `python tests/test_runtime.py`. Build gates reject stale or failed reports. Tests use a menu API contract fixture by default; set `HD2_MOD_OPTIONS_MENU_SOURCE` to the external version2 provider's Lua source to test its real API in isolation. No third-party menu source or game assets are distributed, and tests do not install the native UI hook or interact with the game.
