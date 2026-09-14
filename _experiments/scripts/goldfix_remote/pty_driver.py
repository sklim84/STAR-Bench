#!/usr/bin/env python3
"""H200 웹콘솔 PTY 드라이버. start/input/read 폴링 계약을 그대로 쓴다.

접속 정보는 코드에 두지 않는다. Cloudflare 임시 터널은 재시작마다 주소와
토큰이 바뀌므로 하드코딩해도 곧 무효가 된다. 실행 전에 환경변수로 준다:

    export H200_BASE='https://<임시>.trycloudflare.com'
    export H200_TOKEN='<모니터 토큰>'
    export H200_COOKIE_JAR=/tmp/remote_jar.txt   # 선택, 기본값 동일

쿠키는 먼저 unlock 으로 받아 jar 에 저장해 둔다(비밀번호는 사용자에게 받는다):
    curl -c "$H200_COOKIE_JAR" -H 'Content-Type: application/json' \
         -d '{"password":"<비밀번호>"}' \
         "$H200_BASE/api/terminal/unlock?token=$H200_TOKEN"

사용: python3 pty_driver.py '<명령>' [타임아웃초]
"""
import json, os, re, sys, time, urllib.request

BASE = os.environ.get("H200_BASE", "").rstrip("/")
TOKEN = os.environ.get("H200_TOKEN", "")
JAR = os.environ.get("H200_COOKIE_JAR", "/tmp/remote_jar.txt")
SESS_FILE = os.environ.get("H200_SESSION_FILE", "/tmp/remote_session.txt")

if not BASE or not TOKEN:
    sys.exit("H200_BASE 와 H200_TOKEN 을 환경변수로 설정하십시오 (docstring 참조).")

COOKIE = ""
try:
    for line in open(JAR, encoding="utf-8"):
        if "webconsole_terminal_auth" in line:
            COOKIE = "webconsole_terminal_auth=" + line.split()[-1]
except OSError:
    sys.exit(f"쿠키 jar 를 열 수 없습니다: {JAR} (unlock 을 먼저 수행하십시오.)")
if not COOKIE:
    sys.exit(f"{JAR} 에 webconsole_terminal_auth 쿠키가 없습니다.")


def call(path, body=None, query=""):
    url = f"{BASE}{path}?token={TOKEN}{query}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    req.add_header("Cookie", COOKIE)
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def start(cwd="/home/mlp"):
    d = call("/api/terminal/start", {"cwd": cwd, "rows": 50, "cols": 200})
    open(SESS_FILE, "w").write(d["session_id"])
    return d["session_id"], int(d.get("offset", 0))


def session():
    try:
        sid = open(SESS_FILE).read().strip()
        d = call("/api/terminal/read", query=f"&session_id={sid}&offset=0")
        if d.get("alive"):
            return sid, int(d.get("offset", 0))
    except Exception:
        pass
    return start()


ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07|\r")


def run(cmd, timeout=180):
    sid, off = session()
    mark = f"__EOC_{int(time.time()*1000)}__"
    call("/api/terminal/input", {"session_id": sid, "data": f"{cmd}; echo {mark}\r"})
    buf, t0 = "", time.time()
    while time.time() - t0 < timeout:
        time.sleep(1.2)
        d = call("/api/terminal/read", query=f"&session_id={sid}&offset={off}")
        buf += d.get("text", "")
        off = int(d.get("offset", off))
        if mark in buf and buf.count(mark) >= 2:
            break
        if not d.get("alive"):
            break
    out = ANSI.sub("", buf)
    lines = [l for l in out.split("\n") if mark not in l and not l.strip().endswith("$")]
    return "\n".join(lines).strip()


if __name__ == "__main__":
    print(run(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 180))
