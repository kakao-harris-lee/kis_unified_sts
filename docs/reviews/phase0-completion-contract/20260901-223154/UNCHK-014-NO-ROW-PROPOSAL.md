# UNCHK-014 «출생-NO» 행 — 동결 제안 (U-16 ⓪ 리뷰 대상)

> **Document class**: 제안 기록. D0-A 내부 커밋 순서(계약 §13.6.5 «D0-A 내부
> 커밋 순서에 대한 구체적 귀결»)의 **⓪ 선행 리뷰가 심사할 대상**이다.
> 이 파일은 미래 커밋 ②(`tos-spec/src/verification/PHASE0-UNCHECKABLE-REGISTER.csv`
> 도입)에 실릴 `UNCHK-014` 행의 내용을 **동결**한다 — 승인(①) 후 이 값과 다르게
> 착지하면 `APPROVAL_CONTENT_DRIFT`(U-16-g g2)로 차단된다.
> 스키마의 유일 소스 = 계약 §13.1 · 시드 데이터의 유일 소스 = 계약 §13.2 ·
> digest 계약 = U-16-f
> (계약 = `docs/plans/2026-08-12-tos-phase0-completion-contract-design.md`).
> 이 디렉터리에 `verdict.md` 를 두지 않는다 — U-15-b (1) 선택자는 `verdict.md`
> 있는 스탬프만 보므로(41차 ⓒ) 레인 B 승인 currency 에 간섭하지 않는다.

## 동결 행 — §13.1 스키마 전열 (9열)

```text
id            = UNCHK-014
axis          = 문서가 선언하지 않은 축
reason        = U-2의 우주가 문서 자신이므로 원리적 검출 불가 (§13.5). §5.2.7 "열거는 자기 자신을 빠뜨린다"의 근본형
blocked_by    = 외부 기준 목록 도입 여부
owner_track   =                                  ← 공란 (§13.1: closable=NO 면 공란 · U-1a 면제)
exposed_in    = TOS-COMPLETION-STATUS
normative_ref =                                  ← 공란 (§13.2 시드 그대로)
closable      = NO
blocks_gate   =                                  ← 공란 (§13.2 시드 «—» = 없음)
```

## `row_canonical` 과 `row_content_digest` (U-16-f)

- 열이름을 `LC_ALL=C` 로 정렬:
  `axis, blocked_by, blocks_gate, closable, exposed_in, id, normative_ref, owner_track, reason`
- 각 쌍을 `<열이름>=<값>` UTF-8 바이트열로 만들고 **각 쌍 뒤에 NUL(0x00) 종결자**를
  붙여 이어붙인다 (아래 재량 ③). 총 328 바이트.
- 재현 (결정적):

```bash
python3 - <<'PY'
import hashlib
row = {
    'id': 'UNCHK-014',
    'axis': '문서가 선언하지 않은 축',
    'reason': 'U-2의 우주가 문서 자신이므로 원리적 검출 불가 (§13.5). §5.2.7 "열거는 자기 자신을 빠뜨린다"의 근본형',
    'blocked_by': '외부 기준 목록 도입 여부',
    'owner_track': '',
    'exposed_in': 'TOS-COMPLETION-STATUS',
    'normative_ref': '',
    'closable': 'NO',
    'blocks_gate': '',
}
canon = b''.join(('%s=%s' % (n, row[n])).encode('utf-8') + b'\0' for n in sorted(row))
print(hashlib.sha256(canon).hexdigest())
PY
```

```text
row_content_digest = f5b8616419142924783eca9fdf8630e0e4412f686cf4e80562dc669bea31f87f
```

## 저작 재량 3건 — 리뷰가 심사할 지점 (숨기지 않는다)

1. **`exposed_in` 값.** §13.1 스키마에 있는 열이나 **§13.2 시드 표에는 열 자체가
   부재**하고, 계약 어디에도 소비 규칙이 없다(전수 grep: 계약 내 `exposed_in`
   등장 1회 = 스키마 행뿐). 값을 `TOS-COMPLETION-STATUS` 로 둔다 — 레지스터
   항목이 노출되는 생성물은 그것뿐이다(§13.2 계수 지표들의 노출처와 동일).
2. **markdown → CSV 값 전사 규칙.** §13.2 표의 강조(`**…**`·코드스팬)는 표기이지
   값이 아니므로 제거한다. `owner_track` 칸의 «(U-1a 면제)» 는 주석이므로 값에서
   제외하고(§13.1 이 `closable=NO` 면 공란을 규정), «공란» 리터럴과 «—» 는 빈
   값으로 읽는다(다른 행들이 `G2` 같은 실값을 쓰는 것과 대조).
3. **NUL 의 독법 핀.** U-16-f 의 «쌍을 NUL 로 이어붙인» 은 구분자(separator)와
   종결자(terminator) 두 독법이 가능하다. **종결자로 핀**한다 — 같은 계약
   §12.3.1 의 `bound_set_digest` 레시피가 `printf '%s\0'`(종결자형)를 쓰는
   관행과 동형이며, 미래 검사기(K-*)는 이 핀을 계승해야 한다.

## 관측 (전사 출처)

- §13.2 시드 행 원문은 계약 본문에서 기계 추출했다(`| UNCHK-014 |` 로 시작하는
  유일 행) — 수기 전사 아님. 강조 제거는 정규식
  (`\*\*(.+?)\*\*` → `\1`, `` `(.+?)` `` → `\1`)로 수행했다.
- `reason` 값의 따옴표는 원문 그대로 **직선 큰따옴표**(`"`)다.
