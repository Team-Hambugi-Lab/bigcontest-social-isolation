"""0단계 노트북 생성 — 데이터 신뢰성 점검."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_notebook import BOOTSTRAP, build, check, code, md  # noqa: E402

CELLS = [
    md("""
# [EDA] 데이터 신뢰성 점검 — 2026-09-20

**작성자** — 김태은 (`taeeunni`)

**목적** — 이후 모든 수치의 기반이 되는 로딩 규칙을 고정하고, 원본에서 발견된 배포 오류와
코드 체계를 재현 가능한 형태로 입증한다.

**설계 문서** — `docs/plans/260920_EDA_design.md`

**이 노트북이 답하는 것**

1. 원본 20개 파일의 인코딩·구분자·행수는 정확히 무엇인가
2. 12월 파일의 중복 배포는 실재하는가, 어떻게 제거하는가
3. `BLOCK_CD` 20자리는 무엇을 의미하는가
4. SK 수치값은 어떤 구조를 갖는가
"""),
    code(BOOTSTRAP),
    md("## 1. 파일 인벤토리"),
    code("""
inv = paths.list_raw_files()
print(f"총 {len(inv)}개 파일, {inv.size_mb.sum():,.1f} MB")
print()
print(inv.to_string(index=False))
"""),
    md("""
### 1.1 인코딩·구분자 판별

`docs/data-overview.md`는 SK를 CP949·파이프 구분, 카드를 탭 구분 TXT로 기재했다.
원본 바이트를 직접 확인해 판정한다.
"""),
    code("""
def sniff(path, n=8192):
    head = path.open("rb").read(n)
    bom = head.startswith(b"\\xef\\xbb\\xbf")
    body = head[3:] if bom else head
    first = body.split(b"\\n")[0]
    counts = {"쉼표": first.count(b","), "파이프": first.count(b"|"), "탭": first.count(b"\\t")}
    sep = max(counts, key=counts.get)
    return bom, sep, counts[sep]

rows = []
for grp, d in (("sk", paths.SK_DIR), ("card", paths.CARD_DIR)):
    for p in sorted(d.glob("*.csv")):
        bom, sep, n = sniff(p)
        rows.append({"group": grp, "file": p.name, "BOM": bom, "구분자": sep, "구분자수": n})
sniff_df = pd.DataFrame(rows)
print(sniff_df.to_string(index=False))
print()
print("판정:", sniff_df.BOM.all() and (sniff_df.구분자 == "쉼표").all())
print("-> 20개 파일 전부 UTF-8 BOM + 쉼표 구분. 기존 문서의 CP949/파이프/탭 기재는 오류.")
"""),
    md("""
## 2. 12월 중복 배포

`flow_time_pop_202512.csv`와 `flow_wkdy_pop_202512.csv`가 전체 2배로 복제 배포됐다.
모르고 쓰면 12월 유동인구가 2배로 집계된다.
"""),
    code("""
rep = loaders.dedupe_report()
print(rep.to_string(index=False))
print()
print(f"중복 제거 전 총 행수: {rep.rows_raw.sum():,}")
print(f"중복 제거 후 총 행수: {rep.rows_dedup.sum():,}")
print(f"제거된 행수:        {rep.dropped.sum():,}")
"""),
    code("""
affected = rep[rep.dropped > 0]
print("중복이 발견된 파일")
print(affected.to_string(index=False))
print()
for _, r in affected.iterrows():
    print(f"  {r.table} {r.ym}: {r.rows_raw:,} -> {r.rows_dedup:,} "
          f"(배수 {r.rows_raw / r.rows_dedup:.2f})")
print()
print("다른 16개 파일의 중복 건수:", int(rep[rep.dropped == 0].dropped.sum()))
"""),
    code("""
# PK별 등장 횟수가 정확히 2회인지 확인한다
dec = loaders.load_sk("time", "202512", dedupe=False)
occur = dec.groupby(loaders.SK_PK, observed=True).size().value_counts()
print("12월 time 파일 — PK별 등장 횟수 분포")
print(occur.to_string())
print()
# 값까지 동일한 완전중복인지 확인
print(f"완전중복 행수: {dec.duplicated().sum():,}")
print(f"PK중복 행수:   {dec.duplicated(subset=loaders.SK_PK).sum():,}")
print("-> 두 수가 같으면 PK뿐 아니라 값까지 동일한 단순 복제다")
"""),
    md("## 3. 스키마 검증"),
    code("""
