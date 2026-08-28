#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pagelimb-v222e5.py — «열거 완전성» limb 술어  [gen-2 = v2.22 에라타 5차 ⓧ]

계약 근거(`fd13ca26` docs/plans/2026-08-12-tos-phase0-completion-contract-design.md):
  :5453       (1) `gh api --paginate` 필수 + 질의에 `per_page=100`(계약 리터럴)
  :5454-5457  (2)① `total_count` 대조 «불변»(check-runs 등) · ② «주지 않는» 엔드포인트 — (4) 의 6개 중
              **셋**(`commits/{d}/pulls` · `rulesets` · `rules/branches/{target}`; 실측) — 는 «종단 빈 페이지»로
  :5457-5462  (ㄱ) `--slurp` 를 `--paginate` 와 함께 써 본문이 «페이지 배열의 배열»이 되게 하고 **페이지 수 `N`
              과 페이지별 원소 수를 «본문에서»** 관측한다 · 수집 원소 = 그 배열들의 concat(평탄화는 본문 연산
              이며 재조회가 아니다) · (ㄴ) 이어서 `?page=<N+1>&per_page=100` 한 번을 «명시»로 조회해
              그 본문이 «정확히 `[]`»
  :5488-5490  전이성 — 종단 프로브가 «비-빈» 이면 전이적 차단(limb ① 과 같은 성질 · 전순서 1)
  :5503-5506  (5) transcript 병기 필수 — 페이지 수 `N` · 페이지별 원소 수 · 종단 프로브 본문

  **①②의 정의역은 배타적이다** — «주는» 엔드포인트 / «주지 않는» 엔드포인트.  그래서 이 술어는
  `total_count` 의 유무로 limb ② 의 적용 여부를 «먼저» 가른다(guard).  이 스코핑을 빼고 limb ② 를
  전 엔드포인트에 걸면 check-runs 처럼 «객체를 반환하는» 목록 응답이 전부 red 가 된다
  (실측 GET: check-runs 의 없는 페이지 = `{"total_count":8,"check_runs":[]}` ≠ `[]`).

  이 판의 limb ② 피연산자는 **«본문»** 이다 — 5차 ⓧ 의 처분은 «본문 관측면으로 옮긴다» 하나이고,
  2차 ⓞ 의 «구조 파생 > 미관측 자기신고»와 같은 이동이다.  그래서 `mode`(strict/loose) 는
  **이 판에서 무동작**이다 — 두 독법이 갈리던 자리 자체가 사라진다(피연산자가 관측 가능해졌으므로).

사용:
  pagelimb-v222e4.py <strict|loose> <merged.json> <hdr|NONE> <slurp.json|NONE> <terminal.json|NONE>
                     <elem-key|NONE> <collected-out|NONE>
    argv 규격은 gen-1·gen-2 «공통»이다 — 두 판이 «같은 실행기»에서 호출되기 위한 조건이고,
    각 판은 자기 관측면에 해당하는 인자만 소비한다(미소비 인자를 transcript 에 명기한다).
방출:
  PL-*  관측 라인 · RESULT=PAGES_OK|<detail> 또는 RESULT=PREVENTION_UNVERIFIABLE|<사유>  (rc 0 = PAGES_OK)
