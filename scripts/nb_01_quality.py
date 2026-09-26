"""1단계 노트북 생성 — 구조·품질 EDA."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_notebook import BOOTSTRAP, build, check, code, md  # noqa: E402

CELLS = [
    md("""
# [EDA] 구조·품질 분석 — 2026-09-20

**선행** — `260920_EDA_00_data_integrity.ipynb`에서 로딩 규칙을 확정했다.

**이 노트북이 답하는 것**

1. SK의 0은 실제 0인가 비식별 마스킹인가
2. 테이블 간 격자 커버리지 불일치는 분석에 얼마나 영향을 주는가
3. 카드의 비식별 컷(`USE_CNT>=5`)은 어느 집단을 지우는가 — **발표 핵심 논거**
4. 6개월 시계열에 수집 변동이나 이상치가 있는가
"""),
    code(BOOTSTRAP),
    code("""
PK = loaders.SK_PK
age = loaders.load_sk("age", "202507")
time_ = loaders.load_sk("time", "202507")
wkdy = loaders.load_sk("wkdy", "202507")
print(f"2025-07 기준 격자 수 — AGE {len(age):,} / TIME {len(time_):,} / WKDY {len(wkdy):,}")
"""),
    md("""
## 1. 0값의 정체

플랜은 "0이 실제 0인지 비식별 하한 마스킹인지 문서에 없다"고 남겼다.
값의 이산 구조와 테이블 간 정합성으로 판별한다.
"""),
    code("""
vals = time_[sk_dong.TIME_COLS].to_numpy().ravel()
pos = np.sort(np.unique(vals[vals > 0]))
gaps = np.diff(pos[:60])

print(f"양수 고유값 하위 20종")
print(pos[:20])
print()
print(f"인접 간격 최빈값: {pd.Series(gaps.round(4)).mode().tolist()}")
print(f"양수 최솟값: {pos.min()}   0.0254 미만 양수: {(pos < 0.0254).sum()}개")
print()
q = 0.0254
expected = np.round(np.arange(1, 21) * q, 2)
print("0.0254 배수를 2자리 반올림한 수열")
print(expected)
print(f"관측값과 일치: {np.array_equal(pos[:20], expected)}")
"""),
    code("""
# 증거 1 — 모든 칸이 0인 격자가 존재하는가
tc, ac, wc = sk_dong.TIME_COLS, sk_dong.AGE_COLS, sk_dong.WKDY_COLS
ev = {
    "TIME 24칸 전부 0인 격자": int((time_[tc].sum(axis=1) == 0).sum()),
    "AGE 12칸 전부 0인 격자": int((age[ac].sum(axis=1) == 0).sum()),
    "WKDY 7칸 전부 0인 격자": int((wkdy[wc].sum(axis=1) == 0).sum()),
}
a2 = age.assign(age_sum=age[ac].sum(axis=1)).set_index(PK)
w2 = wkdy.assign(wkdy_sum=wkdy[wc].sum(axis=1)).set_index(PK)
cm = a2.index.intersection(w2.index)
ev["AGE합=0 이면서 WKDY합>0"] = int(
    ((a2.loc[cm, "age_sum"] == 0) & (w2.loc[cm, "wkdy_sum"] > 0)).sum()
)
for k, v in ev.items():
    print(f"  {k}: {v:,}행")
print()
print("-> 전부 0이므로 '격자는 있는데 값이 통째로 지워진' 경우가 없다")
"""),
    code("""
# 증거 2 — 0칸이 많은 격자에서 총량이 새는가 (마스킹이면 새야 한다)
tt = time_.drop_duplicates(subset=PK)
tt = tt.assign(time_sum=tt[tc].sum(axis=1), n_zero=(tt[tc] == 0).sum(axis=1))
m = a2.reset_index()[PK + ["age_sum"]].merge(tt[PK + ["time_sum", "n_zero"]], on=PK)
m["gap"] = m.age_sum - m.time_sum

