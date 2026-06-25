"""
월요일 09:00 KST — 일요일 데이터 이어받아 주간 기획안 3개 생성 → 노션 저장
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


def get_week_page_id() -> str:
    """일요일이 만든 노션 트래커 페이지 찾기"""
    meta_path = os.path.join(os.path.dirname(__file__), "..", "week_meta.json")
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            return json.load(f)["week_page_id"]

    # fallback: 노션 API로 이번 주 페이지 검색
    monday = (datetime.utcnow() - timedelta(days=datetime.utcnow().weekday())).strftime("%Y-%m-%d")
    body = {"filter": {"property": "날짜", "date": {"on_or_after": monday}}}
    resp = requests.post(
        f"https://api.notion.com/v1/databases/{TRACKER_DB_ID}/query",
        headers=NOTION_HEADERS,
        json=body,
    )
    results = resp.json().get("results", [])
    if results:
        return results[0]["id"]

    # 그래도 없으면 새로 생성
    today = datetime.utcnow().strftime("%Y-%m-%d")
    week_num = datetime.utcnow().isocalendar()[1]
    create_body = {
        "parent": {"database_id": TRACKER_DB_ID},
        "properties": {
            "이름": {"title": [{"text": {"content": f"W{week_num} {today}"}}]},
            "날짜": {"date": {"start": today}},
            "상태": {"select": {"name": "🟡 제안 선택 대기"}},
        },
    }
    create_resp = requests.post(
        "https://api.notion.com/v1/pages", headers=NOTION_HEADERS, json=create_body
    )
    return create_resp.json()["id"]


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


def load_competitor_data() -> str:
    path = os.path.join(os.path.dirname(__file__), "..", "latest_collection.json")
    if not os.path.exists(path):
        return "경쟁 채널 데이터 없음 (일요일 수집 스킵됨)"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    summary = ""
    for ch, videos in data.items():
        summary += f"\n{ch}:\n"
        for v in videos[:3]:
            summary += f"  - {v['title']} ({v['views']:,}회)\n"
    return summary


def generate_plan(competitor_summary: str, existing_titles: list[str]) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=5000,
        messages=[
            {
                "role": "user",
                "content": f"""당신은 리채피(richappy_youtube) 유튜브 채널의 주간 콘텐츠 기획자입니다.

## 채널 브랜드
- 미션: "돈으로 자유를 얻고, 그 자유로 행복하게 사는 법을 함께 배운다"
- 슬로건: "여러분은 반드시 행복한 부자가 됩니다"
- 콘텐츠 5축: ①거장 큐레이션 ②역사·사이클 ③투자 심리·잠재의식 ④실패와 성찰 ⑤행복한 부자의 삶
- 금지: 종목 추천, 공포 마케팅, 추상어 단독

## 검증된 흥행 공식
- 초유명 인물+숫자: 2~14배 (켄 피셔 16,373회 / 버핏+하워드 막스 8,196회)
- "90%가 모름 + 3가지": 최대 7.7배
- 올인원/총정리: 최대 9.2배
- 폭로·고백 포맷: 경쟁 채널 공백

## 경쟁 채널이 다루지 않는 리채피 선점 공백
- 투자 심리·행동경제학 심층
- "돈 + 행복" 연결 철학
- 투자 실패 고백·회복 스토리
- 장기투자자 멘탈 관리
- 투자 전문 도서 리뷰
- 저자 관점의 투자 철학

## 기존 영상 (중복 금지)
{chr(10).join(existing_titles[:30])}

## 이번 주 경쟁 채널 트렌드
{competitor_summary}

---

위 정보를 바탕으로 이번 주 리채피 채널 **영상 기획안 3개**를 작성해주세요.

각 기획안 형식:
**[번호]. [콘텐츠 축]**
- 제목 후보 A: ...
- 제목 후보 B: ...
- 선점 각도: (경쟁 채널이 왜 못 다루는지)
- 영상 흐름: 1) → 2) → 3) → 4) → 5)
- 적용 공식: ... / 예상 배율: ...x

마지막에:
⭐ **이번 주 최우선 추천**: [번호] — [이유 한 줄]""",
            }
        ],
    )
    return message.content[0].text


def save_plan_to_notion(week_page_id: str, content: str):
    lines = content.split("\n")
    children = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "🗓️ 이번 주 기획안 3개"}}]
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
            "title": {"title": [{"text": {"content": "🗓️ 주간 기획안 3개 방향"}}]}
        },
        "children": children[:100],
    }
    resp = requests.post("https://api.notion.com/v1/pages", headers=NOTION_HEADERS, json=body)
    return resp.json().get("url", "")


def main():
    print("이번 주 노션 트래커 페이지 연결 중...")
    week_page_id = get_week_page_id()
    print(f"  → {week_page_id}")

    print("리채피 기존 영상 조회...")
    existing_titles = get_my_channel_videos()

    print("경쟁 채널 데이터 로딩...")
    competitor_summary = load_competitor_data()

    print("Claude API로 기획안 3개 생성 중...")
    plan = generate_plan(competitor_summary, existing_titles)

    print("노션에 저장 중...")
    url = save_plan_to_notion(week_page_id, plan)

    print(f"\n✅ 주간 기획안 완료")
    print(f"   노션 페이지: {url}")
    print(plan)


if __name__ == "__main__":
    main()
