#!/usr/bin/env python3
"""HOFINET 사양 준수 검사: 벤치마크 케이스 전체 스캔.

`_datasets/HOFINET.MD` §2/§4/§6 기준 유효 값 검증:
- 거래시간대: {0, 3, 6, 9, 12, 15, 18, 21}
- 출금/입금금융회사: §6.5 정의 50/54개
- 자금구분: {0, 1, 3, 4}
- 매체구분: {1, 2, 3, 4, 5, 6, 7}
- 거래금액: 1 ~ 500,000,000
- 이상거래유형: {1, 2, 3, 4, 5, 7}

추가로 자연어 텍스트와 파라미터 코드 정합성 점검:
- "창구"는 매체구분에 없음 → 위반
- "PC뱅킹"이 자연어인데 매체구분≠1 → 불일치
- 기타 자연어/코드 mismatch

출력: violations.json (위반 케이스 목록 + 재실험용 ID 추출)
"""
import json
import glob
import re
from pathlib import Path
from collections import defaultdict

# HOFINET 유효 값 정의 (HOFINET.MD §2, §4, §6 기준)
VALID_TIMESLOT = {0, 3, 6, 9, 12, 15, 18, 21}
VALID_FUND_TYPE = {0, 1, 3, 4}
VALID_MEDIA_TYPE = {1, 2, 3, 4, 5, 6, 7}
VALID_FRAUD_TYPE = {1, 2, 3, 4, 5, 7}
VALID_OUT_BANK = {102,103,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,
                  122,123,124,125,128,129,130,131,132,133,134,135,136,143,144,145,146,147,
                  148,149,150,151,152,153,154,155,156,157,158,159,160,161}
VALID_IN_BANK = {101,102,103,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,
                 120,121,122,123,124,125,126,127,128,129,130,131,132,133,134,135,136,142,
                 143,144,145,146,147,148,149,150,151,152,153,154,155,156,157,158,159,160}

# 자연어 → 매체구분 매핑 (HOFINET.MD §6.3)
MEDIA_NL_MAP = {
    'PC뱅킹': 1, 'PC 뱅킹': 1,
    '인터넷뱅킹': 2, '인터넷 뱅킹': 2,
    '전화': 3,
    '휴대전화': 4, '모바일': 4,
    '건별이체': 5,
    '대량이체': 7, '대량 이체': 7,
    # EN equivalents
    'PC banking': 1, 'PC Banking': 1,
    'internet banking': 2, 'Internet banking': 2, 'Internet Banking': 2,
    'phone banking': 3, 'Phone banking': 3, 'Phone Banking': 3,
    'mobile phone': 4, 'Mobile phone': 4, 'Mobile Phone': 4, 'mobile banking': 4,
    'per-transaction': 5, 'Per-transaction': 5, 'Per-Transaction': 5,
    'bulk transfer': 7, 'Bulk transfer': 7, 'Bulk Transfer': 7,
}
# 자연어 → 자금구분 매핑 (HOFINET.MD §6.2)
FUND_NL_MAP = {
    '일반': 0,
    '급여': 1,
    '타행자동이체': 4, '타행 자동이체': 4, '자동이체': 4,
}
# 일반 자금 키워드(이체/출금)는 코드 모호 — 검사 제외
INVALID_MEDIA_NL = {'창구', '영업점', '지점',
                    'counter', 'Counter', 'teller', 'Teller', 'branch window'}