bins = pd.cut(m.n_zero, [-1, 0, 3, 6, 12, 18, 24])
tab = m.groupby(bins, observed=True).agg(
    격자수=("gap", "size"), 평균격차=("gap", "mean"),
    평균AGE합=("age_sum", "mean"), 최대절대격차=("gap", lambda s: s.abs().max()),
).round(4)
print("시간대 0칸 개수별 AGE합 - TIME합")
print(tab.to_string())
print()
print("24칸 각각 소수 2자리 반올림 시 누적 오차 한계 = 24 x 0.005 = 0.12")
print("-> 관측 격차가 이 범위 안이면 마스킹이 아니라 반올림 오차다")
"""),
    code("""
fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
ax = axes[0]
ax.bar(range(len(pos[:20])), pos[:20], color=PALETTE[0])
ax.set_title("SK 양수값 하위 20종 — 0.0254 등간격 이산 구조")
ax.set_xlabel("순위")
ax.set_ylabel("유동인구 (명)")

ax = axes[1]
zero_share = [(time_[c] == 0).mean() * 100 for c in tc]
ax.plot(range(24), zero_share, marker="o", color=PALETTE[1], label="0인 격자 비율")
ax.set_title("시간대별 0값 비율 (2025-07)")
ax.set_xlabel("시각 (시)")
ax.set_ylabel("0인 격자 비율 (%)")
ax.set_xticks(range(0, 24, 3))
ax.legend()
plt.tight_layout()
plt.show()
print("심야에 0이 많은 것은 실제로 사람이 없기 때문으로 해석된다")
"""),
    md("""
## 2. 격자 커버리지 불일치

3테이블의 격자 수가 다르다. 단순 조인하면 행이 사라진다.
그 행들이 무엇인지, 동 단위 집계 후에도 문제가 남는지 확인한다.
"""),
    code("""
key = ["BLOCK_CD", "X_COORD", "Y_COORD"]
ka = set(map(tuple, age[key].values))
kt = set(map(tuple, time_.drop_duplicates(subset=PK)[key].values))
kw = set(map(tuple, wkdy[key].values))
common = ka & kt & kw

rows = []
for nm, ks, df, cols in (
    ("AGE", ka, age, ac), ("TIME", kt, time_.drop_duplicates(subset=PK), tc),
    ("WKDY", kw, wkdy, wc),
):
    d = df.copy()
    d["tot"] = d[cols].sum(axis=1)
    d["is_common"] = [tuple(x) in common for x in d[key].values]
    lost = d[~d.is_common]
    rows.append({
        "테이블": nm, "격자수": len(ks), "소실격자": len(lost),
        "소실격자비율%": round(len(lost) / len(ks) * 100, 2),
        "소실유동량비중%": round(lost.tot.sum() / d.tot.sum() * 100, 4),
        "소실격자_총유동_중앙값": round(lost.tot.median(), 3),
        "유지격자_총유동_중앙값": round(d[d.is_common].tot.median(), 3),
    })
cover = pd.DataFrame(rows)
print(f"3테이블 공통 격자: {len(common):,}")
print()
print(cover.to_string(index=False))
print()
print("-> 행 기준 최대 21% 소실이지만 유동인구 총량 기준으로는 0.02% 수준이다")
"""),
    code("""
w3 = wkdy.copy()
w3["tot"] = w3[wc].sum(axis=1)
w3["is_common"] = [tuple(x) in common for x in w3[key].values]
w3["일평균"] = w3.tot / 7

fig, ax = plt.subplots(figsize=(10, 5))
bins = np.logspace(-2, 4, 60)
ax.hist(w3.loc[w3.is_common, "일평균"].clip(lower=0.01), bins=bins,
        alpha=0.7, label=f"공통 격자 (n={int(w3.is_common.sum()):,})", color=PALETTE[0])
