from datetime import datetime

from app.services.melon import fetch_melon_chart_and_save
from app.services.genie import fetch_genie_chart_and_save
from app.services.bugs import fetch_bugs_chart_and_save


def log(message: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {message}", flush=True)


def run_all():
    log("차트 수집 시작")

    try:
        fetch_melon_chart_and_save()
        log("멜론 저장 완료")

        fetch_genie_chart_and_save()
        log("지니 저장 완료")

        fetch_bugs_chart_and_save()
        log("벅스 저장 완료")

        log("차트 수집 완료")

    except Exception as e:
        log(f"에러 발생: {e}")
        raise


if __name__ == "__main__":
    run_all()