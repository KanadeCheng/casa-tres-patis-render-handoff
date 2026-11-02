# Casa Tres Patis · 完整动画渲染交接

**执行入口：[渲染交接文档.md](渲染交接文档.md)。请先完整读取，再检查环境并启动渲染。**

用户最终确认：**24fps / 1920×1080 / 200秒 / 4800帧 / 无字幕**。Cycles画质与已确认的10秒样片一致；每60分钟低频监控。


2026-11-02最新分工：**另一台电脑渲染1～3000帧，本机渲染3001～4800帧**。使用`--mode part`，完成本段后不单独编码；全部PNG到齐再统一编码。详见[两机分段渲染与合并](docs/两机分段渲染.md)。原单机完整渲染模式仅保留作技术兼容，不作为当前两机任务的默认命令。

- `project/`：完整可渲染Blender工程，含最新M3柱体修复、R3路线、开门和季节/片尾淡变。
- `config/render.json`：固定画质及范围。
- `scripts/start_render.py`：检测/安装Blender、后台启动、续渲及编码入口。
- `scripts/render.py`：既有固定画质、原生环境检查、编码和验证。
- `scripts/render_part.py`：指定起止帧的可恢复分段渲染；`merge_parts.py`：两批PNG到齐后的统一校验及汇合。
- `reference/`：此前已确认的10秒1080p24无字幕样片。
- `docs/`：仅画质基准与技术渲染帧定位。
- `manifest.json`：工程与必要文件的SHA-256；`validation/`为本机交接核验记录。

本包不需要CamWeave、Blender MCP、字体、外部模型/纹理或模拟缓存。位置、朝向、季相与水纹均通过原生动画/驱动实现。渲染结果和临时安装在Git忽略目录内保留。

任务范围仅为环境准备、渲染、续渲、编码和技术核验；不执行设计理念、模型合理性、运镜叙事或字幕内容审查。作品署名见[NOTICE.md](NOTICE.md)，不产生额外审查任务。

本机打包核验已通过：同源工程、无外链、24fps/4800帧、原生相机和季节/淡变数据、单帧Cycles全质量试渲。见[package_validation.json](validation/package_validation.json)。目标电脑仍必须重新探测环境和预检。

公开仓库：https://github.com/KanadeCheng/casa-tres-patis-render-handoff