ax.hist(w3.loc[~w3.is_common, "일평균"].clip(lower=0.01), bins=bins,
        alpha=0.7, label=f"소실 격자 (n={int((~w3.is_common).sum()):,})", color=PALETTE[5])
ax.set_xscale("log")
ax.set_yscale("log")
ax.set_title("WKDY 소실 격자 vs 유지 격자의 유동인구 분포 (2025-07)")
ax.set_xlabel("격자 일평균 유동인구 (명, 로그)")
ax.set_ylabel("격자 수 (로그)")
ax.legend()
plt.tight_layout()
plt.show()

print(f"소실 격자 일평균 — 중앙값 {w3.loc[~w3.is_common, '일평균'].median():.3f}, "
      f"최댓값 {w3.loc[~w3.is_common, '일평균'].max():.3f}")
print(f"유지 격자 일평균 — 중앙값 {w3.loc[w3.is_common, '일평균'].median():.3f}, "
      f"최댓값 {w3.loc[w3.is_common, '일평균'].max():,.1f}")
"""),
    code("""
# 소실이 랜덤인가 — 지역·동별 분포
w3 = regions.add_region_codes(w3)
by_sgg = pd.crosstab(w3.sgg_cd, w3.is_common, normalize="index").mul(100).round(2)
by_sgg.columns = ["소실%", "유지%"]
print("시군구별 소실률")
print(by_sgg.to_string())
print()
dl = w3[w3.sgg_cd.isin(regions.TARGET_SGG)].groupby("dong_cd").agg(
    격자수=("tot", "size"),
    소실률=("is_common", lambda s: round((~s).mean() * 100, 2)),
    소실유동비중=("tot", "sum"),
)
lost_tot = w3[~w3.is_common].groupby("dong_cd").tot.sum()
dl["소실유동비중"] = (lost_tot.reindex(dl.index).fillna(0) / dl.소실유동비중 * 100).round(3)
print("행정동별 소실률 상위 8")
print(dl.sort_values("소실률", ascending=False).head(8).to_string())
print()
print("-> 소실은 랜덤이 아니라 춘천 저밀도 면 지역에 집중된다")
"""),
    code("""
# 동 단위 집계 후 테이블 간 총량 격차
panel = sk_dong.build_space_panel()
panel["age_sum"] = panel[ac].sum(axis=1)
panel["time_sum"] = panel[tc].sum(axis=1)
panel["rel"] = (panel.age_sum - panel.time_sum).abs() / panel.age_sum
panel["지역"] = panel.dong_cd.str[:5].map(regions.SGG_NAMES)

print("동x월 282행의 AGE합 vs TIME합 상대격차 (%)")
print((panel.rel * 100).describe(percentiles=[0.5, 0.9, 0.95, 0.99]).round(4).to_string())
print()
print("지역별 (%)")
print((panel.groupby("지역").rel.agg(["mean", "max"]) * 100).round(4).to_string())
print()
print(f"전체 총량 기준 격차: "
      f"{(panel.age_sum.sum() - panel.time_sum.sum()) / panel.age_sum.sum() * 100:.5f}%")
print(f"상대격차 1% 초과: {int((panel.rel > 0.01).sum())} / {len(panel)} (동x월)")
print()
print("-> 중앙값 0.006%. 강남은 최대 0.03%로 사실상 없고,")
print("   춘천 면 지역 7개 동에서만 최대 3.3%다. 비율 지표를 쓰면 영향이 상쇄된다.")
"""),
    md("""
## 3. 비식별 컷 편향 정량화

카드 `USE_CNT` 최솟값이 5다. 5건 미만 집계셀이 삭제됐다는 뜻이다.
희소한 조합일수록 잘려 나가고, **우리가 찾는 고립 위험군이 바로 희소한 조합**이다.

정답을 볼 수 없으므로 두 지표로 간접 추정한다.

