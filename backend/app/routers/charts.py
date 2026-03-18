import re
from fastapi import APIRouter, HTTPException, Query

# 각 사이트별 "저장된 JSON 파일을 읽는 함수" import
# 여기서는 실시간 크롤링을 하지 않고,
# 미리 만들어둔 JSON 파일을 읽어서 응답합니다.
from app.services.melon import load_melon_chart_with_change
from app.services.genie import load_genie_chart_with_change
from app.services.bugs import load_bugs_chart_with_change

# 공통 주소(prefix) 설정
# 이 파일에서 만든 API들은 모두 /api/charts 아래로 시작합니다.
#
# 예:
# GET /api/charts?site=melon
# GET /api/charts/compare?keyword=아이유
router = APIRouter(prefix="/api/charts", tags=["charts"])

# 현재 지원하는 사이트 목록
# 지원하지 않는 site 값이 들어왔을 때 에러 메시지에 사용합니다.
SUPPORTED_SITES = ["melon", "genie", "bugs"]


router = APIRouter(prefix="/api/charts", tags=["charts"])

SUPPORTED_SITES = ["melon", "genie", "bugs"]


@router.get("")
def get_chart(
    site: str = Query(
        ...,
        description="조회할 음악 사이트 이름. 예: melon, genie, bugs"
    )
):
    """
    사이트별 차트를 반환하는 API

    예:
    /api/charts?site=melon

    반환:
    {
        "site": "melon",
        "count": 100,
        "items": [...]
    }

    각 item 안에는 rank_change, rank_status도 포함됩니다.
    """
    normalized_site = site.strip().lower()

    try:
        # 사용자가 melon / Melon / MELON 등으로 입력해도
        # 소문자로 통일해서 처리
        if normalized_site == "melon":
            items = load_melon_chart_with_change()

        elif normalized_site == "genie":
            items = load_genie_chart_with_change()

        elif normalized_site == "bugs":
            items = load_bugs_chart_with_change()

        else:
            # 지원하지 않는 사이트가 들어오면 400 에러 반환
            raise HTTPException(
                status_code=400,
                detail=(
                    f"지원하지 않는 사이트입니다: {site} / "
                    f"지원 사이트: {SUPPORTED_SITES}"
                ),
            )

        return {
            "site": normalized_site,
            "count": len(items),
            "items": items,
        }

    except HTTPException:
        # 이미 의도적으로 발생시킨 HTTPException은 그대로 전달
        raise

    except Exception as e:
        # 그 외 예외는 서버 에러로 처리
        raise HTTPException(status_code=500, detail=f"차트 조회 실패: {str(e)}")


