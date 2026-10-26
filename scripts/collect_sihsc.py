"""서울시고립예방센터(sihsc.welfare.seoul.kr) 협력기관 지도와 지원사업을 수집한다.

- 협력기관 지도: 5개 탭 목록(기관명·좌표) + 기관별 상세 API(사업구분·주소·전화·홈페이지)
- 지원사업 검색: 목록 전체 페이지 + 사업별 상세 페이지(사업구분·기관·자치구·기간·대상·본문)

실행: python scripts/collect_sihsc.py  → data/raw/reference_data/복지기관_수집/sihsc_*.csv
"""

import csv
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.features.institutions import RAW_DIR  # noqa: E402

BASE = "https://sihsc.welfare.seoul.kr/knockseoul"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120"}
MAP_TABS = {
    1: "서울연결처방",
    2: "고립가구 전담기구",
    3: "아름다운 동행가게",
    4: "은둔거부가구 맞춤형 지원",
    5: "지역밀착형 복지관",
}
PROGRAM_FIELDS = ["사업구분", "기관명", "자치구", "모집기간", "진행기간", "성별", "연령"]
PAUSE_SEC = 0.2  # 공공기관 서버라 요청 간격을 둔다


def fetch(url: str, data: dict | None = None, ajax: bool = False) -> str:
    """GET 또는 form POST 응답 본문을 문자열로 받는다."""
    headers = dict(HEADERS, **({"X-Requested-With": "XMLHttpRequest"} if ajax else {}))
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers)
    time.sleep(PAUSE_SEC)
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8")


def text_lines(page: str) -> list[str]:
    """HTML에서 스크립트를 빼고 화면에 보이는 줄만 남긴다."""
    page = re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S)
    lines = html.unescape(re.sub(r"<[^>]+>", "\n", page)).split("\n")
    return [line.strip() for line in lines if line.strip()]


def collect_map() -> list[dict]:
    """협력기관 지도 5개 탭의 기관을 탭별로 한 행씩 모은다 (한 기관이 여러 탭에 나올 수 있다)."""
    rows = []
    for tab_no, tab_name in MAP_TABS.items():
        page = fetch(f"{BASE}/030204/businessmap/list.do?tabNo={tab_no}&searchType1=")
        items = re.findall(
            r'<li data-seq="(\d+)" data-la="([^"]*)" data-lo="([^"]*)" data-nm="([^"]*)"', page
        )
        counts = dict(re.findall(r"tab\('(\d)'\)\"[^>]*><span>[^<(]*\((\d+)\)", page))
        expected = int(counts[str(tab_no)])  # 탭 이름 옆에 표시된 기관 수
        assert len(items) == expected, (tab_name, len(items), expected)
        for seq, lat, lon, name in items:
            info = json.loads(
                fetch(f"{BASE}/030204/businessmap/viewAjax.do", {"seq": seq}, ajax=True)
            )["result"]
            rows.append(
                {
                    "TAB_NO": tab_no,
                    "TAB_NAME": tab_name,
                    "SEQ": seq,
                    "NAME": html.unescape(name),
                    "BSNS_DIV": info.get("bsns_div") or "",
                    "GU": info.get("gu") or "",
                    "ADDR": f"{info.get('addr') or ''} {info.get('daddr') or ''}".strip(),
                    "TEL": info.get("hp") or "",
                    "URL": info.get("url") or "",
                    "LAT": lat,
                    "LON": lon,
                    "UPD_DT": (info.get("upd_dt") or info.get("reg_dt") or "")[:10],
                }
            )
    return rows


def collect_programs() -> list[dict]:
    """지원사업 목록의 모든 페이지를 돌고, 사업마다 상세 페이지를 읽는다."""
    first = fetch(f"{BASE}/030203/bsns/list.do")
    total = int(re.search(r'id="totalCount" name="totalCount" value="(\d+)"', first).group(1))
    ids: list[str] = []
    page_no = 1
    while len(ids) < total:
        page = fetch(
            f"{BASE}/030203/bsns/list.do", {"currentPageNo": page_no, "recordsPerPage": 12}
        )
        found = re.findall(r"goView\((\d+)\)", page)
        if not found:
            break
        ids += [i for i in found if i not in ids]
        page_no += 1
    assert len(ids) == total, (len(ids), total)

    rows = []
    for seq in ids:
        lines = text_lines(fetch(f"{BASE}/030203/bsns/view.do", {"bsns_seq": seq}))
        top = max(k for k, line in enumerate(lines) if line.startswith("외로울 땐 여기가지"))
        row = {"BSNS_SEQ": seq, "TITLE": lines[top + 1], "REG_DT": lines[top + 2][:10]}
        for field in PROGRAM_FIELDS:
            k = lines.index(f"{field} :", top)
            row[field] = lines[k + 1]
        start = lines.index("연령 :", top) + 2
        end = next(
            (k for k in range(start, len(lines)) if lines[k] in ("다음 글", "이전 글", "목록")),
            len(lines),
        )
        row["CONTENT"] = " / ".join(lines[start:end])
        rows.append(row)
    return rows


def save(rows: list[dict], name: str) -> None:
    """UTF-8(BOM) CSV로 저장한다."""
    path = RAW_DIR / name
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"saved {path.name} rows={len(rows)}")


if __name__ == "__main__":
    save(collect_map(), "sihsc_businessmap.csv")
    save(collect_programs(), "sihsc_support_programs.csv")