- `near_cut_share` — 살아남은 셀 중 `USE_CNT`가 최하단 밴드인 비율. 높을수록 절단선에 붙어 있다
- `combo_coverage` — 가능한 (업종 × 거주지) 조합 대비 실제 등장 비율. 낮을수록 많이 지워졌다

그 전에 `USE_CNT` 값 자체의 구조를 확인한다.
"""),
    md("""
### 3.1 `USE_CNT`에 결측 정수 구간이 있다

데이터2의 `USE_CNT`는 단순한 원시 건수가 아니다. 특정 정수가 아예 등장하지 않는다.
"""),
    code("""
card = card_cohort.prepare_card(2)
d1 = card_cohort.prepare_card(1)
print(f"데이터2 {len(card):,}행 / 데이터1 {len(d1):,}행")

rows = []
for v in range(1, 31):
    rows.append({
        "USE_CNT": v,
        "데이터2": int((card.USE_CNT == v).sum()),
        "데이터1": int((d1.USE_CNT == v).sum()),
    })
gap = pd.DataFrame(rows)
print()
print(gap.to_string(index=False))
"""),
    code("""
miss2 = [v for v in range(1, 61) if (card.USE_CNT == v).sum() == 0]
miss1 = [v for v in range(1, 61) if (d1.USE_CNT == v).sum() == 0]
print(f"데이터2 결측 정수(1~60): {miss2}")
print(f"데이터1 결측 정수(1~60): {miss1}")
print()
print("데이터2 등장 구간: [5,6] [11,13] [16,19] [22 이상 연속]")
print("데이터1은 1~4만 없고 나머지는 존재하나 빈도가 비정상적으로 낮다")
print(f"  데이터1 USE_CNT=10 빈도: {int((d1.USE_CNT == 10).sum()):,}건")
print(f"  데이터1 USE_CNT=20 빈도: {int((d1.USE_CNT == 20).sum()):,}건")
print(f"  데이터1 USE_CNT=11 빈도: {int((d1.USE_CNT == 11).sum()):,}건 (비교용)")
print()
print("-> 데이터2는 5건 미만 절단에 더해 추가 비식별 처리를 받았다.")
print("   따라서 '절단선 근접'은 최하단 밴드인 USE_CNT <= 6으로 정의한다.")
print(f"   USE_CNT <= 6 인 셀 비율: {(card.USE_CNT <= card_cohort.NEAR_CUT_MAX).mean() * 100:.2f}%")
"""),
    code("""
fig, ax = plt.subplots(figsize=(12, 4.5))
x = np.arange(1, 31)
w = 0.4
ax.bar(x - w / 2, [int((card.USE_CNT == v).sum()) for v in x], w,
       label="데이터2 (주제2)", color=PALETTE[0])
ax.bar(x + w / 2, [int((d1.USE_CNT == v).sum()) for v in x], w,
       label="데이터1 (주제1)", color=PALETTE[1])
ax.set_yscale("symlog")
ax.set_title("USE_CNT 하위 30개 값의 빈도 — 데이터2에만 결측 구간이 있다")
ax.set_xlabel("USE_CNT (결제 건수)")
ax.set_ylabel("셀 수 (symlog)")
ax.set_xticks(x)
ax.legend()
for v in miss2:
    if v <= 30:
        ax.axvline(v, color=PALETTE[5], alpha=0.15, lw=6)
plt.tight_layout()
plt.show()
print("붉은 세로 띠가 데이터2에서 관측되지 않는 값이다")
"""),
    md("### 3.2 어느 집단이 절단선에 붙어 있는가"),
    code("""
by_age = card_cohort.truncation_stats(card, by=["age_band"])
by_age["near_cut_share%"] = (by_age.near_cut_share * 100).round(2)
by_age["combo_coverage%"] = (by_age.combo_coverage * 100).round(2)
print("연령대별 절단 근접도와 조합 커버리지")
print(by_age[["age_band", "n_cells", "near_cut_share%", "median_use_cnt",
              "observed_combos", "combo_coverage%"]].to_string(index=False))
