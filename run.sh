#!/bin/bash
# 城市景点竖屏视频 —— 唯一入口。反复运行同一条命令；它做完所有脚本步骤，只在需要你填数据时停下并说明下一步。
#
#   ./run.sh <城市名>            正式版 1080x1920 30fps
#   ./run.sh <城市名> --draft    试看版 540x960 15fps（快 6–8 倍）
#
# 退出码：0 成片完成 · 10 填 spots.json · 11 挑图 · 1 按 ERROR 改数据 · 2 网络/环境问题（直接重跑）
set -o pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"; T="$ROOT/template/tools"
NAME="${1:?用法：./run.sh <城市名> [--draft]}"; NAME="${NAME%市}"; shift
DRAFT="$1"
say() { echo "RUN.SH EXIT $1：$2"; exit "$1"; }

# 1 · 找到或创建城市目录
CITY=""
for f in "$ROOT"/examples/*/city.json; do
  [ -f "$f" ] && python3 -c "import json,sys;sys.exit(0 if json.load(open(sys.argv[1])).get('name')==sys.argv[2] else 1)" "$f" "$NAME" && CITY="$(dirname "$f")"
done
if [ -z "$CITY" ]; then
  echo "== STEP 1 初始化 $NAME：地理编码 + 下载城市资料"
  CITY=$(python3 -I "$T/init_city.py" "$NAME" "$ROOT/examples" | tail -1) || say 2 "初始化失败（网络？），直接重跑"
  [ -f "$CITY/spots.json" ] || say 2 "初始化失败，直接重跑"
fi
cd "$CITY" || exit 2
echo "城市目录：$CITY"

# 2 · spots.json 还没填
if ! python3 -c "import json,sys;d=json.load(open('spots.json'));sys.exit(0 if d.get('spots') else 1)" 2>/dev/null; then
  cat <<EOF
== 下一步（STEP 2）：填 $CITY/spots.json
   读 research/candidates.md 挑 5–8 个景点；每个景点先下载两份资料：
     python3 -I $T/wiki.py wp $CITY/research <维基条目名> ...
     python3 -I $T/wiki.py bk $CITY/research <词条名> ...
   再按 SKILL.md §2 写 spots.json（格式见 template/spots.example.json），然后重跑：./run.sh $NAME $DRAFT
EOF
  say 10 "填 spots.json"
fi

# 3 · 校验文字与引文
python3 -I "$T/check.py" . --stage text || say 1 "按上面的 ERROR 改 spots.json 后重跑"

# 4 · 坐标
python3 -I "$T/geocode.py" . || say 1 "按上面的提示改 geo 后重跑"

# 5 · 图片候选 → 等待挑图
if python3 -c "import json,sys;d=json.load(open('spots.json'));sys.exit(0 if any('images' not in s for s in d['spots']) else 1)"; then
  python3 -I "$T/find_images.py" . || say 2 "Commons 搜索失败（网络？），直接重跑"
  cat <<EOF
== 下一步（STEP 3）：挑图
   打开 $CITY/research/images.md，给每个景点写 "images": [{"pick": "s01-3", "caption": "图注"}, ...]（2–3 张）。
   候选都不合适：改该景点的 imageQuery，并删掉它的 images 字段，重跑会刷新候选。然后：./run.sh $NAME $DRAFT
EOF
  say 11 "挑图"
fi
python3 -I "$T/find_images.py" . >/dev/null 2>&1   # refresh candidates for spots whose imageQuery changed
python3 -I "$T/check.py" . --stage images || say 1 "按上面的 ERROR 改 images 后重跑"

# 6 · 下载图片（授权 + AI 过滤）、卫星图
python3 -I "$T/fetch_images.py" . || say 2 "图片下载失败（网络？），直接重跑"
if [ ! -f assets/map/local.json ] || [ ! -f assets/map/wide.json ]; then
  echo "== 下载卫星图（5–15 分钟）"
  python3 -u -I "$T/fetch_map.py" . || say 2 "卫星图下载失败（网络？），直接重跑"
fi

# 7 · 时间线、配乐、出处清单、渲染、合成
echo "== 渲染（试看版约 5 分钟，正式版约 20–40 分钟；可以 nohup 放后台，见 SKILL.md §5）"
"$ROOT/template/render.sh" "$CITY" $DRAFT || say 2 "渲染失败：看上面的报错；直接重跑会接着已渲染的帧继续"
echo "DONE"
say 0 "成片完成：$CITY"
