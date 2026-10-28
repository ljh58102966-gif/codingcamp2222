import re
from collections import Counter

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from wordcloud import WordCloud
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

st.set_page_config(
    page_title="유튜브 댓글 분석기",
    page_icon="📺",
    layout="wide"
)

st.title("📺 유튜브 댓글 분석기")
st.caption("영상과 채널의 댓글 및 조회수 데이터를 분석합니다.")

# -------------------------
# API 및 공통 함수
# -------------------------

@st.cache_resource
def youtube_client(api_key):
    return build(
        "youtube",
        "v3",
        developerKey=api_key,
        cache_discovery=False
    )


def extract_video_id(url):
    patterns = [
        r"(?:youtube\.com/watch\?v=)([\w-]{11})",
        r"(?:youtu\.be/)([\w-]{11})",
        r"(?:youtube\.com/shorts/)([\w-]{11})",
        r"(?:youtube\.com/embed/)([\w-]{11})",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    if re.fullmatch(r"[\w-]{11}", url.strip()):
        return url.strip()

    return None


def get_video_info(yt, video_id):
    result = yt.videos().list(
        part="snippet,statistics",
        id=video_id
    ).execute()

    if not result.get("items"):
        raise ValueError("영상을 찾을 수 없습니다.")

    return result["items"][0]


def get_comments(yt, video_id, max_pages=10):
    comments = []
    token = None

    for _ in range(max_pages):
        response = yt.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=100,
            order="relevance",
            pageToken=token,
            textFormat="plainText"
        ).execute()

        for item in response.get("items", []):
            snippet = item["snippet"]["topLevelComment"]["snippet"]

            comments.append({
                "작성자": snippet.get("authorDisplayName", ""),
                "댓글": snippet.get("textDisplay", ""),
                "좋아요": int(snippet.get("likeCount", 0)),
                "작성일": snippet.get("publishedAt", "")
            })

        token = response.get("nextPageToken")
        if not token:
            break

    return comments


def get_channel_id(yt, channel_input):
    value = channel_input.strip()

    # 채널 ID 직접 입력
    if value.startswith("UC") and len(value) == 24:
        return value

    # 채널 URL 또는 @핸들
    match = re.search(r"youtube\.com/@([^/?]+)", value)
    if match:
        result = yt.channels().list(
            part="id",
            forHandle=match.group(1)
        ).execute()

        if result.get("items"):
            return result["items"][0]["id"]

    # /channel/UC... 형태
    match = re.search(r"/channel/(UC[\w-]+)", value)
    if match:
        return match.group(1)

    raise ValueError(
        "채널 URL 또는 채널 ID를 확인해 주세요."
    )


def get_top_videos(yt, channel_id):
    response = yt.search().list(
        part="snippet",
        channelId=channel_id,
        type="video",
        order="viewCount",
        maxResults=3
    ).execute()

    video_ids = [
        item["id"]["videoId"]
        for item in response.get("items", [])
    ]

    if not video_ids:
        return []

    details = yt.videos().list(
        part="snippet,statistics",
        id=",".join(video_ids)
    ).execute()

    videos = details.get("items", [])
    videos.sort(
        key=lambda v: int(
            v.get("statistics", {}).get("viewCount", 0)
        ),
        reverse=True
    )

    return videos


def show_top_videos(videos):
    for rank, video in enumerate(videos, start=1):
        snippet = video["snippet"]
        stats = video.get("statistics", {})
        video_id = video["id"]

        st.markdown(f"### {rank}. {snippet['title']}")
        st.write(
            f"조회수: {int(stats.get('viewCount', 0)):,}"
        )
        st.markdown(
            f"[유튜브에서 영상 보기]"
            f"(https://www.youtube.com/watch?v={video_id})"
        )
        st.divider()


# -------------------------
# 사이드바
# -------------------------

st.sidebar.header("⚙️ 설정")

api_key = st.sidebar.text_input(
    "YouTube Data API 키",
    type="password",
    help="Google Cloud에서 발급한 API 키를 입력하세요."
)

st.sidebar.caption(
    "API 키를 GitHub 코드에 직접 적지 마세요."
)

if not api_key:
    st.info("왼쪽 사이드바에 YouTube API 키를 입력하세요.")
    st.stop()

try:
    yt = youtube_client(api_key)
except Exception as e:
    st.error(f"API 초기화 오류: {e}")
    st.stop()


# -------------------------
# 탭
# -------------------------

tab1, tab2, tab3, tab4 = st.tabs([
    "👍 최다 좋아요 댓글",
    "💼 직업 언급 TOP 3",
    "📊 채널 인기 영상 TOP 3",
    "☁️ 댓글 워드클라우드"
])

# -------------------------
# 탭 1: 최다 좋아요 댓글
# -------------------------

with tab1:
    st.subheader("좋아요를 가장 많이 받은 최상위 댓글")

    video_url = st.text_input(
        "유튜브 영상 URL 또는 영상 ID",
        key="like_video"
    )

    if st.button("최다 좋아요 댓글 분석", key="like_btn"):
        video_id = extract_video_id(video_url)

        if not video_id:
            st.error("올바른 유튜브 영상 URL을 입력하세요.")
        else:
            try:
                with st.spinner("댓글을 분석하는 중..."):
                    comments = get_comments(yt, video_id)

                if not comments:
                    st.warning(
                        "댓글이 없거나 댓글을 불러올 수 없습니다."
                    )
                else:
                    top = max(
                        comments,
                        key=lambda c: c["좋아요"]
                    )

                    st.success("분석 완료")
                    st.markdown("### 🏆 최다 좋아요 댓글")
                    st.write(top["댓글"])
                    st.metric("좋아요 수", f"{top['좋아요']:,}")
                    st.caption(f"작성자: {top['작성자']}")
                    st.caption(
                        f"분석한 최상위 댓글 수: {len(comments):,}"
                    )

            except HttpError as e:
                st.error(
                    "YouTube API 오류입니다. "
                    "API 할당량이나 댓글 사용 가능 여부를 확인하세요."
                )
            except Exception as e:
                st.error(f"오류: {e}")


