#!/bin/bash
# 28/28 도달 시 결과·스크립트를 저장소 안에 tar 로 묶어 둔다.
# 파일 API 루트가 /home/mlp 이므로 저장소 안에 두어야 내려받을 수 있다(/tmp 는 사정권 밖).
R=/home/mlp/hgyoo/bubble/codex/star-bench/STAR-Bench
OUT=$R/_experiments/_backup/goldfix_final
cd "$R" || exit 9
mkdir -p "$OUT"
count() { local n=0
  for f in _experiments/results_kr/checkpoint/*.jsonl; do
    c=$(awk -F'"case_id": "' 'NF>1{split($2,a,"\""); print a[1]}' "$f" 2>/dev/null \
        | grep -E '^st_(pf|mtool|fiu)_' | sort | uniq -d | wc -l)
    [ "$c" -eq 68 ] && n=$((n+1))
  done; echo $n; }
echo "[$(date '+%F %H:%M:%S')] 감시 시작 (현재 $(count)/28)" >> "$OUT/watch.log"
for i in $(seq 1 90); do
  n=$(count)
  if [ "$n" -ge 28 ]; then
    echo "[$(date '+%F %H:%M:%S')] 28/28 도달 — 묶음 생성" >> "$OUT/watch.log"
    TS=$(date +%Y%m%d_%H%M%S)
    { echo "생성 $(date '+%F %H:%M:%S')  서버 $(hostname)"; echo "완료 설정 $n/28"; echo
      echo "설정별 금키 재실행(중복 case_id) 수:"
      for f in _experiments/results_kr/checkpoint/*.jsonl; do
        c=$(awk -F'"case_id": "' 'NF>1{split($2,a,"\""); print a[1]}' "$f" \
            | grep -E '^st_(pf|mtool|fiu)_' | sort | uniq -d | wc -l)
        printf "  %-52s %s/68\n" "$(basename "$f" .jsonl | sed 's/^checkpoint_//')" "$c"
      done
      echo; echo "빈 eval(total_cases=0):"
      grep -l '"total_cases": 0' _experiments/results_kr/eval/*.json 2>/dev/null | sed 's/^/  /' || echo "  없음"
    } > "$OUT/MANIFEST_$TS.txt"
    tar czf "$OUT/goldfix_final_$TS.tar.gz" \
      _experiments/results_kr/eval _experiments/results_kr/checkpoint \
      _experiments/logs/goldfix _experiments/scripts/goldfix_remote \
      _experiments/scripts/run_benchmark.sh _experiments/scripts/run_benchmark_fin.sh \
      _experiments/scripts/run_benchmark_fin2.sh _experiments/rerun_gold_fix \
      "_experiments/_backup/goldfix_final/MANIFEST_$TS.txt" 2>/dev/null
    echo "[$(date '+%F %H:%M:%S')] 완료 $(ls -la "$OUT/goldfix_final_$TS.tar.gz" | awk '{print $5}') bytes" >> "$OUT/watch.log"
    echo "READY $OUT/goldfix_final_$TS.tar.gz" > "$OUT/READY.txt"
    exit 0
  fi
  sleep 180
done
echo "[$(date '+%F %H:%M:%S')] 타임아웃 ($(count)/28)" >> "$OUT/watch.log"
