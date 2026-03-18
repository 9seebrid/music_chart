from app.services.melon import fetch_melon_chart_and_save
from app.services.genie import fetch_genie_chart_and_save
from app.services.bugs import fetch_bugs_chart_and_save


def run_all():
    print("차트 수집 시작")

    fetch_melon_chart_and_save()
    fetch_genie_chart_and_save()
    fetch_bugs_chart_and_save()

    print("차트 수집 완료")


if __name__ == "__main__":
    run_all()