# -------------------------
# 탭 2: 직업 언급 댓글 수 TOP 3
# -------------------------

with tab2:
    st.subheader("직업별 언급 댓글 수 TOP 3")

    job_video_url = st.text_input(
        "분석할 영상 URL 또는 ID",
        key="job_video"
    )

    # 필요에 따라 직업 키워드를 추가하거나 수정하세요.
    jobs = [
        "의사", "간호사", "변호사", "검사", "판사",
        "경찰", "소방관", "교사", "선생님", "학생",
        "배우", "가수", "유튜버", "개발자", "프로그래머",
        "기자", "작가", "요리사", "셰프", "군인",
        "공무원", "회사원", "아나운서", "회장", "사장",
        "알바", "배달원", "약사", "회계사", "변리사"
    ]

    if st.button("직업 언급 분석", key="job_btn"):
        video_id = extract_video_id(job_video_url)

        if not video_id:
            st.error("올바른 영상 URL을 입력하세요.")
        else:
            try:
                with st.spinner("직업 언급을 분석하는 중..."):
                    comments = get_comments(yt, video_id)

                counts = Counter()

                for item in comments:
                    comment = item["댓글"].lower()

                    # 댓글 한 개에서 같은 직업이 여러 번 나와도
                    # 해당 직업의 언급 댓글 수는 1개로 계산합니다.
                    for job in jobs:
                        if job.lower() in comment:
                            counts[job] += 1

                top3 = counts.most_common(3)

                if not top3:
                    st.warning(
                        "등록된 직업 키워드가 댓글에서 발견되지 않았습니다."
                    )
                else:
                    df = pd.DataFrame(
                        top3,
                        columns=["직업", "언급된 댓글 수"]
                    )
                    df.index = range(1, len(df) + 1)
                    df.index.name = "순위"
                    st.dataframe(
                        df,
                        use_container_width=True
                    )

                st.caption(
                    f"분석한 최상위 댓글 수: {len(comments):,}"
                )

            except HttpError:
                st.error(
                    "API 오류입니다. 댓글 사용 가능 여부와 "
                    "API 할당량을 확인하세요."
                )
            except Exception as e:
                st.error(f"오류: {e}")


# -------------------------
# 탭 3: 채널 조회수 TOP 3
# -------------------------

with tab3:
    st.subheader("채널의 조회수 TOP 3 영상")

    channel_url = st.text_input(
        "채널 URL 또는 채널 ID",
        placeholder="https://www.youtube.com/@채널핸들"
    )

    if st.button("인기 영상 찾기", key="channel_btn"):
        try:
            with st.spinner("채널 영상을 검색하는 중..."):
                channel_id = get_channel_id(yt, channel_url)
                videos = get_top_videos(yt, channel_id)

            if videos:
                show_top_videos(videos)
            else:
                st.warning("영상을 찾을 수 없습니다.")

        except HttpError:
            st.error(
                "API 오류입니다. 채널 정보와 API 할당량을 확인하세요."
            )
        except Exception as e:
            st.error(f"오류: {e}")


# -------------------------
# 탭 4: 댓글 워드클라우드
# -------------------------

with tab4:
    st.subheader("댓글 워드클라우드")

    cloud_video_url = st.text_input(
        "워드클라우드를 만들 영상 URL 또는 ID",
        key="cloud_video"
    )

    if st.button("워드클라우드 생성", key="cloud_btn"):
        video_id = extract_video_id(cloud_video_url)

        if not video_id:
            st.error("올바른 영상 URL을 입력하세요.")
        else:
            try:
                with st.spinner("워드클라우드를 만드는 중..."):
                    comments = get_comments(yt, video_id)

                text = " ".join(
                    item["댓글"] for item in comments
                )

                # 한글 불용어 및 자주 등장하는 일반 단어
                stopwords = {
                    "진짜", "정말", "너무", "그냥", "이거",
                    "저거", "이렇게", "저렇게", "그리고",
                    "근데", "에서", "으로", "하는", "했다",
                    "있는", "없는", "같은", "합니다", "입니다"
                }

                font_path = (
                    "/usr/share/fonts/truetype/nanum/"
                    "NanumGothic.ttf"
                )

                if not text.strip():
                    st.warning("워드클라우드를 만들 댓글이 없습니다.")
                else:
                    cloud = WordCloud(
                        font_path=font_path,
                        width=1200,
                        height=600,
                        background_color="white",
                        stopwords=stopwords,
                        collocations=False
                    ).generate(text)

                    fig, ax = plt.subplots(figsize=(14, 7))
                    ax.imshow(cloud, interpolation="bilinear")
                    ax.axis("off")
                    st.pyplot(fig)
                    plt.close(fig)

                    st.caption(
                        f"분석한 최상위 댓글 수: {len(comments):,}"
                    )

            except HttpError:
                st.error(
                    "API 오류입니다. 댓글 사용 가능 여부와 "
                    "API 할당량을 확인하세요."
                )
            except Exception as e:
                st.error(f"오류: {e}")