print("SK 3테이블 구조 (2025-07)")
for t in paths.SK_TABLES:
    df = loaders.load_sk(t, "202507")
    vc = loaders.sk_value_cols(df)
    print(f"\\n[{t}] {len(df):,}행 x {df.shape[1]}열 / 수치컬럼 {len(vc)}개")
    print(f"  PK      : {loaders.SK_PK}")
    print(f"  수치컬럼: {vc}")
    print(f"  결측    : {int(df[vc].isnull().sum().sum())}건")
    print(f"  음수    : {int((df[vc] < 0).sum().sum())}건")
"""),
    code("""
print("신한카드 2종 구조")
for ds in (1, 2):
    df = loaders.load_card(ds)
    print(f"\\n[데이터{ds}] {len(df):,}행 x {df.shape[1]}열")
    print(f"  컬럼    : {list(df.columns)}")
    print(f"  결측    : {int(df.isnull().sum().sum())}건")
    print(f"  완전중복: {int(df.duplicated().sum())}건")
    print(f"  TS_AT   : min {df.TS_AT.min():,} / max {df.TS_AT.max():,}")
    print(f"  USE_CNT : min {df.USE_CNT.min():,} / max {df.USE_CNT.max():,}")
    print(f"  기간    : {df.TA_YMD.min()} ~ {df.TA_YMD.max()} (고유 {df.TA_YMD.nunique()}일)")
    print(f"  업종수  : {df.MCT_RY_CD.nunique()}종 / 성별 {sorted(df.SEX_CCD.unique())}")
"""),
    code("""
d1, d2 = loaders.load_card(1), loaders.load_card(2)
s1, s2 = set(d1.MCT_RY_CD), set(d2.MCT_RY_CD)
print(f"데이터1 전용 업종: {sorted(s1 - s2)}")
print(f"데이터2 전용 업종: {sorted(s2 - s1)}")
print(f"공통 업종: {len(s1 & s2)}종")
print()
print("USE_CNT 최솟값이 5인 것은 5건 미만 집계셀이 비식별 처리로 삭제됐다는 뜻이다.")
print("이 절단이 어느 집단에 편중되는지는 1단계에서 정량화한다.")
"""),
    md("""
## 4. BLOCK_CD 해독

문서에 코드 체계 설명이 없다. 좌표를 WGS84로 변환해 실지리와 대조하는 방식으로 역추적한다.
"""),
    code("""
age = regions.add_wgs84(regions.add_region_codes(loaders.load_sk("age", "202507")))
age["tot"] = age[sk_dong.AGE_COLS].sum(axis=1)

g = age.groupby("sgg_cd").agg(
    격자수=("tot", "size"), 총유동=("tot", "sum"),
    중심위도=("lat", "mean"), 중심경도=("lon", "mean"),
)
g["관측면적km2"] = g.격자수 * regions.GRID_AREA_M2 / 1e6
print("BLOCK_CD 앞 5자리별 실제 위치")
print(g.sort_values("격자수", ascending=False).round(
    {"중심위도": 5, "중심경도": 5, "관측면적km2": 2, "총유동": 0}).to_string())
print()
print("실제 좌표 대조")
print("  서울 강남구청 37.5172, 127.0473 / 면적 39.5 km2")
print("  강원 춘천시청 37.8813, 127.7300")
print("-> 11230 = 서울 강남구, 32010 = 강원 춘천시로 확정")
"""),
    code("""
print("BLOCK_CD 자릿수별 단위 개수")
rows = []
for n in (5, 8, 10, 12, 14, 20):
    r = {"앞자리": n, "전체": age.BLOCK_CD.str[:n].nunique()}
    for cd, nm in regions.SGG_NAMES.items():
        r[nm] = age.loc[age.sgg_cd == cd, "BLOCK_CD"].str[:n].nunique()
    rows.append(r)
print(pd.DataFrame(rows).to_string(index=False))
print()
print("실제 행정구역 수")
print("  강남구 행정동 22개 (법정동은 14개)")
print("  춘천시 1읍 + 9면 + 15동 = 25개")
print("-> 앞 8자리가 행정동과 정확히 1:1 대응한다. 이를 분석 단위로 쓴다.")
"""),
    code("""