"""),
    code("""
fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
ax = axes[0]
ax.plot(by_age.age_band, by_age["near_cut_share%"], marker="o", color=PALETTE[5])
ax.set_title("연령대별 절단선 근접도")
ax.set_xlabel("연령대")
ax.set_ylabel("USE_CNT <= 6 셀 비율 (%)")

ax = axes[1]
ax.plot(by_age.age_band, by_age["combo_coverage%"], marker="s", color=PALETTE[0])
ax.set_title("연령대별 (업종 x 거주지) 조합 커버리지")
ax.set_xlabel("연령대")
ax.set_ylabel("등장 조합 비율 (%)")
plt.tight_layout()
plt.show()

lo, hi = by_age.iloc[0], by_age.iloc[-1]
print(f"10대 절단근접 {lo['near_cut_share%']:.1f}% / 커버리지 {lo['combo_coverage%']:.1f}%")
print(f"90대 절단근접 {hi['near_cut_share%']:.1f}% / 커버리지 {hi['combo_coverage%']:.1f}%")
"""),
    code("""
by_sgg_t = card_cohort.truncation_stats(card, by=["MCT_SGG_CD"])
by_sgg_t["near_cut_share%"] = (by_sgg_t.near_cut_share * 100).round(2)
by_sgg_t["combo_coverage%"] = (by_sgg_t.combo_coverage * 100).round(2)
print("지역별")
print(by_sgg_t[["MCT_SGG_CD", "n_cells", "near_cut_share%", "median_use_cnt",
                "combo_coverage%"]].to_string(index=False))
print()

by_ry = card_cohort.truncation_stats(card, by=["MCT_RY_CD"])
by_ry["near_cut_share%"] = (by_ry.near_cut_share * 100).round(2)
top = by_ry.nlargest(10, "near_cut_share")[["MCT_RY_CD", "n_cells", "near_cut_share%",
                                            "median_use_cnt"]]
bot = by_ry.nsmallest(5, "near_cut_share")[["MCT_RY_CD", "n_cells", "near_cut_share%",
                                            "median_use_cnt"]]
print("절단선에 가장 가까운 업종 10종")
print(top.to_string(index=False))
print()
print("가장 먼 업종 5종")
print(bot.to_string(index=False))
"""),
    code("""
# 연령 x 지역 교차
cross = card_cohort.truncation_stats(card, by=["MCT_SGG_CD", "age_band"])
piv = cross.pivot(index="MCT_SGG_CD", columns="age_band", values="near_cut_share").mul(100)

fig, ax = plt.subplots(figsize=(11, 3.2))
im = ax.imshow(piv.values, cmap="YlOrRd", aspect="auto")
ax.set_xticks(range(len(piv.columns)))
ax.set_xticklabels([f"{c}대" for c in piv.columns])
ax.set_yticks(range(len(piv.index)))
ax.set_yticklabels(piv.index)
ax.set_title("지역 x 연령별 절단선 근접도 (USE_CNT <= 6 셀 비율 %)")
ax.set_xlabel("연령대")
ax.grid(False)
for i in range(piv.shape[0]):
    for j in range(piv.shape[1]):
        ax.text(j, i, f"{piv.values[i, j]:.0f}", ha="center", va="center", fontsize=9)
plt.colorbar(im, ax=ax, label="비율 (%)")
plt.tight_layout()
plt.show()

print("사회적 업종 12종만 따로 보면")
soc = card[card.is_social]
soc_stats = card_cohort.truncation_stats(soc, by=["age_band"])
soc_stats["near_cut_share%"] = (soc_stats.near_cut_share * 100).round(2)
print(soc_stats[["age_band", "n_cells", "near_cut_share%", "median_use_cnt"]].to_string(index=False))
"""),
    md("""
## 4. 시계열 무결성
"""),
    code("""
