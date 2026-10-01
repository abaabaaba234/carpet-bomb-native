# 原生地毯式轰炸 / Native CarpetBomb

为《绝地潜兵 2》恢复原生地毯式轰炸战备，并在进入新任务时自动携带，不占四个自选槽位。当前版本 **v0.4.0**，需要 [Bingus Shared Loader v18](https://github.com/CowboyBingus/BingusSharedLoader/releases/tag/v18)。

## 下载与安装

从 [Releases](https://github.com/abaabaaba234/carpet-bomb-native/releases) 下载 `NativeCarpetBomb_v0.4.0.zip`，关闭游戏，在 Arsenal / HD2MM 中导入、启用并部署。通过管理器替换旧版本；加载器顺序按其说明设置。进入新任务后输入 **↑ → ↑ → ↑ →** 调用地毯式轰炸。

支持 Steam build **25480438** / EXE **1.8.46015.0**。完整安装、配置和移除说明见 [中文说明](README_中文.md)。

## 管理器设置

| 选项 | 含义 | 默认值 |
| --- | --- | --- |
| 使用次数 | 重新装填前可使用的次数 | 2 次 |
| 调用冷却（每次使用之间） | 地毯式轰炸两次使用之间的基础间隔 | 15 秒 |
| 飞鹰返航装填冷却 | 次数耗尽或手动重新武装后返航装填的基础时间 | 保持原版 |

返航装填冷却为所有携带的飞鹰共用，舰船升级仍由游戏计算。可选保持原版，或 0、5、10、15、30、60、120、150、180、300、600、900 秒。调整管理器选项后重新部署并重启游戏。

## 构建与验证

构建安装包仅使用 Python 标准库。离线测试需要带 LuaJIT 的 Lupa；已验证 Python 3.12 / Lupa 2.8。

```powershell
python -m pip install -r requirements-dev.txt
python tools/build.py
python tests/test_runtime.py
```

输出为 `dist/NativeCarpetBomb_v0.4.0.zip`。源码位于 `src/core.lua`，选项清单位于 `manifest.json`，测试位于 `tests/`。`tools/` 中其余脚本用于本地诊断和历史测试，部分包含本机游戏路径；常规安装使用管理器。

已通过 12 组离线检查，检查 32 个预设模块，可选择 1170 种参数组合。v0.4.0 完整包通过管理器冷启动；实机验证装填参数从原版 150 秒改为 30 秒并恢复，次数和调用间隔保持原样。120 米进场高度修复此前已确认在信标附近投弹。本次未重新计时完整装填周期，联机同步未验证。详细记录见 [验证报告](validation/report.json)。

## 参考

依赖与研究参考见 [CREDITS.md](CREDITS.md)。安装包不包含加载器、其他 mod 源码或游戏素材；运行时使用游戏已有资源。
