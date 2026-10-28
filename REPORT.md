# 湖州景点竖屏视频 + city-scenic skill · REPORT

生成时间：2026-10-28 约 22:03（Asia/Shanghai）  
说明：Claude Code 主跑已产出成片与 skill；因 Claude Pro 5 小时额度耗尽（重置 1:10am Asia/Shanghai），本 REPORT 由监控进程根据 Claude 已落盘产物整理，未推送、未发布。

## 成片

| 项 | 路径 / 值 |
|---|---|
| mp4 | `/workspace/opc-videos/huzhou-scenic/v1/city-scenic-skill/examples/huzhou/huzhou-scenic.mp4` |
| 封面 | `…/examples/huzhou/cover.png` |
| 缩略帧 contact | `…/examples/huzhou/contact.jpg` |
| 时长 | **56.0 s** |
| 分辨率 | **1080×1920** |
| 帧率 | **30 fps** |
| 视频编码 | H.264 · 1680 帧 |
| 音频 | AAC（程序合成 score.wav，约 56.6 s） |
| 体积 | ≈139 MB（145624176 bytes） |

备份（重渲前）：`examples/huzhou/huzhou-scenic.mp4.bak-2155`（21:55 首版，同规格）。

## Skill 与工程

| 项 | 路径 |
|---|---|
| skill 根目录 | `/workspace/opc-videos/huzhou-scenic/v1/city-scenic-skill/` |
| SKILL.md | `…/city-scenic-skill/SKILL.md` |
| 入口 | `…/city-scenic-skill/run.sh <城市名> [--draft]` |
| 模板 | `…/city-scenic-skill/template/`（src、tools、render.sh、spots.example.json） |
| 湖州示例 | `…/city-scenic-skill/examples/huzhou/` |
| 史实出处 | `…/examples/huzhou/sources.md` |
| 图片授权 | `…/examples/huzhou/image-sources.md` |
| 待核对 | `…/examples/huzhou/REVIEW.md` |
| 节点表 | `…/examples/huzhou/spots.json` |
| brief / prompt | `/workspace/opc-videos/huzhou-scenic/v1/brief-v1.md`、`final-prompt.txt` |

## 景点列表（7）与运镜

结尾提问：**「湖州这7个地方，你最想先去哪一个？」**（仅评论区提问；无账号名、无粉丝群）

| # | 景点 | 地点 | 运镜 | 上屏事实摘要 |
|---|---|---|---|---|
| 1 | 月亮酒店 | 南太湖 | ring | 马岩松主创；正名湖州喜来登温泉度假酒店 |
| 2 | 飞英塔 | 吴兴区 · 塔下街 | tilt | 塔中有塔、外塔通高55米；1988 国保 |
| 3 | 小西街 | 湖州古城 · 中心城区 | bands | 名门望族聚居（待核对）；钮氏状元厅 |
| 4 | 南浔古镇 | 南浔区 | pano | 1252 建镇；“湖州一个城，不及南浔半个镇”（待核对） |
| 5 | 莫干山 | 德清县 | carousel | 四大避暑胜地之一；干将莫邪传说 |
| 6 | 安吉竹乡 | 安吉县 | strips | “中国竹乡” |
| 7 | 余村 | 安吉县 · 天荒坪镇 | bloom | “绿水青山就是金山银山”；2005-08 在余村提出 |

片头钩子：7 张照片快闪 +「飞越湖州」；卫星图俯冲开场；景点间多种转场；结尾 3D 照片墙 + 全城路线图 + 提问。

## AI 内容标注

- **全片无 AI 生成实景画面**；照片均来自 Wikimedia Commons（公有领域 / CC0 / CC BY / CC BY-SA），地图为 NASA GIBS 卫星影像，配乐由 `music.py` 程序合成。
- 片尾字幕（`endCredits`）：「本片由 AI 辅助剪辑；画面均为实拍授权照片与卫星影像，无 AI 生成画面」。
- 模板预留角标「AI生成画面」（默认隐藏）；若 `images` 条目带 `"ai": true` 会自动显示。本片未启用。

## 未核实 / 待人工核对

见 `REVIEW.md` / `sources.md`：

1. **小西街**：「历代名门望族聚居之地」— 仅维基一处，⚠ 待核对  
2. **南浔古镇**：「湖州一个城，不及南浔半个镇」— 仅一处，⚠ 待核对  
3. 地名小字（where）与图注（caption）由模型填写，脚本只查长度/禁用词，**未逐字核对**。

其余上屏事实脚本已对维基百科 + 快懂百科引文逐字比对（标记「已核」）。

## WorkBuddy 复用与阻塞点

- Skill 设计：轻量模型**只填 `spots.json` / 挑图编号**，不写代码；地理编码、Commons 下载与授权过滤、卫星图、配乐、渲染均脚本化。`./run.sh <城市>` 可反复跑到 `RUN.SH EXIT 0`。
- `--draft` = 540×960 @15fps 试看；正式为 1080×1920 @30fps。长任务需 `nohup`（SKILL.md 已写）。
- Claude 在额度耗尽前已启动 **WorkBuddy + DeepSeek V4.1 flash** 杭州验收（只给城市名「杭州」、`--draft`），进程仍在跑：`examples/hangzhou/` 已有 spots/图片，正下载卫星图；**杭州 draft mp4 尚未完成**，不能算验收通过。
- 阻塞 / 风险：
  1. **正式渲染约数十分钟**，WorkBuddy 单条命令超时需严格按 SKILL 后台跑，否则会像年轮 skill 那样卡死。
  2. 单源事实会进 REVIEW.md，**发布前需人审**。
  3. Claude Code 本会话 **5h limit 至 1:10am Asia/Shanghai**；与 WorkBuddy/DeepSeek 无关，但无法再用 Claude 收尾改片。
  4. 卫星图依赖 NASA GIBS；网络/代理异常会卡在 `fetch_map`。
  5. 未做 Git 推送；仓库推送仍由 OPC运营负责。

## 未做

- 未推送 GitHub、未发飞书、未发布任何平台。
