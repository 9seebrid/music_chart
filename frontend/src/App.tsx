import { useEffect, useMemo, useState } from "react";
import "./App.css";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
} from "recharts";

/**
 * 사이트 이름 타입
 * 문자열 오타를 줄이기 위해 union type으로 고정합니다.
 */
type SiteType = "melon" | "genie" | "bugs";

/**
 * 순위 변동 상태 타입
 * 백엔드에서 내려주는 값과 맞춥니다.
 */
type RankStatus = "UP" | "DOWN" | "SAME" | "NEW";

/**
 * 차트 곡 1개에 대한 타입
 * 백엔드의 /api/charts 응답 items 안에 들어있는 각 노래 데이터 구조와 맞춥니다.
 *
 * 참고:
 * 사이트마다 이미지 key 이름이 다를 수도 있어서
 * album_image, image, thumbnail을 모두 optional로 열어둡니다.
 */
interface ChartItem {
  rank: number;
  title: string;
  artist: string;
  album_image?: string;
  image?: string;
  thumbnail?: string;
  collected_at?: string;

  rank_change?: number | null;
  rank_status?: RankStatus;
}

/**
 * 백엔드 전체 응답 타입
 * /api/charts?site=melon 호출 시 반환되는 JSON 구조와 맞춥니다.
 */
interface ChartResponse {
  site: string;
  count: number;
  items: ChartItem[];
}

/**
 * 비교 API 1개 결과 타입
 * /api/charts/compare 응답 items 안에 들어있는 데이터 구조와 맞춥니다.
 */
interface CompareItem {
  title: string;
  artist: string;
  thumbnail?: string;

  melon_rank: number | null;
  genie_rank: number | null;
  bugs_rank: number | null;

  melon_rank_change?: number | null;
  genie_rank_change?: number | null;
  bugs_rank_change?: number | null;

  melon_rank_status?: RankStatus;
  genie_rank_status?: RankStatus;
  bugs_rank_status?: RankStatus;
}

/**
 * 비교 API 전체 응답 타입
 */
interface CompareResponse {
  keyword: string;
  count: number;
  items: CompareItem[];
}

/**
 * 아티스트 비중 그래프 1칸 데이터 타입
 * name: 가수명
 * value: 해당 가수가 현재 차트에 몇 곡 들어와 있는지
 */
interface ArtistChartItem {
  name: string;
  value: number;
}

/**
 * 곡 카드에 표시할 이미지 주소를 안전하게 고르는 함수
 * 사이트별 JSON key 이름이 다를 수 있으므로 순서대로 확인합니다.
 */
function getSongImage(song: ChartItem): string {
  return song.album_image || song.image || song.thumbnail || "";
}

/**
 * 순위 변동 표시용 배지 컴포넌트
 *
 * 예:
 * UP   -> ▲2
 * DOWN -> ▼1
 * SAME -> -
 * NEW  -> NEW
 */
type RankChangeBadgeProps = {
  status?: RankStatus;
  change?: number | null;
};

function RankChangeBadge({ status, change }: RankChangeBadgeProps) {
  if (status === "UP") {
    return <span className="rank-change up">▲{change}</span>;
  }

  if (status === "DOWN") {
    return <span className="rank-change down">▼{Math.abs(change ?? 0)}</span>;
  }

  if (status === "SAME") {
    return <span className="rank-change same">-</span>;
  }

  if (status === "NEW") {
    return <span className="rank-change new">NEW</span>;
  }

  return null;
}

/**
 * 현재 사이트 차트에 표시할 곡 1개 컴포넌트
 * 같은 UI를 반복하므로 컴포넌트로 분리합니다.
 */
function SongItem({ song }: { song: ChartItem }) {
  const imageUrl = getSongImage(song);

  return (
    <div className="song-item">
      {/* 순위 */}
      <div className="song-rank">{song.rank}</div>

      {/* 앨범 이미지 */}
      <img className="song-image" src={imageUrl} alt={song.title} />

      {/* 곡 정보 */}
      <div className="song-info">
        <div className="song-title-row">
          <div className="song-title">{song.title}</div>
          <RankChangeBadge
            status={song.rank_status}
            change={song.rank_change}
          />
        </div>

        <div className="song-artist">{song.artist}</div>
      </div>
    </div>
  );
}

