# Native CarpetBomb

Native hidden CarpetBomb (↑ → ↑ → ↑ →), automatically carried alongside Resupply without occupying a chosen slot. Requires Bingus Shared Loader v18. Supported Steam build: 25480438 / EXE 1.8.46015.0.

v0.5.2 removes the forward-offset dropdown, configuration field, and runtime aircraft-target adjustment. Aircraft use their original target positions. Legacy `forward` presets and configuration entries are ignored. Independent charges, interval between uses, shared Eagle rearm cooldown, and bomb selection (Airstrike / native 200 kg / Eagle 500 kg) remain available.

Quantity is fixed at vanilla 1x, 20 bombs per aircraft. Quantity multipliers are not included in this release. The experimental quantity implementation was withdrawn after a GameGuard 1015 bridge report; the exact trigger was not isolated. The current source makes no executable-code writes. No external game-memory inspection is used for new live tests.

Earlier v0.5.1 tests confirmed normal 200 kg and 500 kg bomb drops. This release uses native targeting with no forward adjustment. v0.5.2 cold start and field testing are pending; multiplayer is unverified.

Close the game, import `NativeCarpetBomb_v0.5.2.zip` over the old version with Arsenal/HD2MM, then Purge + Deploy with the loader's documented priority and restart. Remove the old version if your manager imports it as a separate mod. See [Chinese instructions](README_中文.md), [validation](validation/report.json), and [credits](CREDITS.md). Download [v0.5.2](https://github.com/abaabaaba234/carpet-bomb-native/releases/tag/v0.5.2).

Build: `python tools/build.py`. Validate: `python tests/test_runtime.py`. Install development requirements from `requirements-dev.txt`.