rep = loaders.dedupe_report()
piv_m = rep.pivot(index="ym", columns="table", values="rows_dedup")
print("월별 고유 격자 수 (중복 제거 후)")
print(piv_m.to_string())
print()
print("월별 변화율 (%)")
print((piv_m.pct_change() * 100).round(2).to_string())

fig, ax = plt.subplots(figsize=(10, 4.5))
for i, t in enumerate(piv_m.columns):
    ax.plot(piv_m.index, piv_m[t], marker="o", label=t.upper(), color=PALETTE[i])
ax.set_title("SK 테이블별 월간 고유 격자 수 추이")
ax.set_xlabel("기준년월")
ax.set_ylabel("격자 수")
ax.legend()
plt.tight_layout()
plt.show()
"""),
    code("""
daily = card.groupby("TA_YMD").agg(행수=("USE_CNT", "size"), 건수=("USE_CNT", "sum"),
                                    금액=("TS_AT", "sum")).reset_index()
daily["date"] = pd.to_datetime(daily.TA_YMD, format="%Y%m%d")
daily["요일"] = daily.date.dt.dayofweek.map(
    {0: "월", 1: "화", 2: "수", 3: "목", 4: "금", 5: "토", 6: "일"})

missing = pd.date_range("2025-07-01", "2025-12-31").difference(daily.date)
print(f"기간 내 누락일: {len(missing)}일")
print(f"일별 행수 — 평균 {daily.행수.mean():,.0f} / 최소 {daily.행수.min():,} / 최대 {daily.행수.max():,}")

fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
axes[0].plot(daily.date, daily.행수, color=PALETTE[0], lw=1)
axes[0].set_title("신한카드 데이터2 — 일별 집계 행수")
axes[0].set_ylabel("행수")
axes[1].plot(daily.date, daily.건수 / 1e6, color=PALETTE[1], lw=1)
axes[1].set_title("일별 결제 건수")
axes[1].set_ylabel("건수 (백만)")
axes[1].set_xlabel("일자")
plt.tight_layout()
plt.show()
"""),
    code("""
fig, ax = plt.subplots(figsize=(9, 4.5))
order = ["월", "화", "수", "목", "금", "토", "일"]
data = [daily.loc[daily.요일 == d, "건수"].values / 1e6 for d in order]
bp = ax.boxplot(data, tick_labels=order, patch_artist=True)
for patch in bp["boxes"]:
    patch.set_facecolor(PALETTE[4])
ax.set_title("요일별 결제 건수 분포")
ax.set_xlabel("요일")
ax.set_ylabel("일 결제 건수 (백만)")
plt.tight_layout()
plt.show()

print("결제 건수 하위 10일 (공휴일 후보)")
print(daily.nsmallest(10, "건수")[["TA_YMD", "요일", "행수", "건수"]].to_string(index=False))
print()
print("결제 건수 상위 5일")
print(daily.nlargest(5, "건수")[["TA_YMD", "요일", "행수", "건수"]].to_string(index=False))
"""),
    md("""
## 5. 분포 구조
"""),
    code("""
dong_tot = panel.groupby(["dong_cd", "지역"], observed=True).age_sum.mean().reset_index()
print("행정동별 월평균 총유동 분포")
print(dong_tot.groupby("지역").age_sum.describe(
    percentiles=[0.25, 0.5, 0.75]).round(0).to_string())
print()
print(f"강남/춘천 동 평균 배율: "
      f"{dong_tot[dong_tot.지역 == '서울 강남구'].age_sum.mean() / dong_tot[dong_tot.지역 == '강원 춘천시'].age_sum.mean():.2f}배")

g = age.copy()
g["tot"] = g[ac].sum(axis=1)
g = g.sort_values("tot", ascending=False)
top1 = int(len(g) * 0.01)
print(f"\\n격자 상위 1%({top1:,}개)가 차지하는 유동인구 비중: "
      f"{g.head(top1).tot.sum() / g.tot.sum() * 100:.2f}%")