def check_case(case_id, params, question, source):
    violations = []
    if params is None:
        return violations

    # 거래시간대
    if '거래시간대' in params:
        v = params['거래시간대']
        if v not in VALID_TIMESLOT:
            violations.append(('invalid_timeslot', f'거래시간대={v} not in {sorted(VALID_TIMESLOT)}'))

    # 출금금융회사일련번호
    if '출금금융회사일련번호' in params:
        v = params['출금금융회사일련번호']
        if v not in VALID_OUT_BANK:
            violations.append(('invalid_out_bank', f'출금사={v} not in 50-set'))

    # 입금금융회사일련번호
    if '입금금융회사일련번호' in params:
        v = params['입금금융회사일련번호']
        if v not in VALID_IN_BANK:
            violations.append(('invalid_in_bank', f'입금사={v} not in 54-set'))

    # 자금구분
    if '자금구분' in params:
        v = params['자금구분']
        if v not in VALID_FUND_TYPE:
            violations.append(('invalid_fund_type', f'자금구분={v} not in {sorted(VALID_FUND_TYPE)}'))

    # 매체구분
    if '매체구분' in params:
        v = params['매체구분']
        if v not in VALID_MEDIA_TYPE:
            violations.append(('invalid_media_type', f'매체구분={v} not in {sorted(VALID_MEDIA_TYPE)}'))

    # 거래금액
    if '거래금액' in params:
        v = params['거래금액']
        if isinstance(v, (int, float)) and not (1 <= v <= 500_000_000):
            violations.append(('invalid_amount', f'거래금액={v} out of [1, 500M]'))

    # 자연어 vs 매체구분 정합성
    if question:
        import re
        for nl in INVALID_MEDIA_NL:
            # word-boundary 매칭으로 'counter'가 'counterparty/counterpart' 부분이 되는 false positive 방지
            if re.search(rf'(?<![A-Za-z]){re.escape(nl)}(?![A-Za-z])', question):
                violations.append(('nl_invalid_media', f'자연어 "{nl}" not in HOFINET media types'))
        # NL 매체 명시되었는데 코드와 불일치
        if '매체구분' in params:
            for nl, code in MEDIA_NL_MAP.items():
                if nl in question and params['매체구분'] != code:
                    violations.append(('nl_media_mismatch', f'NL "{nl}" vs 매체구분={params["매체구분"]} (expected {code})'))

    return violations


def collect_singleturn(lang='kr'):
    """싱글턴 케이스 수집 + 검사. lang: 'kr' 또는 'en'."""
    base = 'benchmarks' if lang == 'kr' else 'benchmarks_en'
    out = []
    for f in sorted(glob.glob(f'{base}/cases_*.json')):
        d = json.load(open(f))
        for c in d:
            cid = c.get('id')
            q = c.get('question', '')
            expected = c.get('expected', {})
            param_checks = expected.get('param_checks', {})
            for tool, params in param_checks.items():
                v = check_case(cid, params, q, f)
                for vtype, vmsg in v:
                    out.append({
                        'source': f'{lang}/' + Path(f).name, 'case_id': cid, 'tool': tool,
                        'violation_type': vtype, 'detail': vmsg,
                        'question_excerpt': q[:120],
                    })
    return out


