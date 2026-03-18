from datetime import datetime
from pathlib import Path
from typing import List, Dict
import json
import re

import requests
from bs4 import BeautifulSoup


# ==============================
# 기본 경로 설정
# ==============================
# 기존에는 data/genie.json 한 파일만 덮어썼지만,
# 이제는 data/genie/2026-03-17_21.json 처럼
# 시간별 파일을 저장하기 위해 폴더 경로를 사용합니다.
BASE_DIR = Path("data")
SITE_NAME = "genie"
SITE_DIR = BASE_DIR / SITE_NAME


GENIE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/146.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.genie.co.kr/chart/top200",
}

GENIE_URL = "https://www.genie.co.kr/chart/top200"


def _fetch_genie_page(page: int) -> str:
    """
    지니 차트 페이지 HTML을 가져옵니다.

    pg=1 -> 1~50위
    pg=2 -> 51~100위
    """
    params = {
        "ditc": "D",
        "rtm": "Y",
        "pg": page,
    }

    response = requests.get(
        GENIE_URL,
        headers=GENIE_HEADERS,
        params=params,
        timeout=10,
    )
    response.raise_for_status()
    return response.text


def _parse_genie_items(html: str, start_rank: int) -> List[Dict]:
    """
    지니 차트 HTML에서 곡 목록을 파싱합니다.

    start_rank:
    - 1페이지면 1
    - 2페이지면 51
    """
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("tr.list")

    collected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    items: List[Dict] = []

    # HTML 안에 등락 관련 숫자가 섞일 수 있으므로
    # rows 순서대로 rank를 직접 부여합니다.
    for index, row in enumerate(rows, start=start_rank):
        # 제목
        title_tag = row.select_one("td.info a.title.ellipsis")
        title = title_tag.get_text(strip=True) if title_tag else ""

        # 가수
        artist_tag = row.select_one("td.info a.artist.ellipsis")
        artist = artist_tag.get_text(strip=True) if artist_tag else ""

        # 이미지
        img_tag = row.select_one("a.cover img")
        album_image = ""

        if img_tag:
            album_image = (
                img_tag.get("src")
                or img_tag.get("data-src")
                or img_tag.get("lazy-src")
                or ""
            ).strip()

            # //image... 형태면 https: 붙여서 완전한 URL로 만듭니다.
            if album_image.startswith("//"):
                album_image = f"https:{album_image}"
            # /images/... 형태면 도메인을 붙여 완전한 URL로 만듭니다.
            elif album_image.startswith("/"):
                album_image = f"https://www.genie.co.kr{album_image}"

        items.append(
            {
                "rank": index,
                "title": title,
                "artist": artist,
                "album_image": album_image,
                "collected_at": collected_at,
            }
        )

    return items


def fetch_genie_chart(limit: int = 100) -> List[Dict]:
    """
    지니 TOP100을 가져옵니다.
    1~50위, 51~100위를 합쳐서 반환합니다.
    """
    all_items: List[Dict] = []

    # 1페이지: 1~50위
    html_page_1 = _fetch_genie_page(page=1)
    items_page_1 = _parse_genie_items(html_page_1, start_rank=1)
    all_items.extend(items_page_1)

    # 2페이지: 51~100위
    html_page_2 = _fetch_genie_page(page=2)
    items_page_2 = _parse_genie_items(html_page_2, start_rank=51)
    all_items.extend(items_page_2)

    return all_items[:limit]


def _get_current_hour_file_path() -> Path:
    """
    현재 시각 기준 시간별 파일 경로를 만듭니다.

    예:
    data/genie/2026-03-17_21.json
    """
    filename = datetime.now().strftime("%Y-%m-%d_%H.json")
    return SITE_DIR / filename


def cleanup_old_files(site_dir: Path, keep: int = 48):
    """
    오래된 JSON 파일을 정리합니다.

    keep=48 이면 최근 48개 파일만 남깁니다.
    1시간마다 저장한다면 약 2일치 보관입니다.
    """
    files = sorted(site_dir.glob("*.json"))

    if len(files) <= keep:
        return

    for old_file in files[:-keep]:
        old_file.unlink(missing_ok=True)