print(f"격자 상위 10%가 차지하는 비중: {g.head(len(g) // 10).tot.sum() / g.tot.sum() * 100:.2f}%")
"""),
    code("""
fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
ax = axes[0]
bins = np.logspace(-2, 4.2, 60)
for i, (cd, nm) in enumerate(regions.SGG_NAMES.items()):
    sub = g[g.BLOCK_CD.str[:5] == cd]
    ax.hist(sub.tot.clip(lower=0.01), bins=bins, alpha=0.65, label=nm, color=PALETTE[i])
ax.set_xscale("log")
ax.set_yscale("log")
ax.set_title("격자 총유동 분포 (2025-07)")
ax.set_xlabel("격자 일평균 총유동 (명, 로그)")
ax.set_ylabel("격자 수 (로그)")
ax.legend()

ax = axes[1]
dd = dong_tot.sort_values("age_sum", ascending=False)
colors = [SGG_COLORS[z] for z in dd.지역]
ax.barh(range(len(dd)), dd.age_sum, color=colors)
ax.set_yticks([])
ax.invert_yaxis()
ax.set_title("행정동 47개 월평균 총유동 (내림차순)")
ax.set_xlabel("월평균 총유동 (명)")
handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in SGG_COLORS.values()]
ax.legend(handles, list(SGG_COLORS), loc="lower right")
plt.tight_layout()
plt.show()
"""),
    md("""
## 핵심 발견

**1. SK의 0은 비식별 마스킹이 아니라 실제 0일 가능성이 높다.**
모든 값이 0.0254의 정수배이고 그 미만 양수가 하나도 없다.
24칸·12칸·7칸이 전부 0인 격자가 0행이고, `AGE`합=0이면서 `WKDY`합>0인 격자도 0행이다.
0칸이 많은 격자에서 관측된 총량 격차(최대 0.12)는 24칸 반올림 누적 오차 한계와 정확히 일치한다.
따라서 0을 결측으로 처리하지 않는다.

**2. 격자 커버리지 불일치는 행 기준 21%지만 정보량 기준 0.02%다.**
소실 격자의 일평균 유동인구는 중앙값 0.069명, 최댓값 0.261명으로 사실상 빈 격자다.
다만 소실은 랜덤이 아니라 춘천 저밀도 면 지역에 집중된다.
동 단위 집계 시 테이블 간 총량 격차는 중앙값 0.006%, 강남 최대 0.03%로 무시 가능하나
춘천 면 7개 동에서는 최대 3.3%가 남는다. 절대량 대신 비율 지표를 쓴다.

**3. 비식별 컷은 고령층·춘천·희소 업종을 체계적으로 지우며, 데이터2는 추가 가공까지 받았다.**

데이터2의 `USE_CNT`에는 `1~4`뿐 아니라 `7~10`, `14~15`, `20~21`이 아예 없다.
등장 구간이 `[5,6] [11,13] [16,19] [22~]`로 22 이상부터만 연속이다.
같은 출처인 데이터1에는 `1~4`만 없고 나머지는 모두 존재한다.
즉 데이터2는 5건 미만 절단에 더해 **추가 비식별 처리**를 받았다.
`USE_CNT`를 원시 건수로 다루면 안 되고, 건당 결제액은 최하단 구간에서 왜곡된다.

절단 편향의 방향은 명확하다. 연령대별 절단선 근접도와 조합 커버리지가 U자를 그리며
90대에서 가장 나쁘고, 춘천이 강남보다 일관되게 나쁘다.
이는 고립 위험군을 찾는 분석에 정확히 역방향으로 작용한다. 발표 자료의 핵심 논거로 쓴다.

**다음 단계** — 2단계에서 강남·춘천의 인구·시간 패턴을 대조하고 타겟 지역을 좁힌다.
"""),
]


def main() -> None:
    out = ROOT / "notebooks" / "260920_EDA_01_quality.ipynb"
    check(build(CELLS, out))


if __name__ == "__main__":
    main()
