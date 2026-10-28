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
- `examples/`：运行时按城市自动生成（如 `examples/huzhou/`），仓库内不预置任何城市素材
- `REPORT.md`：简要说明（历史验收记录已清空）

照片、卫星图、成片视频、调研文本、`spots.json`、渲染中间文件和 `node_modules` 都不入库；运行 `./run.sh <城市>` 时由脚本重新下载与生成。

## 安装说明（WorkBuddy）

本仓库刻意做得很轻，方便国内网络安装。若你本地还残留上次装到一半的大文件目录，先删掉再重装：

```text
~/.workbuddy/skills/ 下对应的 jingdian / city-scenic 目录
```

然后重新从本仓库安装即可。

## 许可

MIT，见 [LICENSE](LICENSE)。示例文案与调研文本仅作格式参考；图片授权以各城市本地生成的 `image-sources.md` 为准。
