# Native CarpetBomb

Native hidden CarpetBomb (↑ → ↑ → ↑ →), automatically carried alongside Resupply without occupying a chosen slot. Requires Bingus Shared Loader v18. Supported Steam build: 25480438 / EXE 1.8.46015.0.

v0.5.1 offers independent charges, interval between uses, shared Eagle rearm cooldown, bomb selection (Airstrike / native 200 kg / Eagle 500 kg), and forward target offset (0 /40 /80 /120 /160 metres). Quantity is temporarily fixed at vanilla 1x, 20 bombs per aircraft. Requested quantity multipliers remain unfinished.

The experimental quantity implementation was withdrawn after a GameGuard 1015 bridge report. The current source removes executable-code writes. The exact earlier trigger was not isolated. No external game-memory inspection is used for new live tests.

The earlier 200 kg/vanilla-quantity field test succeeded near the beacon. v0.5.1 cold start and 200 kg/1x/80-metre forward adjustment passed; the user observed more even coverage on both sides of the beacon. The 500 kg/1x/0-metre field test also passed, with the user confirming normal bomb drops. Sixteen offline groups and 41 preset modules pass. Multiplayer is unverified.

Import `NativeCarpetBomb_v0.5.1.zip` with Arsenal/HD2MM and deploy with the loader's documented priority. The 200 kg/80-metre coverage and 500 kg/0-metre bomb drops have been field-tested. Other combinations remain unverified. See [Chinese instructions](README_中文.md), [validation](validation/report.json), and [credits](CREDITS.md). Download [v0.5.1](https://github.com/abaabaaba234/carpet-bomb-native/releases/tag/v0.5.1). v0.5.2 has been withdrawn after a user-reported regression; this release restores the earlier field-tested runtime unchanged.

Build: `python tools/build.py`. Validate: `python tests/test_runtime.py`. Install development requirements from `requirements-dev.txt`.
