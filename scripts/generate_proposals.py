"""
일요일 10:00 KST — 경쟁 채널 데이터 기반 제목·썸네일 10개 제안 → 노션 저장
"""
import os
import json
import requests
import anthropic
from datetime import datetime, timedelta

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
TRACKER_DB_ID = os.environ["NOTION_TRACKER_DB_ID"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
YOUTUBE_API_KEY = os.environ["YOUTUBE_API_KEY"]

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

COPY_STRUCTURES = """
01. 숫자 한정형      예) "한국 ETF 3개로 평생 월급"
02. 지시대명사 은폐  예) "'이것' 알고나니 수익률이 달라졌다"
03. 내부자 폭로      예) "20년차 펀드매니저가 폭로하는 ETF의 함정"
04. Before→After     예) "월 50만 → 500만 배당 만든 방법"
05. 금기 경고        예) "'이것' 하면 평생 가난, 지금 당장 바꾸세요"
06. 비밀 공개        예) "부자들이 알리지 말라던 배당 레시피"
07. 통념 부정        예) "분산투자, 무작정 하지 마세요"
08. 직접 검증        예) "10년간 매달 ETF 샀더니 실제 결과"
09. 의외성 반전      예) "주식 안 해도 됩니다, 이게 더 쉬워요"
10. 소수 특권        예) "상위 1%만 아는 배당주 선별 기준 3가지"
11. 변신·되는 법     예) "겁쟁이 투자자도 멘탈 강해지는 법"
12. 대안 지시        예) "펀드 말고 '이거' 하세요"
13. 시간 즉효        예) "포트폴리오 리밸런싱 5분 만에 끝내는 법"
14. 눈높이 보장      예) "주린이도 이해하는 금리와 주가의 관계"
15. 질문·자문형      예) "나는 왜 주식하면 항상 손해일까?"
16. 기관 은폐        예) "증권사가 절대 말 안 하는 수수료의 진실"
17. 특징·징조        예) "행복한 부자들의 공통 투자 습관 5가지"
18. 후회 예방        예) "1억 날리고 후회하는 투자 실수 7가지"
19. vs 대결          예) "복리 vs 감정적 매매 — 10년 후 결과 비교"
20. 랭킹·TOP         예) "2026 지금 당장 사도 되는 배당주 TOP 5"
"""


def get_my_channel_videos() -> list[str]:
    url = (
        f"https://www.googleapis.com/youtube/v3/channels"
        f"?part=contentDetails&forHandle=richappy_youtube&key={YOUTUBE_API_KEY}"
    )
    ch = requests.get(url).json()
    uploads_id = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    pl_url = (
        f"https://www.googleapis.com/youtube/v3/playlistItems"
        f"?part=snippet&maxResults=50&playlistId={uploads_id}&key={YOUTUBE_API_KEY}"
    )
    pl = requests.get(pl_url).json()
    return [item["snippet"]["title"] for item in pl.get("items", [])]


def load_competitor_data() -> dict:
    path = os.path.join(os.path.dirname(__file__), "..", "latest_collection.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def create_week_page() -> str:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    week_num = datetime.utcnow().isocalendar()[1]
    week_label = f"W{week_num} {today}"
    body = {
        "parent": {"database_id": TRACKER_DB_ID},
        "properties": {
            "이름": {"title": [{"text": {"content": week_label}}]},
            "날짜": {"date": {"start": today}},
            "상태": {"select": {"name": "🟡 제안 선택 대기"}},
            "메모": {"rich_text": [{"text": {"content": "자동 생성"}}]},
        },
    }
    resp = requests.post("https://api.notion.com/v1/pages", headers=NOTION_HEADERS, json=body)
    return resp.json()["id"]


def generate_proposals(competitor_data: dict, existing_titles: list[str]) -> str:
    competitor_summary = ""
    for ch, videos in competitor_data.items():
        competitor_summary += f"\n{ch}:\n"
        for v in videos[:3]:
            competitor_summary += f"  - {v['title']} ({v['views']:,}회)\n"

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[
            {
                "role": "user",
                "content": f"""당신은 리채피(richappy_youtube) 유튜브 채널의 콘텐츠 기획자입니다.

## 리채피 채널 정체성
- 브랜드: "인문학으로 행복한 부자가 되는 방법"
- 주제: 투자 심리·철학·자기계발 (종목 추천 금지)
- 흥행 공식: 초유명 인물+숫자 (버핏, 켄 피셔, 피터 린치 등) → 2~14배 효과
- 선점 공백: 투자 심리, 돈+행복 철학, 실패 고백, 장기투자 멘탈, 투자 도서 리뷰

## 기존 영상 (중복 금지)
{chr(10).join(existing_titles[:30])}

## 이번 주 경쟁 채널 인기 영상
{competitor_summary}

## 20가지 카피 구조
{COPY_STRUCTURES}

위 정보를 바탕으로 리채피 채널용 영상 제목 10개를 제안해주세요.
각 제안마다:
(a) 카피 구조 번호+유형명
(b) 유튜브 영상 제목
(c) 썸네일 메인카피 (1-2줄)
(d) 상단 라벨 워딩
(e) 디자인 컨셉 (한 줄)
(f) 참고한 경쟁 채널 영상

형식: 번호. [카피구조] 제목 / 썸네일: ... / 라벨: ... / 디자인: ... / 참고: ...""",
            }
        ],
    )
    return message.content[0].text


def save_proposals_to_notion(week_page_id: str, content: str):
    lines = content.split("\n")
    children = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "📋 이번 주 제목·썸네일 제안 10개"}}]
            },
        }
    ]
    for line in lines:
        if line.strip():
            children.append(
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": line[:2000]}}]
                    },
                }
            )

    body = {
        "parent": {"page_id": week_page_id},
        "properties": {
            "title": {"title": [{"text": {"content": "📋 제목·썸네일 제안 10개"}}]}
        },
        "children": children[:100],
    }
    resp = requests.post("https://api.notion.com/v1/pages", headers=NOTION_HEADERS, json=body)
    return resp.json().get("url", "")


def main():
    print("경쟁 채널 데이터 로딩...")
    competitor_data = load_competitor_data()

    print("리채피 기존 영상 조회...")
    existing_titles = get_my_channel_videos()

    print("이번 주 노션 트래커 페이지 생성...")
    week_page_id = create_week_page()

    print("Claude API로 제안 10개 생성 중...")
    proposals = generate_proposals(competitor_data, existing_titles)

    print("노션에 저장 중...")
    url = save_proposals_to_notion(week_page_id, proposals)

    # 다음 작업(월요일)이 이어받을 수 있도록 week_page_id 저장
    meta_path = os.path.join(os.path.dirname(__file__), "..", "week_meta.json")
    with open(meta_path, "w") as f:
        json.dump({"week_page_id": week_page_id, "proposal_url": url}, f)

    print(f"\n✅ 제안 10개 완료")
    print(f"   노션 페이지: {url}")
    print(proposals)


if __name__ == "__main__":
    main()