/**
 * 비교 결과 카드 컴포넌트
 * 한 곡이 멜론/지니/벅스에서 각각 몇 위인지 보여줍니다.
 */
function CompareCard({ item }: { item: CompareItem }) {
  return (
    <div className="compare-card">
      <img
        className="compare-image"
        src={item.thumbnail || ""}
        alt={item.title}
      />

      <div className="compare-info">
        <div className="song-title">{item.title}</div>
        <div className="song-artist">{item.artist}</div>

        <div className="compare-rank-row">
          <span className="compare-rank-pill melon-pill">
            멜론 {item.melon_rank ?? "-"}
          </span>
          <span className="compare-rank-pill genie-pill">
            지니 {item.genie_rank ?? "-"}
          </span>
          <span className="compare-rank-pill bugs-pill">
            벅스 {item.bugs_rank ?? "-"}
          </span>
        </div>
      </div>
    </div>
  );
}

/**
 * 현재 차트 기준 아티스트 비중 TOP5 그래프 컴포넌트
 *
 * data 예시:
 * [
 *   { name: "아이유", value: 4 },
 *   { name: "IVE (아이브)", value: 3 },
 * ]
 */
function ArtistChart({ data }: { data: ArtistChartItem[] }) {
  /**
   * 막대 색상 배열
   * 상위 5개 막대가 조금 더 보기 좋게 구분되도록 사용합니다.
   */
  const barColors = ["#6bdbf2d4", "#76a5ef", "#eb67b2", "#a47cef", "#efdf76"];

  return (
    <div className="artist-chart-card">
      <ResponsiveContainer width="100%" height={180}>
        <BarChart
          data={data}
          barCategoryGap="37%" // 막대 간격 크게
          barGap={4} // 막대 사이 간격
          margin={{ top: 10, right: 20, left: 0, bottom: 10 }}
        >
          {/* X축: 가수명 */}
          <XAxis dataKey="name" interval={0} tick={{ fontSize: 11 }} />

          {/* Y축: 곡 수 */}
          <YAxis allowDecimals={false} tick={{ fontSize: 10 }} />

          {/* 마우스를 올리면 상세값 표시 */}
          <Tooltip />

          {/* 막대 그래프 본체 */}
          <Bar dataKey="value" radius={[8, 8, 0, 0]}>
            {data.map((_, index) => (
              <Cell
                key={`cell-${index}`}
                fill={barColors[index % barColors.length]}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function App() {
  /**
   * 현재 선택된 사이트 상태
   * 처음에는 melon으로 시작합니다.
   */
  const [site, setSite] = useState<SiteType>("melon");

  /**
   * 실제 차트 데이터 전체를 저장할 상태
   * 처음에는 null(데이터 없음) 상태로 시작합니다.
   */
  const [chartData, setChartData] = useState<ChartResponse | null>(null);

  /**
   * 차트 로딩 상태
   */
  const [loading, setLoading] = useState(false);

  /**
   * 차트 에러 메시지 상태
   */
  const [error, setError] = useState("");

  /**
   * 현재 사이트 차트 내에서만 검색하는 검색어
   * 예: 곡 제목 / 가수명 필터링용
   */
  const [chartKeyword, setChartKeyword] = useState("");

  /**
   * 상위 몇 개까지 화면에 표시할지 결정하는 상태
   * 10 / 50 / 100 중 하나를 사용합니다.
   */
  const [visibleCount, setVisibleCount] = useState<number>(10);

  /**
   * 비교 검색창 입력값
   * 예: 아이유, love, 뉴진스
   */
  const [compareKeyword, setCompareKeyword] = useState("");

  /**
   * 비교 API 결과 데이터
   */
  const [compareData, setCompareData] = useState<CompareResponse | null>(null);

  /**
   * 비교 API 로딩 상태
   */
  const [compareLoading, setCompareLoading] = useState(false);

  /**
   * 비교 API 에러 메시지 상태
   */
  const [compareError, setCompareError] = useState("");

  /**
   * 차트 데이터를 불러오는 공통 함수
   * 현재 선택된 사이트를 기준으로 백엔드 API를 호출합니다.
   */
  const fetchChart = async (selectedSite: SiteType) => {
    try {
      setLoading(true);
      setError("");

      const response = await fetch(`/api/charts?site=${selectedSite}`);

      if (!response.ok) {
        throw new Error("차트 데이터를 불러오지 못했습니다.");
      }

      const data: ChartResponse = await response.json();
      setChartData(data);
    } catch (err) {
      console.error(err);
      setError("차트 조회 중 오류가 발생했습니다.");
      setChartData(null);
    } finally {
      setLoading(false);
    }
  };

  /**
   * 비교 API 호출 함수
   * 사용자가 입력한 compareKeyword를 이용해
   * /api/charts/compare API를 호출합니다.
   */
  const fetchCompare = async () => {
    try {
      setCompareLoading(true);
      setCompareError("");

      const response = await fetch(
        `/api/charts/compare?keyword=${encodeURIComponent(compareKeyword)}`,
      );

      if (!response.ok) {
        throw new Error("비교 데이터를 불러오지 못했습니다.");
      }

      const data: CompareResponse = await response.json();
      setCompareData(data);
    } catch (err) {
      console.error(err);
      setCompareError("비교 조회 중 오류가 발생했습니다.");
      setCompareData(null);
    } finally {
      setCompareLoading(false);
    }
  };

  /**
   * site 값이 바뀔 때마다 자동 조회
   * 탭을 바꿀 때마다 새로운 사이트의 차트를 다시 가져옵니다.
   */
  useEffect(() => {
    fetchChart(site);
  }, [site]);

  /**
   * 현재 사이트 차트 목록을
   * 1) chartKeyword로 필터링하고
   * 2) visibleCount만큼 잘라서
   * 최종적으로 화면에 보여줄 목록을 만듭니다.
   *
   * useMemo를 사용하면 불필요한 재계산을 줄일 수 있습니다.
   */
  const filteredChartItems = useMemo(() => {
    if (!chartData) return [];

    const normalizedKeyword = chartKeyword.trim().toLowerCase();

    const filtered = chartData.items.filter((song) => {
      if (!normalizedKeyword) return true;

      return (
        song.title.toLowerCase().includes(normalizedKeyword) ||
        song.artist.toLowerCase().includes(normalizedKeyword)
      );
    });

    // 검색어가 있으면 TOP10/50/100과 상관없이
    // 검색 결과 전체를 보여줍니다.
    if (normalizedKeyword) {
      return filtered;
    }

    // 검색어가 없을 때만 표시 개수 제한 적용
    return filtered.slice(0, visibleCount);
  }, [chartData, chartKeyword, visibleCount]);

  /**
   * 현재 차트 전체(chartData.items)를 기준으로
   * 가수별 곡 수를 세어서 그래프용 데이터로 변환합니다.
   *
   * 처리 순서:
   * 1. chartData가 없으면 빈 배열 반환
   * 2. artist 이름별로 곡 수 집계
   * 3. { name, value } 형태로 변환
   * 4. 곡 수가 많은 순으로 정렬
   * 5. 상위 5명만 잘라서 반환
   */
  const artistChartData = useMemo<ArtistChartItem[]>(() => {
    if (!chartData) return [];

    const countMap: Record<string, number> = {};

    chartData.items.forEach((item) => {
      const artist = item.artist;
      countMap[artist] = (countMap[artist] || 0) + 1;
    });

    return Object.entries(countMap)
      .map(([artist, count]) => ({
        name: artist,
        value: count,
      }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 5);
  }, [chartData]);

  return (
    <div className="app-container">
      {/* 페이지 제목 영역 */}
      <header className="page-header">
        <h1 className="page-title">🎵 음악 차트 비교 서비스</h1>
        <p className="page-description">
          FastAPI 백엔드에서 차트 데이터를 받아와 사이트별로 조회하고,
          곡명/가수명 기준으로 순위를 비교합니다.
        </p>
      </header>

      {/* 사이트 선택 탭 */}
      <div className="tab-group">
        <button
          className={`tab-button tab-melon ${site === "melon" ? "active" : ""}`}
          onClick={() => setSite("melon")}
        >
          멜론
        </button>

        <button
          className={`tab-button tab-genie ${site === "genie" ? "active" : ""}`}
          onClick={() => setSite("genie")}
        >
          지니
        </button>

        <button
          className={`tab-button tab-bugs ${site === "bugs" ? "active" : ""}`}
          onClick={() => setSite("bugs")}
        >
          벅스
        </button>
      </div>

      {/* 차트 검색 + TOP 필터 영역 */}
      <section className="control-card">
        <div className="control-row">
          <div className="control-group">
            <label className="control-label" htmlFor="chart-search">
              현재 차트 검색
            </label>
            <input
              id="chart-search"
              className="search-input"
              type="text"
              placeholder="곡명 또는 가수명을 입력하세요"
              value={chartKeyword}
              onChange={(e) => setChartKeyword(e.target.value)}
            />
          </div>

          <div className="control-group">
            <span className="control-label">표시 개수</span>

            <div className="count-filter-group">
              <button
                className={`count-button ${visibleCount === 10 ? "active" : ""}`}
                onClick={() => setVisibleCount(10)}
              >
                TOP10
              </button>

              <button
                className={`count-button ${visibleCount === 50 ? "active" : ""}`}
                onClick={() => setVisibleCount(50)}
              >
                TOP50
              </button>

              <button
                className={`count-button ${visibleCount === 100 ? "active" : ""}`}
                onClick={() => setVisibleCount(100)}
              >
                TOP100
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* 로딩 메시지 */}
      {loading && <div className="status-box loading">불러오는 중...</div>}

      {/* 에러 메시지 */}
      {error && <div className="status-box error">{error}</div>}

      {/* 데이터가 있을 때만 표시 */}
      {chartData && !loading && (
        <>
          {/* 상단 요약 영역 대신 현재 차트의 아티스트 비중 그래프 표시 */}
          <section className="chart-summary">
            <h2 className="section-title">아티스트 비중 TOP5</h2>
            <ArtistChart data={artistChartData} />
          </section>

          {/* 차트 리스트 */}
          <section className="chart-section">
            <h2 className="section-title">
              {site.toUpperCase()} 차트
              <span className="chart-count">
                {chartKeyword
                  ? ` - 검색 결과 ${filteredChartItems.length}곡`
                  : ` - ${filteredChartItems.length}곡`}
              </span>
            </h2>

            {/* 현재 차트 검색 결과가 있으면 리스트 표시, 없으면 안내 문구 표시 */}
            {filteredChartItems.length > 0 ? (
              <section className="chart-grid">
                {filteredChartItems.map((song) => (
                  <SongItem
                    key={`${song.rank}-${song.title}-${song.artist}`}
                    song={song}
                  />
                ))}
              </section>
            ) : (
              <div className="empty-box">현재 차트 검색 결과가 없습니다.</div>
            )}
          </section>
        </>
      )}

      {/* 비교 검색 영역 */}
      <section className="compare-section">
        <h2 className="section-title">사이트 통합 비교</h2>

        <div className="compare-search-row">
          <input
            className="search-input"
            type="text"
            placeholder="곡명 또는 가수명을 입력하세요. 예: 아이브"
            value={compareKeyword}
            onChange={(e) => setCompareKeyword(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                fetchCompare();
              }
            }}
          />

          <button className="compare-search-button" onClick={fetchCompare}>
            비교 검색
          </button>
        </div>

        {compareLoading && (
          <div className="status-box loading">비교 데이터를 불러오는 중...</div>
        )}

        {compareError && <div className="status-box error">{compareError}</div>}

        {compareData && !compareLoading && (
          <div className="compare-result-wrapper">
            <div className="compare-summary">
              <strong>검색어:</strong> {compareData.keyword || "(전체)"} /{" "}
              <strong>결과 수:</strong> {compareData.count}
            </div>

            {compareData.items.length > 0 ? (
              <div className="compare-list">
                {compareData.items.map((item, index) => (
                  <CompareCard
                    key={`${item.title}-${item.artist}-${index}`}
                    item={item}
                  />
                ))}
              </div>
            ) : (
              <div className="empty-box">검색 결과가 없습니다.</div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}

export default App;
