import json, glob, os, collections
R="/home/mlp/hgyoo/bubble/codex/star-bench/STAR-Bench/_experiments"
CASES=None
for p in glob.glob("/home/mlp/hgyoo/bubble/codex/star-bench/STAR-Bench/**/cases_str_workflow.json", recursive=True):
    CASES=json.load(open(p)); break
# generate_str 을 호출하는 45개 시나리오 부분집합
sub=set()
if CASES:
    for c in CASES:
        t=json.dumps(c, ensure_ascii=False).lower()
        if "generate_str" in t: sub.add(c.get("id"))
print(f"45 부분집합 크기: {len(sub)}")

def load(tag):
    out={}
    for f in glob.glob(f"{R}/results_mt_{tag}/eval/multiturn_*.json"):
        d=json.load(open(f))
        name=os.path.basename(f)[10:-5]
        out[name]=d
    return out
O, Rr = load("oracle"), load("real")
print(f"설정 수: oracle {len(O)} · real {len(Rr)}")

# 락/에러 집계 (real)
tot=err=lock=0
for d in Rr.values():
    for s in d.get("scenarios",[]):
        for t in s.get("turns",[]):
            for r in (t.get("executed_results") or []):
                tot+=1
                txt=json.dumps(r, ensure_ascii=False)
                if "Could not set lock" in txt: lock+=1
                if '"error"' in txt or "Error" in txt: err+=1
print(f"\n=== 도구 실행 (real, 28설정) ===")
print(f"  총 {tot}건 · 에러 {err}건({err/tot*100:.1f}%) · DuckDB 락 {lock}건")
print(f"  기존(오염): 5,607건 중 에러 3,136(55.9%) · 락 2,381(42.5%)")

def agg(d, use_sub):
    hs=[]; cs=[]
    for s in d.get("scenarios",[]):
        if use_sub and sub and s.get("id") not in sub: continue
        hs.append(s.get("avg_tool_hit", 0)); cs.append(1 if s.get("scenario_complete") else 0)
    return (sum(hs)/len(hs) if hs else float("nan"),
            sum(cs)/len(cs) if cs else float("nan"), len(hs))

print(f"\n=== 45 부분집합 기준 ===")
print(f"{'설정':44s} {'oracle h̄':>9s} {'real h̄':>8s} {'Δ':>7s} {'o c':>6s} {'r c':>6s} {'n':>4s}")
print("-"*90)
rows=[]
for k in sorted(O):
    if k not in Rr: continue
    oh, oc, n = agg(O[k], True); rh, rc, _ = agg(Rr[k], True)
    rows.append((k, oh, rh, rh-oh, oc, rc, n))
for k,oh,rh,d,oc,rc,n in sorted(rows, key=lambda x:-x[1]):
    print(f"{k:44s} {oh:9.4f} {rh:8.4f} {d:+7.4f} {oc:6.3f} {rc:6.3f} {n:4d}")
deg=sum(1 for r in rows if r[3]<0)
print(f"\n  E2E 에서 하락한 설정: {deg}/{len(rows)}")
print(f"  상승(역전): {[r[0] for r in rows if r[3]>0]}")
zc=sum(1 for r in rows if r[4]==0)
print(f"  oracle c == 0.000 인 설정: {zc}/{len(rows)}")
print(f"  oracle h̄ 범위 {min(r[1] for r in rows):.3f}~{max(r[1] for r in rows):.3f} · real h̄ 범위 {min(r[2] for r in rows):.3f}~{max(r[2] for r in rows):.3f}")
print(f"  평균 낙폭 {sum(r[3] for r in rows)/len(rows)*100:+.1f}pp")