"""
import json
import re
import sys

UV = "PREVENTION_UNVERIFIABLE"
OK = "PAGES_OK"
MODES = ("strict", "loose")


def obs(s):
    print(s)


def die(state, why):
    print("RESULT=%s|%s" % (state, why))
    sys.exit(0 if state == OK else 1)


def elems_of(doc, key):
    """한 «응답 본문»에서 (원소 리스트, total_count) 를 뽑는다 — bare array 와 객체 둘 다 받는다."""
    if isinstance(doc, list):
        return doc, None
    if isinstance(doc, dict):
        e = doc.get(key) if key else None
        return (e if isinstance(e, list) else []), doc.get("total_count")
    return [], None


def main():
    if len(sys.argv) != 8:
        die(UV, "argv %d개 (요구 7) — 술어 호출 규격 위반" % (len(sys.argv) - 1))
    mode, merged_p, hdr_p, slurp_p, term_p, key, out_p = sys.argv[1:8]
    if key == "NONE":
        key = None
    if mode not in MODES:
        die(UV, "mode=%r ∉ {strict, loose}" % mode)

    # ── READER (gen-2) — 관측면 = «--paginate --slurp 본문»(페이지 배열의 배열)
    try:
        pages = json.load(open(slurp_p, encoding="utf-8"))
    except Exception as e:
        die(UV, "--slurp 본문 파싱 실패 %r" % (e,))
    if not isinstance(pages, list):
        die(UV, "--slurp 본문이 «페이지 배열의 배열»이 아니다: %s" % type(pages).__name__)
    per, collected, tots = [], [], []
    for pg in pages:
        _e, _t = elems_of(pg, key)
        per.append(len(_e))
        collected = collected + _e
        tots.append(_t)
    N = len(pages)
    total = tots[0] if tots else None
    obs("PL-R [gen-2 READER] 관측면 = «--paginate --slurp 본문» · 페이지 수 N=%d · 페이지별 원소 수 %s · "
        "수집 원소 = concat = %d개 · total_count=%s" % (N, per, len(collected), total))
    if len(set(repr(t) for t in tots)) > 1:
        obs("PL-R **주의** 페이지별 total_count 가 서로 다르다 %s — 걷는 동안 컬렉션이 변했다" % tots)
    obs("PL-R 미소비 인자(gen-2): merged=%s · hdr=%s · mode=%s(무동작) — 이 판의 limb ② 피연산자는 «본문»이다"
        % (merged_p, hdr_p, mode))

    # ── limb ① — 수집 원소 수 == total_count  (계약 (2)①)
    if total is None:                                                                  # [LIMB1]
        limb1 = "N/A"                                                                  # [LIMB1]
        obs("PL-1 limb ① N/A — 이 엔드포인트는 `total_count` 를 주지 않는다")           # [LIMB1]
    else:                                                                              # [LIMB1]
        limb1 = "PASS" if len(collected) == int(total) else "FAIL"                     # [LIMB1]
        obs("PL-1 limb ① 수집 원소 %d == total_count %s ?  → %s"                        # [LIMB1]
            % (len(collected), total, limb1))                                          # [LIMB1]
        if limb1 == "FAIL":                                                            # [LIMB1]
            die(UV, "limb ① 개수 불일치 — 수집 %d ≠ total_count %s "                    # [LIMB1]
                    "(전이적 차단 · 재조회로 해소 · 8 로 접지 않는다)"                  # [LIMB1]
                % (len(collected), total))                                             # [LIMB1]

    # ── limb ② — 정의역 guard: `total_count` 를 «주지 않는» 엔드포인트만  (계약 (2) 의 배타적 정의역)
    if total is not None:                                                              # [LIMB2G]
        limb2 = "N/A"                                                                  # [LIMB2G]
        obs("PL-2 limb ② N/A — 이 엔드포인트는 `total_count` 를 «주므로» 열거 완전성은 limb ① 소관이다 "   # [LIMB2G]
            "(계약 (2) 의 ①②는 배타적 정의역: ① «주는» 엔드포인트 · ② «주지 않는» 엔드포인트)")           # [LIMB2G]
    else:                                                                              # [LIMB2G]
        if term_p == "NONE":
            die(UV, "종단 프로브 본문 미제공 — limb ② 를 «본문»에서 관측할 수 없다 → «열거 불완전»")
        try:
            tj = json.loads(open(term_p, encoding="utf-8").read())
        except Exception as e:
            die(UV, "종단 프로브 본문 파싱 실패 %r — limb ② 관측 불가" % (e,))
        obs("PL-2 limb ② [gen-2] 피연산자 = «본문» · 종단 프로브 ?page=<N+1> (N=%d → page=%d) · 본문 = %s"
            % (N, N + 1, json.dumps(tj, ensure_ascii=False)[:240]))
        if not (isinstance(tj, list) and len(tj) == 0):
            die(UV, "종단 프로브 본문이 «정확히 []» 가 아니다(%s) — 열거 불완전 "
                    "(전이적 차단 · 걷는 동안 원소가 늘어난 경우 포함 · 재조회로 해소 · 8 로 접지 않는다)"
                % ("원소 %d개" % len(tj) if isinstance(tj, list) else "비-배열 %s" % type(tj).__name__))
        limb2 = "PASS"
        obs("PL-2 종단 프로브 «정확히 []» 확인 → limb ② PASS — **본문만으로 재판정 가능**하고 헤더에 "
            "무의존이다(헤더는 보조이고 판정 피연산자가 아니다·(5))")
        obs("PL-2m mode=%s 는 이 판에서 «무동작» — 피연산자가 관측 가능해져 두 독법이 갈리던 자리가 사라졌다"
            % mode)
        obs("PL-2r 미결(정직 등재) — ① `?page=<N+1>` 이 «없는 페이지»에 `[]` 를 준다는 것은 «실측»이고 문서 "
            "규정은 확인되지 않았다 · ② 페이지 «사이»의 삽입·삭제로 원소가 경계를 넘는 것은 limb ① 이 잡고 "
            "이 limb 은 잡지 못한다(문서 침묵으로부터의 추론 · 잔여)")

    if limb1 == "N/A" and limb2 == "UNOBSERVED":
        obs("PL-2v **공허 green 경고** — limb ① N/A ∧ limb ② 미관측인데 통과한다: 이 조회의 «전수성»에 대한 "
            "증거가 0 이다.  (2) 마지막 문장은 이 조합을 «열거 불완전»으로 읽으라 하지만 loose 독법은 "
            "limb ② 를 «확인됨»으로 세므로 그 문장이 발화하지 않는다")

    if out_p != "NONE":
        json.dump(collected, open(out_p, "w", encoding="utf-8"))
        obs("PL-C 수집(평탄화) 원소 %d개 → %s  (하류 술어는 이 결과를 소비한다)" % (len(collected), out_p))
    die(OK, "limb ①=%s · limb ②=%s(mode=%s) · 수집 %d · total_count=%s"
        % (limb1, limb2, mode, len(collected), total))


if __name__ == "__main__":
    main()