@router.get("/compare")
def compare_charts(
    keyword: str = Query(
        "", description="곡명 또는 가수명 검색어. 비워두면 전체 비교 결과 반환"
    )
):
    """
    사이트 통합 비교 API

    사용 예시:
    GET /api/charts/compare
    GET /api/charts/compare?keyword=아이유
    GET /api/charts/compare?keyword=love

    동작 방식:
    1. 멜론 / 지니 / 벅스의 JSON 파일을 모두 읽습니다.
    2. 같은 곡(제목 + 가수)을 하나의 데이터로 합칩니다.
    3. 각 사이트의 순위를 melon_rank / genie_rank / bugs_rank 로 저장합니다.
    4. keyword가 있으면 곡명/가수명 기준으로 필터링합니다.
    5. 가장 높은 순위(숫자가 가장 작은 값) 기준으로 정렬해서 반환합니다.
    """

    try:

        # 각 사이트의 최신 차트 + 순위 변동 정보까지 함께 로드
        melon_items = load_melon_chart_with_change()
        genie_items = load_genie_chart_with_change()
        bugs_items = load_bugs_chart_with_change()

        # 사이트별 데이터를 하나로 합치기 위한 딕셔너리
        #
        # key 예시:
        # "love wins all|아이유"
        #
        # value 예시:
        # {
        #   "title": "Love wins all",
        #   "artist": "아이유",
        #   "thumbnail": "...",
        #   "melon_rank": 1,
        #   "genie_rank": 3,
        #   "bugs_rank": 5,
        # }
        merged = {}
        
        # =========================
        # 비교용 문자열 정규화 함수
        # =========================

        # 기본 텍스트 정리:
        # - 앞뒤 공백 제거
        # - 소문자 변환
        # - 여러 공백을 한 칸으로 통일
        def normalize_text(text: str) -> str:
            text = text.strip().lower()
            text = re.sub(r"\s+", " ", text)
            return text

        # 가수명 정리:
        # - 아이유(IU), 아이유 (IU) -> 아이유
        def normalize_artist(artist: str) -> str:
            artist = normalize_text(artist)

            # 괄호 안 내용 제거
            artist = re.sub(r"\([^)]*\)", "", artist)

            # 제거 후 공백 다시 정리
            artist = re.sub(r"\s+", " ", artist).strip()
            return artist

        # 제목 정리:
        # 지금은 공백/대소문자만 정리
        def normalize_title(title: str) -> str:
            title = normalize_text(title)
            return title

        # 공통 병합 함수
        # items: 각 사이트의 곡 목록
        # site_name: "melon" / "genie" / "bugs"
        def add_items(items, site_name):
            for item in items:
                # 곡 제목, 가수명, 순위 꺼내기
                title = item.get("title", "").strip()
                artist = item.get("artist", "").strip()
                rank = item.get("rank")

                # 사이트마다 이미지 key 이름이 다를 수 있으므로
                # album_image -> image -> thumbnail 순서로 확인
                # 현재 사용자님 차트 데이터는 album_image를 쓰고 있으므로
                # 이 값을 먼저 확인해야 비교 카드에도 이미지가 표시됩니다.
                thumbnail = (
                    item.get("album_image")
                    or item.get("image")
                    or item.get("thumbnail")
                    or ""
                )                

                # 같은 곡 판별용 key            
                # =========================
                # 정규화 후 병합용 key 생성
                # =========================
                normalized_title = normalize_title(title)
                normalized_artist = normalize_artist(artist)

                key = f"{normalized_title}|{normalized_artist}"

                # 아직 merged에 없는 곡이면 기본 구조 생성
                if key not in merged:
                    merged[key] = {
                        "title": item["title"],
                        "artist": item["artist"],
                        "thumbnail": item.get("album_image", ""),

                        # 각 사이트 순위
                        "melon_rank": None,
                        "genie_rank": None,
                        "bugs_rank": None,

                        # 각 사이트 순위 변동값
                        "melon_rank_change": None,
                        "genie_rank_change": None,
                        "bugs_rank_change": None,

                        # 각 사이트 순위 상태
                        "melon_rank_status": None,
                        "genie_rank_status": None,
                        "bugs_rank_status": None,
                        
                        "search_text": f"{title.lower()} {artist.lower()} {normalized_artist.lower()}",
                    }

                # 사이트별 순위 저장
                merged[key][f"{site_name}_rank"] = rank
                merged[key][f"{site_name}_rank_change"] = item.get("rank_change")
                merged[key][f"{site_name}_rank_status"] = item.get("rank_status")
                
                # 같은 곡이 다른 사이트에서 또 들어올 때,
                extra_search_text = f" {title.lower()} {artist.lower()} {normalized_artist.lower()}"
                # 검색용 문자열에도 원본 가수명/정규화 가수명을 계속 누적합니다.
                merged[key]["search_text"] += extra_search_text

                # 기존 썸네일이 비어 있고 이번 item에 썸네일이 있으면 채워넣기
                if not merged[key]["thumbnail"] and thumbnail:
                    merged[key]["thumbnail"] = thumbnail

        # 각 사이트 데이터를 merged에 차례대로 추가
        add_items(melon_items, "melon")
        add_items(genie_items, "genie")
        add_items(bugs_items, "bugs")

        # 딕셔너리 -> 리스트 변환
        # 프론트에서 배열 형태가 다루기 쉽기 때문
        results = list(merged.values())

        # 검색어(keyword) 정리
        normalized_keyword = keyword.strip().lower()

        # 검색어가 들어온 경우:
        # 곡명 또는 가수명에 검색어가 포함된 데이터만 남김
        if normalized_keyword:
            results = [
                item
                for item in results
                if normalized_keyword in item["search_text"]
            ]

        # 정렬 기준:
        # 세 사이트 순위 중 "가장 높은 순위"를 기준으로 오름차순 정렬
        #
        # 예:
        # melon=10, genie=None, bugs=3 이면 min 값은 3
        # => 더 상위권 곡이 먼저 오게 됨
        def get_best_rank(item):
            ranks = [
                item["melon_rank"],
                item["genie_rank"],
                item["bugs_rank"],
            ]

            # None 값 제거
            valid_ranks = [rank for rank in ranks if rank is not None]

            # 모든 rank가 None인 경우는 맨 뒤로 보내기 위해 큰 값 반환
            if not valid_ranks:
                return 999999

            return min(valid_ranks)

        results.sort(key=get_best_rank)

        # 비교 결과 반환
        return {
            "keyword": keyword,
            "count": len(results),
            "items": results,
        }

    # 비교 API에서도 예상 못한 에러는 500으로 감싸서 반환
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"비교 조회 실패: {str(e)}")
