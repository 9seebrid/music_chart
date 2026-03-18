from datetime import datetime
from pathlib import Path
import json
import re

import requests
from bs4 import BeautifulSoup


# -----------------------------
# 기본 저장 경로 설정
# -----------------------------
# data/melon 폴더 안에 시간별 JSON 파일을 저장하기 위한 경로입니다.
# 예:
# data/melon/2026-03-17_13.json
BASE_DIR = Path("data")
SITE_NAME = "melon"
SITE_DIR = BASE_DIR / SITE_NAME


def fetch_melon_chart(limit: int = 100) -> list[dict]:
    """
    멜론 차트 페이지에 접속해서 차트 정보를 가져오는 함수

    반환값 예시:
    [
        {
            "rank": 1,
            "title": "노래 제목",
            "artist": "가수명",
            "album_image": "썸네일 주소",
            "collected_at": "2026-03-17 21:00:00"
        },
        ...
    ]

    limit:
        최대 몇 개까지 가져올지 지정
        기본값은 100개
    """
    url = "https://www.melon.com/chart/index.htm"

    # 일부 사이트는 브라우저가 아닌 요청을 막을 수 있기 때문에
    # User-Agent 헤더를 브라우저처럼 넣어줍니다.
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
    }

    # timeout=10:
    # 너무 오래 응답이 없으면 무한 대기하지 않도록 10초 제한
    response = requests.get(url, headers=headers, timeout=10)

    # 요청 실패(404, 500 등) 시 예외 발생
    response.raise_for_status()

    # HTML 파싱
    soup = BeautifulSoup(response.text, "html.parser")

    # 제목, 가수, 이미지 요소를 각각 선택
    titles = soup.find_all("div", {"class": "ellipsis rank01"})
    artists = soup.find_all("div", {"class": "ellipsis rank02"})
    album_images = soup.find_all("a", {"class": "image_typeAll"})

    title_list = []
    artist_list = []
    image_list = []

    # 제목 추출
    for title_tag in titles:
        a_tag = title_tag.find("a")
        title_list.append(a_tag.text.strip() if a_tag else "제목 없음")

    # 가수명 추출
    for artist_tag in artists:
        span_tag = artist_tag.find("span", {"class": "checkEllipsis"})
        artist_list.append(span_tag.text.strip() if span_tag else "가수 정보 없음")

    # 앨범 이미지 주소 추출
    for image_tag in album_images:
        img_tag = image_tag.find("img")
        image_list.append(img_tag.get("src", "").strip() if img_tag else "")

    # 제목/가수/이미지 개수가 완전히 같지 않을 수 있으므로
    # 가장 짧은 길이에 맞춰 안전하게 데이터 생성
    max_count = min(limit, len(title_list), len(artist_list), len(image_list))

    # 수집 시각 저장
    collected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    chart_data = []

    # 최종 차트 데이터 생성
    for i in range(max_count):
        chart_data.append(
            {
                "rank": i + 1,                  # 현재 순위
                "title": title_list[i],         # 곡 제목
                "artist": artist_list[i],       # 가수명
                "album_image": image_list[i],   # 썸네일 이미지
                "collected_at": collected_at,   # 수집 시각
            }
        )

    return chart_data


def _get_current_hour_file_path() -> Path:
    """
    현재 시각 기준 파일명을 만들어 반환하는 내부 함수

    예:
    현재 시각이 2026-03-17 21시라면
    data/melon/2026-03-17_21.json 반환
    """
    now = datetime.now()
    filename = now.strftime("%Y-%m-%d_%H.json")
    return SITE_DIR / filename


def cleanup_old_files(site_dir: Path, keep: int = 48):
    """
    오래된 JSON 파일을 정리하는 함수

    keep=48 이면 최근 48개 파일만 남기고
    그 이전 파일은 삭제합니다.

    1시간마다 저장한다면:
    - 48개 = 약 2일치 보관

    이 함수는 선택사항이지만,
    파일이 계속 쌓이는 걸 방지하는 데 유용합니다.
    """
    files = sorted(site_dir.glob("*.json"))

    # 보관 개수보다 적거나 같으면 삭제할 필요 없음
    if len(files) <= keep:
        return

    # 오래된 파일부터 삭제
    for old_file in files[:-keep]:
        old_file.unlink(missing_ok=True)


def fetch_melon_chart_and_save(limit: int = 100):
    """
    멜론 차트를 가져와서 시간별 JSON 파일로 저장하는 함수

    기존에는 data/melon.json 하나만 덮어썼다면,
    이제는 data/melon/2026-03-17_21.json 처럼
    시간별 파일을 생성합니다.
    """
    items = fetch_melon_chart(limit=limit)

    # API에서 사용하기 편하도록 site, count, items 구조 유지
    data = {
        "site": SITE_NAME,
        "count": len(items),
        "items": items,
    }

    # data/melon 폴더가 없으면 생성
    SITE_DIR.mkdir(parents=True, exist_ok=True)

    # 현재 시간 기준 파일 경로 생성
    file_path = _get_current_hour_file_path()

    # JSON 저장
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 오래된 파일 정리
    cleanup_old_files(SITE_DIR, keep=48)


