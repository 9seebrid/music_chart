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
# 기존 data/bugs.json 단일 파일 대신
# data/bugs/2026-03-17_21.json 형태로 시간별 저장합니다.
BASE_DIR = Path("data")
SITE_NAME = "bugs"
SITE_DIR = BASE_DIR / SITE_NAME


BUGS_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/146.0.0.0 Safari/537.36"
    ),
    "Referer": "https://music.bugs.co.kr/chart/track/realtime/total",
}

BUGS_URL = "https://music.bugs.co.kr/chart/track/realtime/total"


def fetch_bugs_chart(limit: int = 100) -> List[Dict]:
    """
    벅스 실시간 TOP100 차트를 크롤링합니다.
    """
    response = requests.get(
        BUGS_URL,
        headers=BUGS_HEADERS,
        timeout=10,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # 사용자님이 확인한 구조 기준:
    # table.list.trackList.byChart > tbody > tr
    rows = soup.select("table.list.trackList.byChart tbody tr")

    collected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    items: List[Dict] = []

    # HTML 안에 등락용 숫자가 섞일 수 있으니
    # rows 순서대로 직접 1,2,3... 순위를 부여합니다.
    for index, row in enumerate(rows[:limit], start=1):
        # 제목
        title_tag = row.select_one("p.title a")
        title = title_tag.get_text(strip=True) if title_tag else ""

        # 가수
        artist_tag = row.select_one("p.artist a")
        artist = artist_tag.get_text(strip=True) if artist_tag else ""

        # 앨범 이미지
        img_tag = row.select_one("a.thumbnail img")
        album_image = ""

        if img_tag:
            album_image = (
                img_tag.get("src")
                or img_tag.get("data-src")
                or img_tag.get("data-original")
                or ""
            ).strip()

            # //image... 형태면 https 붙이기
            if album_image.startswith("//"):
                album_image = f"https:{album_image}"
            # /img/... 형태면 bugs 도메인 붙이기
            elif album_image.startswith("/"):
                album_image = f"https://music.bugs.co.kr{album_image}"

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


def _get_current_hour_file_path() -> Path:
    """
    현재 시간 기준 시간별 파일 경로를 만듭니다.

    예:
    data/bugs/2026-03-17_21.json
    """
    filename = datetime.now().strftime("%Y-%m-%d_%H.json")
    return SITE_DIR / filename


def cleanup_old_files(site_dir: Path, keep: int = 48):
    """
    오래된 JSON 파일을 정리합니다.
    최근 keep개만 남기고 이전 파일은 삭제합니다.
    """
    files = sorted(site_dir.glob("*.json"))

    if len(files) <= keep:
        return

    for old_file in files[:-keep]:
        old_file.unlink(missing_ok=True)


def fetch_bugs_chart_and_save(limit: int = 100):
    """
    벅스 차트를 가져와 시간별 JSON 파일로 저장합니다.
    """
    items = fetch_bugs_chart(limit=limit)

    data = {
        "site": SITE_NAME,
        "count": len(items),
        "items": items,
    }

    # data/bugs 폴더 생성
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
    """
    title = _normalize_text(item.get("title", ""))
    artist = _normalize_artist(item.get("artist", ""))
    return f"{title}|{artist}"


def _get_latest_two_files() -> List[Path]:
    """
    최근 JSON 파일 2개를 반환합니다.
    """
    if not SITE_DIR.exists():
        return []

    files = sorted(SITE_DIR.glob("*.json"))
    return files[-2:]


def load_bugs_chart() -> List[Dict]:
    """
    가장 최신 벅스 차트만 반환합니다.
    """
    files = _get_latest_two_files()

    if not files:
        fetch_bugs_chart_and_save()
        files = _get_latest_two_files()

    if not files:
        return []

    return _load_json_file(files[-1])


def load_bugs_chart_with_change() -> List[Dict]:
    """
    가장 최신 벅스 차트를 읽고,
    이전 파일과 비교해 rank_change / rank_status를 붙여 반환합니다.
    """
    files = _get_latest_two_files()

    if not files:
        fetch_bugs_chart_and_save()
        files = _get_latest_two_files()

    if not files:
        return []

    # 최신 파일 = 현재 차트
    current_items = _load_json_file(files[-1])

    # 이전 파일이 없으면 전부 NEW 처리
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

    # 이전 차트의 곡별 순위 맵 생성
    previous_rank_map = {
        _make_key(item): item.get("rank")
        for item in previous_items
    }

    result = []

    # 현재 차트와 이전 차트 비교
    for item in current_items:
        new_item = dict(item)

        current_rank = item.get("rank")
        previous_rank = previous_rank_map.get(_make_key(item))

        # 이전 차트에 없으면 NEW
        if previous_rank is None:
            new_item["rank_change"] = None
            new_item["rank_status"] = "NEW"

        else:
            # 이전 10위 -> 현재 7위면 3칸 상승
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