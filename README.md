# Casa Tres Patis · 完整动画渲染交接

**执行入口：[渲染交接文档.md](渲染交接文档.md)。请先完整读取，再检查环境并启动渲染。**

用户最终确认：**24fps / 1920×1080 / 200秒 / 4800帧 / 无字幕**。Cycles画质与已确认的10秒样片一致；每30分钟低频监控。

- `project/`：完整可渲染Blender工程，含最新M3柱体修复、R3路线、开门和季节/片尾淡变。
- `config/render.json`：固定画质及范围。
- `scripts/start_render.py`：检测/安装Blender、后台启动、续渲及编码入口。
- `scripts/render.py`：原生Blender环境检查、预检、实际渲染、编码和验证。
- `reference/`：此前已确认的10秒1080p24无字幕样片。
- `docs/`：设计理念、来源、镜头时间轴和画质基准。
- `captions/`：仅供后期使用的200秒SRT；**不烧录到本次动画**。
- `manifest.json`：工程与必要文件的SHA-256；`validation/`为本机交接核验记录。

本包不需要CamWeave、Blender MCP、字体、外部模型/纹理或模拟缓存。位置、朝向、季相与水纹均通过原生动画/驱动实现。渲染结果和临时安装在Git忽略目录内保留。

作品和参考归属见[NOTICE.md](NOTICE.md)，不将重建模型写成原作的精确复原。

本机打包核验已通过：同源工程、无外链、24fps/4800帧、原生相机和季节/淡变数据、单帧Cycles全质量试渲。见[package_validation.json](validation/package_validation.json)。目标电脑仍必须重新探测环境和预检。

公开仓库：https://github.com/KanadeCheng/casa-tres-patis-render-handoff