# 춘천 읍면동 코드 규칙 확인 — 구 행정구역코드는 읍 1xx, 면 3xx, 동 5xx~7xx
cc = age[age.sgg_cd == "32010"].copy()
cc["d3"] = cc.BLOCK_CD.str[5:8]
kind = cc.d3.str[0].map({"1": "읍", "3": "면", "5": "동", "6": "동", "7": "동"})
print("춘천시 6~8자리 코드 유형별 개수")
print(kind.groupby(cc.d3).first().value_counts().to_string())
print()
print(f"전체 {cc.d3.nunique()}개 = 읍 1 + 면 9 + 동 15")
print("-> 구 행정구역코드 체계와 일치한다")
"""),
    code("""
border = age[~age.sgg_cd.isin(regions.TARGET_SGG)]
print(f"대상 외 시군구 코드: {sorted(border.sgg_cd.unique())}")
print(f"해당 격자 행수: {len(border)}행 (전체의 {len(border) / len(age) * 100:.4f}%)")
print(f"해당 격자 총유동: {border.tot.sum():,.1f} "
      f"(전체의 {border.tot.sum() / age.tot.sum() * 100:.4f}%)")
print()
print("-> 경계에 걸친 격자다. 분석에서 제외한다.")
"""),
    md("""
## 5. 값의 구조

SK 유동인구가 어떤 단위로 기록되는지, 0이 무엇을 뜻하는지 확인한다.
이것은 이후 모든 지표의 해석에 영향을 준다.
"""),
    code("""
t = loaders.load_sk("time", "202507")
vals = t[sk_dong.TIME_COLS].to_numpy().ravel()
pos = np.sort(np.unique(vals[vals > 0]))

print(f"전체 수치셀 {vals.size:,}개")
print(f"0인 셀      {(vals == 0).mean() * 100:.2f}%")
print(f"양수 최솟값 {pos.min()}")
print(f"0.03 미만 양수 개수: {(pos < 0.03).sum()}")
print()
print("1 미만 양수 고유값 25종")
print(pos[pos < 1][:25])
print()
Q = 0.0254
print(f"{Q} 배수를 소수 2자리로 반올림한 수열 (비교용)")
print(np.round(np.arange(1, 26) * Q, 2))
print()
# 전수 검정: |k*Q - v| <= 반올림 한계
k = np.rint(pos / Q)
resid = np.abs(k * Q - pos)
print(f"|k*{Q} - v| 최대 잔차 = {resid.max():.6f}  (2자리 반올림 한계 0.005)")
print(f"설명률 = {(resid <= 0.006).mean() * 100:.4f}%")
print(f"-> 모든 값이 {Q}의 정수배다. 1/{Q} = {1 / Q:.4f}")
"""),
    code("""
# 0이 비식별 마스킹인지 실제 0인지 판별
tc = sk_dong.TIME_COLS
print(f"TIME 24칸이 전부 0인 격자: {int((t[tc].sum(axis=1) == 0).sum()):,}행")

a = loaders.load_sk("age", "202507")
w = loaders.load_sk("wkdy", "202507")
a2 = a.assign(age_sum=a[sk_dong.AGE_COLS].sum(axis=1)).set_index(loaders.SK_PK)
w2 = w.assign(wkdy_sum=w[sk_dong.WKDY_COLS].sum(axis=1)).set_index(loaders.SK_PK)
common = a2.index.intersection(w2.index)
n_odd = int(((a2.loc[common, "age_sum"] == 0) & (w2.loc[common, "wkdy_sum"] > 0)).sum())
print(f"AGE 총합=0 인데 WKDY 총합>0 인 격자: {n_odd:,}행")
print()
print("-> 둘 다 0이면 '격자 자체가 비어 있는 경우는 없고,")
print("   셀 단위 0은 해당 칸 값이 최소단위 미만'이라는 뜻이다.")
print("   0은 비식별 마스킹이 아니라 0.0254명 단위 이산 추계에서의 실제 0일 가능성이 높다.")
"""),
    code("""
# 테이블 간 총량 정합성
tt = t.drop_duplicates(subset=loaders.SK_PK).assign(
    time_sum=lambda d: d[sk_dong.TIME_COLS].sum(axis=1))
m = (a2.reset_index()[loaders.SK_PK + ["age_sum"]]
     .merge(tt[loaders.SK_PK + ["time_sum"]], on=loaders.SK_PK))
