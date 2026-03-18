from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.charts import router as charts_router

# FastAPI 앱 생성
app = FastAPI(title="Music Chart API")


# CORS 설정
# ---------------------------------------------------------
# 프론트(React)와 백엔드(FastAPI)의 주소가 다를 때
# 브라우저에서 요청을 막지 않도록 허용하는 설정입니다.
#
# 개발 단계에서는 모든 출처(*) 허용으로 두는 편이 편합니다.
# 나중에 배포할 때는 실제 프론트 주소만 허용하는 게 좋습니다.
# ---------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# charts 관련 router 등록
app.include_router(charts_router)


@app.get("/")
def read_root():
    """
    서버가 살아있는지 확인하는 기본 주소
    """
    return {"message": "Music Chart API is running"}