def _load_json_file(file_path: Path) -> list[dict]:
    """
    특정 JSON 파일에서 items 배열만 꺼내서 반환하는 내부 함수

    반환 예:
    [
        {"rank": 1, "title": "...", ...},
        ...
    ]
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["items"]


def _normalize_text(text: str) -> str:
    """
    비교용 문자열 정규화 함수

    목적:
    - 대소문자 차이 제거
    - 앞뒤 공백 제거
    - 중간 공백 여러 개를 한 칸으로 통일

    예:
    "  IVE  " -> "ive"
    "IU" -> "iu"
    """
    text = (text or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _normalize_artist(artist: str) -> str:
    """
    가수명 비교용 정규화 함수

    목적:
    - 괄호 안 텍스트 제거
    - 대소문자 차이 제거
    - 공백 정리

    예:
    "IVE (아이브)" -> "ive"
    "IU" -> "iu"

    화면 표시용 원본은 그대로 두고,
    '비교할 때만' 이 함수를 사용합니다.
    """
    artist = _normalize_text(artist)

    # 괄호 안 텍스트 제거
    artist = re.sub(r"\([^)]*\)", "", artist)

    # 공백 다시 정리
    artist = re.sub(r"\s+", " ", artist).strip()

    return artist


def _make_key(item: dict) -> str:
    """
    곡 비교용 고유 키 생성 함수

    제목 + 정규화된 가수명 조합으로 key를 만듭니다.

    예:
    "Rebel Heart|ive"

    왜 필요한가?
    순위 비교 시 '같은 곡인지' 판단해야 하기 때문입니다.
    """
    title = _normalize_text(item.get("title", ""))
    artist = _normalize_artist(item.get("artist", ""))
    return f"{title}|{artist}"


def _get_latest_two_files() -> list[Path]:
    """
    가장 최근 JSON 파일 2개를 반환하는 내부 함수

    예:
    [
        Path("data/melon/2026-03-17_20.json"),
        Path("data/melon/2026-03-17_21.json")
    ]

    파일이 1개뿐이면 1개만 반환
    파일이 없으면 빈 리스트 반환
    """
    if not SITE_DIR.exists():
        return []

    files = sorted(SITE_DIR.glob("*.json"))
    return files[-2:]


def load_melon_chart() -> list[dict]:
    """
    멜론의 '가장 최신 차트 파일'만 읽어서 반환하는 함수

    이 함수는 순위 변동 없이
    현재 차트만 필요할 때 사용할 수 있습니다.
    """
    files = _get_latest_two_files()

    # 저장된 파일이 하나도 없으면 일단 한 번 수집해서 저장 시도
    if not files:
        fetch_melon_chart_and_save()
        files = _get_latest_two_files()

    # 그래도 없으면 빈 배열 반환
    if not files:
        return []

    # 가장 최신 파일의 items 반환
    return _load_json_file(files[-1])


def load_melon_chart_with_change() -> list[dict]:
    """
    멜론 최신 차트를 읽고,
    이전 차트와 비교해서 rank_change / rank_status를 추가한 뒤 반환

    추가되는 필드:
    - rank_change:
        이전 순위 - 현재 순위
        예) 이전 5위, 현재 3위 -> 2
    - rank_status:
        "UP", "DOWN", "SAME", "NEW"
    """
    files = _get_latest_two_files()

    # 파일이 없으면 일단 수집부터 시도
    if not files:
        fetch_melon_chart_and_save()
        files = _get_latest_two_files()

    if not files:
        return []

    # 가장 최신 파일 = 현재 차트
    current_items = _load_json_file(files[-1])

    # 파일이 1개뿐이면 비교 대상이 없으므로 모두 NEW 처리
    if len(files) == 1:
        result = []

        for item in current_items:
            new_item = dict(item)
            new_item["rank_change"] = None
            new_item["rank_status"] = "NEW"
            result.append(new_item)

        return result

    # 파일이 2개 이상이면
    # 마지막 파일 = 현재
    # 마지막 전 파일 = 이전
    previous_items = _load_json_file(files[-2])

    # 이전 차트의 곡별 순위를 맵으로 저장
    # key: 제목+가수 정규화
    # value: 이전 순위
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
            # diff 계산 방식:
            # 이전 5위 -> 현재 3위면 2칸 상승
            # 5 - 3 = 2
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