def collect_multiturn():
    """멀티턴 시나리오 수집 + 검사."""
    # generate_str.fraud_type enum: STR 양식 §VI-4 16종 + §VI-5 code 31 = 17종
    # (agent.py canonical enum)
    VALID_GENSTR_FRAUD = {
        '갑작스러운 거래패턴의 변화',     # §VI-4 code 15
        '원격지거래',                       # §VI-4 code 16
        '교환거래',                         # §VI-4 code 17
        '분할거래',                         # §VI-4 code 18
        '현금에 집착하는 거래',            # §VI-4 code 19
        '거액 입금 후 당일/익일 인출',     # §VI-4 code 20
        '무기명증서 관련거래',              # §VI-4 code 21
        '계좌개설 없이 거액 환전/송금',    # §VI-4 code 22
        '의심스러운 담보대출/보험약관대출', # §VI-4 code 23
        '주금 납입/잔액증명서 발급',       # §VI-4 code 24
        '다중거래의 동시요청',              # §VI-4 code 25
        '빈번한 입출금',                    # §VI-4 code 26
        '의심스러운 대여금고/보호예수',    # §VI-4 code 27
        '법인/타인자산 담보 거래',         # §VI-4 code 28
        '무관업종 보험청약',                # §VI-4 code 29
        '테러자금으로 의심',                # §VI-4 code 30
        '기타(자유기술)',                   # §VI-5 code 31
    }

    out = []
    for f in sorted(glob.glob('benchmarks_multiturn/cases_*.json')):
        d = json.load(open(f))
        for s in d:
            sid = s.get('id')
            for t in s.get('turns', []):
                q = t.get('content', '')
                for tc in t.get('tool_calls') or []:
                    name = tc.get('name')
                    args = tc.get('arguments') or {}
                    v = check_case(f"{sid}.t{t['turn']}", args, q, f)
                    for vtype, vmsg in v:
                        out.append({
                            'source': Path(f).name, 'scenario_id': sid,
                            'turn': t['turn'], 'tool': name,
                            'violation_type': vtype, 'detail': vmsg,
                            'question_excerpt': q[:120],
                        })
                    # generate_str.fraud_type 별도 검사
                    if name == 'generate_str':
                        ft = args.get('fraud_type')
                        if ft and ft not in VALID_GENSTR_FRAUD:
                            out.append({
                                'source': Path(f).name, 'scenario_id': sid,
                                'turn': t['turn'], 'tool': name,
                                'violation_type': 'genstr_fraud_type_invalid',
                                'detail': f'fraud_type="{ft}" not in HOFINET enum (use HOFINET pattern name, not crime category)',
                                'question_excerpt': q[:120],
                            })
                # tool_result에 들어있는 거래레코드 샘플도 점검
                tr = t.get('tool_result') or {}
                if isinstance(tr, dict):
                    for rec in tr.get('거래레코드_샘플') or []:
                        v = check_case(f"{sid}.t{t['turn']}.sample", rec, '', f)
                        for vtype, vmsg in v:
                            out.append({
                                'source': Path(f).name, 'scenario_id': sid,
                                'turn': t['turn'], 'tool': f'{name}.tool_result.sample',
                                'violation_type': vtype, 'detail': vmsg,
                                'question_excerpt': '',
                            })
    return out


def main():
    st_kr = collect_singleturn('kr')
    st_en = collect_singleturn('en')
    st = st_kr + st_en
    mt = collect_multiturn()

    # 집계
    summary = {
        'singleturn_violations': len(st),
        'multiturn_violations': len(mt),
        'by_type': defaultdict(int),
        'unique_cases': set(),
    }
    for v in st + mt:
        summary['by_type'][v['violation_type']] += 1
        if 'case_id' in v:
            summary['unique_cases'].add((v['source'], v['case_id']))
        else:
            summary['unique_cases'].add((v['source'], v['scenario_id']))

    summary['by_type'] = dict(summary['by_type'])
    summary['n_unique_cases'] = len(summary['unique_cases'])
    summary['unique_cases'] = sorted(summary['unique_cases'])

    out_dir = Path('_experiments/analysis')
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / 'hofinet_violations.json').open('w') as f:
        json.dump({
            'summary': {
                'singleturn_violations': summary['singleturn_violations'],
                'multiturn_violations': summary['multiturn_violations'],
                'by_type': summary['by_type'],
                'n_unique_cases': summary['n_unique_cases'],
            },
            'unique_cases_for_reexperiment': summary['unique_cases'],
            'singleturn_details': st,
            'multiturn_details': mt,
        }, f, ensure_ascii=False, indent=2)

    print(f'Singleturn violations: {summary["singleturn_violations"]}')
    print(f'Multiturn violations:  {summary["multiturn_violations"]}')
    print(f'By type: {summary["by_type"]}')
    print(f'Unique cases for re-exp: {summary["n_unique_cases"]}')
    for src, cid in summary['unique_cases'][:30]:
        print(f'  {src}: {cid}')
    print(f'\nSaved: {out_dir}/hofinet_violations.json')


if __name__ == '__main__':
    main()