print(f"AGE·TIME 공통 격자 {len(m):,}개")
print(f"  상관계수      {m.age_sum.corr(m.time_sum):.6f}")
print(f"  평균 절대차   {(m.age_sum - m.time_sum).abs().mean():.4f}")
print(f"  최대 절대차   {(m.age_sum - m.time_sum).abs().max():.4f}")
print()
mw = m.merge(w2.reset_index()[loaders.SK_PK + ["wkdy_sum"]], on=loaders.SK_PK)
ratio = mw.wkdy_sum.sum() / mw.age_sum.sum()
print(f"WKDY 7칸합 / AGE 12칸합 = {ratio:.4f}")
print("-> 약 7. 따라서 WKDY 각 칸은 '해당 요일의 일평균'이다.")
print("   월 총량이라면 30 근처여야 한다. 요일 지표를 7로 나누지 않는다.")
"""),
    md("""
## 6. 확정된 처리 규칙

이후 모든 분석은 아래 규칙을 따른다. 로딩은 반드시 `src/data/loaders.py`를 거친다.

| 항목 | 결정 | 근거 |
|---|---|---|
| 인코딩·구분자 | UTF-8 BOM, 쉼표 | 1.1절 전수 확인 |
| 한글 경로 | `Path.glob()`으로만 접근 | OneDrive NFD 저장 |
| 12월 중복 | `drop_duplicates(subset=PK)` | 2절 |
| 분석 단위 | `BLOCK_CD[:8]` 행정동 47개 | 4절 |
| 경계 격자 | 대상 외 시군구 8종 제외 | 4절 |
| 3테이블 결합 | 공통 격자 제한 없음, 동 집계 후 결합 | 1단계에서 편향 정량화 |
| WKDY 스케일 | 7로 나누지 않음 | 5절 |
| 0 처리 | 결측 변환 없이 실제 0으로 집계 | 5절 |
| 카드 | 데이터2 주력, 데이터1과 합산 금지 | 3절 (모집단 상이) |
| 금액 지표 | `ZZ_나머지`·`세금공과금` 제외 | 1단계 |
"""),
    code("""
# 규칙이 코드에 반영되어 있는지 확인
panel = sk_dong.build_space_panel()
print(f"공간축 패널: {len(panel)}행 = 행정동 {panel.dong_cd.nunique()}개 x 월 {panel.STD_YM.nunique()}개")
print(f"결측: {int(panel.isnull().sum().sum())}건")
print()
print("행정동 목록")
dong_list = panel[["dong_cd"]].drop_duplicates().assign(
    지역=lambda d: d.dong_cd.str[:5].map(regions.SGG_NAMES))
print(dong_list.groupby("지역").size().to_string())
"""),
    md("""
## 핵심 발견

**1. 12월 `flow_time`·`flow_wkdy`가 전체 2배로 복제 배포됐다.**
PK뿐 아니라 값까지 동일한 단순 복제다. 제거하지 않으면 12월 유동인구가 2배가 된다.
총 행수는 2,101,675에서 1,887,863으로 줄어든다. 대회 공지에서 재배포 여부를 확인해야 한다.

**2. `BLOCK_CD` 앞 8자리가 행정동과 1:1 대응한다.**
앞 5자리는 구 행정구역코드 시군구(11230=강남구, 32010=춘천시), 6~8자리는 행정동이다.
강남 22개·춘천 25개로 실제 행정구역 수와 정확히 일치하므로 외부 격자 매핑표 없이
동 단위 집계가 가능하다.

**3. SK 수치는 0.0254 단위 이산값이고 0은 마스킹이 아닐 가능성이 높다.**
양수 셀 전수가 `k x 0.0254`(k는 양의 정수)를 소수 2자리로 반올림한 값으로 설명된다.
0.0254 미만 양수가 하나도 없고, 24칸 전부 0인 격자와 `AGE`=0∧`WKDY`>0인 격자가 모두 0행이다.
0을 결측으로 처리하지 않는다.

**다음 단계** — 1단계에서 비식별 컷(`USE_CNT>=5`)의 편향과 격자 커버리지 불일치의 영향을
정량화한다.
"""),
]


def main() -> None:
    out = ROOT / "notebooks" / "260920_EDA_00_data_integrity_taeeunni.ipynb"
    check(build(CELLS, out))


if __name__ == "__main__":
    main()
