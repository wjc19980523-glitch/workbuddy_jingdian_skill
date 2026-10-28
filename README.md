# 城市景点视频 skill（WorkBuddy）

输入一个城市名，自动调研、填景点表、下载授权照片与卫星图，渲染一条约 50–60 秒的竖屏景点展示片（卫星俯冲开场、每景不同运镜、地图转场、照片墙收尾、结尾一个评论区提问）。

## 快速开始

```bash
./run.sh 杭州            # 正式档：1080×1920 / 30fps
./run.sh 杭州 --draft    # 试看档：540×960 / 15fps，更快
```

反复运行同一条命令；它做完所有脚本步骤，只在需要你填 `spots.json` 或挑图时停下。完整步骤见 [SKILL.md](SKILL.md)。

## 目录

- `SKILL.md`：给 WorkBuddy（或其他执行模型）的完整用法
- `run.sh`：唯一入口
- `template/`：冻结模板（画面/运镜/工具脚本），执行模型不改这里
- `examples/huzhou/`：湖州示例（成片约 56s，7 景）
- `examples/hangzhou/`：杭州示例（WorkBuddy 验收填表）
- `REPORT.md`：湖州成片与待核对说明

成片视频、渲染中间文件和 `node_modules` 不入库（见 `.gitignore`），本地运行时重新生成。

## 许可

MIT，见 [LICENSE](LICENSE)。示例图片来自各自出处，见各城市的 `image-sources.md`。
