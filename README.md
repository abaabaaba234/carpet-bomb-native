# Native CarpetBomb v0.6.1

[Download v0.6.1 ZIP](https://github.com/abaabaaba234/carpet-bomb-native/releases/download/v0.6.1/NativeCarpetBomb_v0.6.1.zip) · [Release notes](https://github.com/abaabaaba234/carpet-bomb-native/releases/tag/v0.6.1) · [中文说明](README_中文.md)

v0.6.1 adds incremental preparation, ship-idle scheduling, recoverable faults, table-replacement handling and resumable menu registration. Detailed diagnostics default off. Runtime compatibility uses code/layout checks rather than a game-version allowlist. Existing gameplay settings are retained.

On 2026-10-17 the author confirmed testing both updates without observing problems in their own environment. Reports lacked specific errors or same-session logs, so these are tentative fixes based on possible causes and are NOT guaranteed to fully resolve every player's ship stutter, loading failure or intermittent behavior. This Release uses the exact ZIP uploaded to AyakaMods, without rebuilding it.

Adds Extra beacon delay (seconds): 0-60 seconds, one-second steps, default 0 to preserve current timing. Set it under Esc → MODS → Native CarpetBomb and Apply. Manager presets are 0/3/5/8/10/15/20/30/60 seconds. Try 5 seconds first, then 8 or 10 if more escape time is needed. Missing `call_delay` follows the manager; `call_delay=5` adds 5 seconds, and `call_delay=manager` restores the deployed preset.

This adds to the native beacon activation delay for future CarpetBomb calls. Arrival also includes flight time and game modifiers; it is not an exact beacon-to-first-explosion duration. Running countdowns keep their values. Zero or Disable restores the owned baseline. Other Eagles, the interval between calls and Eagle rearm remain independent.

On 2026-10-16 the user confirmed v0.5.9 cluster timing was now just right. Its actual-height release, native 0.35-second split timer, 20 primaries per aircraft and 8 native bomblets per primary are retained. 69 offline groups pass, including six-payload delay edits, a nonzero baseline, persistence/restart, preset restoration, competing writers and partial failures. The author also reports successful local gameplay testing of v0.6.1 on 2026-10-17; multiplayer and every preset combination remain unverified.

Native hidden CarpetBomb (↑ → ↑ → ↑ →), automatically carried alongside Resupply without occupying a chosen slot. Includes Eagle Cluster, Napalm and Gas payloads, and a left/right or front/back approach selector. Requires Bingus Shared Loader v18 / API 1. The optional MODS menu requires separate Bingus ModOptionsMenu API 1 / version 2+. Reference layout: Steam build 25480438 / EXE 1.8.46015.0; PE architecture/bounds, code anchors and record identity are still checked, without exact timestamp/image-size matching. Changed RVAs/layouts may require adaptation; future versions are not verified; offline tests run LuaJIT 2.1 (`lupa.luajit21`, lupa 2.8).

| Setting | Choices |
| --- | --- |
| Bomb | Airstrike (default), CarpetBomb 200 kg, Eagle 500 kg, Eagle Cluster, Eagle Napalm, Eagle Gas |
| Approach | Left/right across the throw (default), front/back along the throw |
| Extra beacon delay | 0-60 seconds, default 0; manager presets and MODS slider |
| Other settings | Enable, charges, call interval, shared Eagle rearm cooldown, forward target offset |

Each parameter can follow its manager preset or use an independent override. Titles, labels and choices support Chinese (default) and English; descriptions always display both languages. Quantity stays at 20 primary bombs per aircraft. Cluster uses native projectile 286, which releases 8 secondary bomblets per primary bomb through explosion 417, increasing projectile/effect load. Napalm and Gas retain their native fire/status definitions. The selected native loadout package supplies the corresponding resources. Other Eagle records, projectile damage and ship upgrade definitions remain untouched. See the [historical performance audit](PERFORMANCE_AUDIT.md) and [recovery audit](RELIABILITY_AUDIT.md).

Import `NativeCarpetBomb_v0.6.1.zip` with Arsenal / HD2MM, replacing the older package. Purge and Deploy with the loader's documented priority, restart, and enter a new mission. Open Esc → MODS → Native CarpetBomb, then Apply to save. Bomb changes require a restart and a new mission to load resources; charges and running timers may require a new mission. Approach changes affect newly spawned aircraft; aircraft already in flight keep their copied settings. Forward offset follows the selected flight axis. Close and reopen Esc after a language change.

Config and log: `%LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\CarpetBombNative.cfg` / `CarpetBombNative.log`. Use `bomb=170/192/239/286/141/188`, `direction=90/180`, or `manager`. Old configs missing direction use the manager choice, normally left/right. Existing settings are retained; comments and unknown keys survive saves. Disable restores owned settings and stops future shifts; component aliases remain allocated until process exit to keep existing aircraft references valid.

The current 55 preset modules offer 631,800 selectable combinations, not individual gameplay tests. Current user feedback is recorded in [field feedback](validation/field_feedback_20261016.json); multiplayer remains unverified.

See [menu instructions](README_MODS菜单.md), [Chinese runtime instructions](README_中文.md), [validation](validation/report.json), and [credits](CREDITS.md).

Build with Python 3.12 and `python -m pip install -r requirements-dev.txt`, then `python tools/build.py` (output under `dist`, ignored by Git). Validate: `python tests/test_runtime.py`. Build gates reject stale or failed reports. Tests use a menu API contract fixture by default; set `HD2_MOD_OPTIONS_MENU_SOURCE` to the external version2 provider's Lua source to test its real API in isolation. No third-party menu source or game assets are distributed, and tests do not install the native UI hook or interact with the game.

The repository keeps current runtime, build tools, tests and validation. Obsolete experiments remain available in Git history.

## v0.6.1 lifecycle and troubleshooting

Preparation and grant publication remain available before a mission so packages can load. Preparation handles at most two tables per frame, retaining hash-probe cursors and yielding after 64 probes per step; publication follows complete validation. No private allocation is made while waiting for required tables.

Once prepared, the ship path performs only light scene checks (at most every 0.25 seconds) and approximately five-second configuration/menu/static checks. Aircraft, projectile, cluster-height and diagnostic polling stop outside missions. Menu Apply schedules work immediately; external file edits wait for the next poll. Mission exit clears dynamic tracking while retaining the next mission's grant/resources.

`waiting`/`preparing` describe dependencies/preparation; `active` means prepared, with `in_mission` indicating mission context. `disabled` preserves an explicit off setting; `suspended` means native work paused safely. Fault cleanup retains failed records: the first three rounds are at least one second apart, later rounds at least 30 seconds apart. After cleanup, retries back off from 1 to 30 seconds. Foreign values are preserved; unreadable pointers do not prove retirement. Confirmed replacement allocations retire old static records without dereferencing them, then new records/tables are validated. Known aliases and private Eagles are reused where valid. At most four private allocations are retained per process; reaching that limit pauses with a restart message. Published pointers are never freed early.

Loader API 1 and required methods are checked (v18 recommended). Late dependencies retry through an existing update; missing update leaves no success marker so the addon can be run again later. Partial menu registration/binding/synchronization resumes without duplicate callbacks. Replacing the provider resets its registration state. Original update arguments, trailing nil return values and errors pass through. Another MOD that overwrites update without chaining it, or an older package loading first, still requires deployment/package correction; duplicate versions are logged.

Set `diagnostics=1` in the config only when investigating detailed flight/cluster traces; default is `0`. Necessary cluster fuse and height handling continue in production mode. Repeated logs are deduplicated for 30 seconds with at most 64 entries; log failures do not interrupt the original update. Bomb changes still require a restart/new mission, and existing charges or timers may require a new mission.

All 69 offline groups pass, including real menu-API isolation, preparation budgets/long probe chains, ship-idle and mission transitions, moved records/tables, ownership recovery and partial menu failures. In a 60-second simulated ship comparison, RPM calls fell from 5,280 to 1,118; aircraft/projectile-system polls fell to zero and config reads fell from 60 to 11. These counts do not establish a real FPS improvement. See PERFORMANCE_AUDIT.md for the comparison conditions. The later author-reported local gameplay test is separate from the offline report, whose flags retain the original offline validation scope. Multiplayer remains unverified.