def fetch_genie_chart_and_save(limit: int = 100):
    """
    지니 차트를 가져와 시간별 JSON 파일로 저장합니다.
    """
    items = fetch_genie_chart(limit=limit)

    data = {
        "site": SITE_NAME,
        "count": len(items),
        "items": items,
    }

    # data/genie 폴더가 없으면 생성
    SITE_DIR.mkdir(parents=True, exist_ok=True)

    # 현재 시간 기준 파일명으로 저장
    file_path = _get_current_hour_file_path()

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 오래된 파일 정리
    cleanup_old_files(SITE_DIR, keep=48)


def _load_json_file(file_path: Path) -> List[Dict]:
    """
    특정 JSON 파일에서 items 배열만 읽어 반환합니다.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)["items"]


def _normalize_text(text: str) -> str:
    """
    비교용 문자열 정규화
    - 소문자 변환
    - 앞뒤 공백 제거
    - 여러 공백을 한 칸으로 정리
    """
    text = (text or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _normalize_artist(artist: str) -> str:
    """
    가수명 비교용 정규화
    - 괄호 제거
    - 공백 정리
    - 소문자 변환
    """
    artist = _normalize_text(artist)
    artist = re.sub(r"\([^)]*\)", "", artist)
    artist = re.sub(r"\s+", " ", artist).strip()
    return artist


def _make_key(item: Dict) -> str:
    """
    같은 곡 판별용 key 생성
    제목 + 정규화된 가수명 기준으로 비교합니다.
    """
    title = _normalize_text(item.get("title", ""))
    artist = _normalize_artist(item.get("artist", ""))
    return f"{title}|{artist}"


def _get_latest_two_files() -> List[Path]:
    """
    가장 최근 JSON 파일 2개를 반환합니다.

    파일이 없으면 []
    파일이 1개면 [최신파일]
    파일이 2개 이상이면 [이전파일, 현재파일]
    """
    if not SITE_DIR.exists():
        return []

    files = sorted(SITE_DIR.glob("*.json"))
    return files[-2:]


def load_genie_chart() -> List[Dict]:
    """
    가장 최신 지니 차트만 반환합니다.
    순위 변동 없이 '현재 차트'만 필요할 때 사용합니다.
    """
    files = _get_latest_two_files()

    # 저장 파일이 없으면 한 번 수집해서 파일 생성
    if not files:
        fetch_genie_chart_and_save()
        files = _get_latest_two_files()

    if not files:
        return []

    # 가장 최신 파일의 items 반환
    return _load_json_file(files[-1])


def load_genie_chart_with_change() -> List[Dict]:
    """
    가장 최신 지니 차트를 읽고,
    이전 파일과 비교하여 rank_change / rank_status를 붙여 반환합니다.

    rank_change:
    - 이전 순위 - 현재 순위
    - 예) 이전 5위, 현재 3위 => 2 (2칸 상승)

    rank_status:
    - UP / DOWN / SAME / NEW
    """
    files = _get_latest_two_files()

    # 파일이 없으면 한 번 수집해서 파일 생성
    if not files:
        fetch_genie_chart_and_save()
        files = _get_latest_two_files()

    if not files:
        return []

    # 최신 파일 = 현재 차트
    current_items = _load_json_file(files[-1])

    # 비교할 이전 파일이 없으면 전부 NEW 처리
    if len(files) == 1:
        result = []

        for item in current_items:
            new_item = dict(item)
            new_item["rank_change"] = None
            new_item["rank_status"] = "NEW"
            result.append(new_item)

        return result

    # 이전 파일 읽기
    previous_items = _load_json_file(files[-2])

    # 이전 차트의 곡별 rank를 미리 맵으로 만들어 둡니다.
    previous_rank_map = {
        _make_key(item): item.get("rank")
        for item in previous_items
    }

    result = []

    # 현재 차트 곡 하나씩 순회하며 이전 순위와 비교
    for item in current_items:
        new_item = dict(item)

        current_rank = item.get("rank")
        previous_rank = previous_rank_map.get(_make_key(item))

        # 이전 차트에 없던 곡이면 NEW
        if previous_rank is None:
            new_item["rank_change"] = None
            new_item["rank_status"] = "NEW"

        else:
            # 이전 5위 -> 현재 3위면 2칸 상승
            diff = previous_rank - current_rank
            new_item["rank_change"] = diff

            if diff > 0:
                new_item["rank_status"] = "UP"
            elif diff < 0:
                new_item["rank_status"] = "DOWN"
            else:
                new_item["rank_status"] = "SAME"

        result.append(new_item)

    return result