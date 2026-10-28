#!/bin/bash
# WorkBuddy (codebuddy CLI) + DeepSeek V4.1 flash acceptance run: input = city name only.
cd /workspace/opc-videos/huzhou-scenic/v1/city-scenic-skill
export https_proxy=http://127.0.0.1:7890 http_proxy=http://127.0.0.1:7890
for i in 1 2 3 4 5 6; do
  C=""; [ $i -gt 1 ] && C="-c"
  P="$(cat workbuddy-test/prompt.txt)"; [ $i -gt 1 ] && P="继续，按 SKILL.md 反复运行 ./run.sh 杭州 --draft 直到最后一行是 RUN.SH EXIT 0。渲染很慢时用 nohup 放后台并轮询。"
  echo "=== round $i $(date)" >> workbuddy-test/workbuddy.log
  timeout 5400 codebuddy $C -p "$P" --model deepseek-v4.1-flash -y --output-format stream-json --verbose >> workbuddy-test/workbuddy.jsonl 2>> workbuddy-test/workbuddy.log
  echo "=== exit $? $(date)" >> workbuddy-test/workbuddy.log
  [ -f examples/hangzhou/hangzhou-scenic-draft.mp4 ] && break
done
echo DONE >> workbuddy-test/workbuddy.log
