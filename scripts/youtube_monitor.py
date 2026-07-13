import requests
import json
import os
from datetime import datetime

YOUTUBE_API_KEY = os.environ["YOUTUBE_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
NOTION_TOKEN = os.environ["NOTION_TOKEN"].strip()
NOTION_PARENT_PAGE_ID = "39cccc610ced8124ac62de7748b10151"
NOTION_DATABASE_ID = "34cd019660f94d3684a493d4244475db"

MY_CHANNEL_ID = "UCopbo8p9-a5XyT6k7o1zSwQ"
MY_CHANNEL_NAME = "리채피 richappy"
MY_CHANNEL_CONCEPT = "인문학으로 행복한 부자가 되는 방법 (투자 + 인문학 융합 채널)"

MONITOR_CHANNELS = [
    "@stockingssam", "@제이디부자연구소JDRich", "@GuruLab_Eric",
    "@sng_tv", "@CapitalSong", "@leesemusaTV", "@epicinvestment",
    "@wsaj", "@sosumonkey", "@김단테", "@CashMaker_",
    "@gwanghwamun", "@신동경TV",
]

BASE_URL = "https://www.googleapis.com/youtube/v3"
SEEN_FILE = "seen_videos.json"


def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)


def get_channel_id(handle):
    res = requests.get(f"{BASE_URL}/search", params={
        "key": YOUTUBE_API_KEY, "q": handle, "type": "channel",
        "part": "snippet", "maxResults": 1,
    }).json()
    items = res.get("items", [])
    if items:
        return items[0]["snippet"]["channelId"], items[0]["snippet"]["title"]
    return None, None


def get_latest_videos(channel_id, max_results=2):
    res = requests.get(f"{BASE_URL}/search", params={
        "key": YOUTUBE_API_KEY, "channelId": channel_id, "type": "video",
        "part": "snippet", "order": "date", "maxResults": max_results,
    }).json()
    return res.get("items", [])


def get_video_stats(video_id):
    res = requests.get(f"{BASE_URL}/videos", params={
        "key": YOUTUBE_API_KEY, "id": video_id, "part": "statistics,snippet",
    }).json()
    items = res.get("items", [])
    if items:
        s = items[0].get("statistics", {})
        sn = items[0].get("snippet", {})
        return {
            "views": int(s.get("viewCount", 0)),
            "likes": int(s.get("likeCount", 0)),
            "thumbnail": sn.get("thumbnails", {}).get("high", {}).get("url", ""),
        }
    return {}


def get_top_comments(video_id, max_results=2):
    try:
        res = requests.get(f"{BASE_URL}/commentThreads", params={
            "key": YOUTUBE_API_KEY, "videoId": video_id,
            "part": "snippet", "order": "relevance", "maxResults": max_results,
        }).json()
        return [
            item["snippet"]["topLevelComment"]["snippet"]["textDisplay"][:150]
            for item in res.get("items", [])
        ]
    except:
        return []


def get_my_channel_stats():
    res = requests.get(f"{BASE_URL}/channels", params={
        "key": YOUTUBE_API_KEY, "id": MY_CHANNEL_ID, "part": "statistics",
    }).json()
    s = res["items"][0]["statistics"]
    return {
        "subscribers": int(s.get("subscriberCount", 0)),
        "total_views": int(s.get("viewCount", 0)),
        "video_count": int(s.get("videoCount", 0)),
    }


def get_my_recent_videos(max_results=5):
    videos = get_latest_videos(MY_CHANNEL_ID, max_results)
    result = []
    for v in videos:
        vid = v["id"]["videoId"]
        stats = get_video_stats(vid)
        result.append({
            "title": v["snippet"]["title"],
            "published": v["snippet"]["publishedAt"][:10],
            "views": stats.get("views", 0),
            "likes": stats.get("likes", 0),
        })
    return result


def collect_monitored_channels(seen_ids):
    new_videos = []
    all_videos = []
    for handle in MONITOR_CHANNELS:
        channel_id, channel_name = get_channel_id(handle)
        if not channel_id:
            continue
        for v in get_latest_videos(channel_id):
            vid = v["id"]["videoId"]
            stats = get_video_stats(vid)
            data = {
                "channel": channel_name,
                "title": v["snippet"]["title"],
                "published": v["snippet"]["publishedAt"][:10],
                "url": f"https://www.youtube.com/watch?v={vid}",
                "views": stats.get("views", 0),
                "likes": stats.get("likes", 0),
                "comments": get_top_comments(vid),
            }
            all_videos.append(data)
            if vid not in seen_ids:
                new_videos.append(data)
                seen_ids.add(vid)
    return new_videos, all_videos, seen_ids


def analyze_with_claude(my_stats, my_recent, all_videos):
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    monitored_summary = "\n".join([
        f"- [{v['channel']}] {v['title']} | 조회수:{v['views']:,}"
        for v in sorted(all_videos, key=lambda x: x['views'], reverse=True)[:15]
    ])
    my_summary = "\n".join([
        f"- {v['title']} | 조회수:{v['views']:,} | 좋아요:{v['likes']:,}"
        for v in my_recent
    ])

    prompt = f"""당신은 리채피 유튜브 채널 전략 전문가입니다.

## 채널 정보
- 채널명: {MY_CHANNEL_NAME}
- 컨셉: {MY_CHANNEL_CONCEPT}
- 구독자: {my_stats['subscribers']:,}명
- 검증된 흥행 공식: ①유명인+숫자(켄피셔 16,373회) ②90%가모름+3가지 ③인문학+투자 심리 결합
- 피해야 할 패턴: 추상어 단독, 종목 추천, 인지도 낮은 인물

## 내 최근 영상 성과
{my_summary}

## 경쟁 채널 인기 영상 (조회수 순)
{monitored_summary}

---

아래 JSON 형식으로만 응답하세요. 다른 텍스트 없이 JSON만 출력하세요.

{{
  "트렌드키워드": "키워드1, 키워드2, 키워드3",
  "아이디어": [
    {{
      "제목1": "후킹되는 제목 버전1",
      "제목2": "후킹되는 제목 버전2",
      "썸네일": "1줄(작게): 텍스트 / 2줄(크게): 텍스트 / 3줄(강조): 텍스트",
      "핵심내용": "이 영상의 핵심 내용 1~2줄 요약"
    }},
    {{
      "제목1": "후킹되는 제목 버전1",
      "제목2": "후킹되는 제목 버전2",
      "썸네일": "1줄(작게): 텍스트 / 2줄(크게): 텍스트 / 3줄(강조): 텍스트",
      "핵심내용": "이 영상의 핵심 내용 1~2줄 요약"
    }},
    {{
      "제목1": "후킹되는 제목 버전1",
      "제목2": "후킹되는 제목 버전2",
      "썸네일": "1줄(작게): 텍스트 / 2줄(크게): 텍스트 / 3줄(강조): 텍스트",
      "핵심내용": "이 영상의 핵심 내용 1~2줄 요약"
    }}
  ],
  "성장조언": "채널 성장을 위한 핵심 조언 한 줄"
}}"""

    msg = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = msg.content[0].text.strip()
    # JSON 블록 추출
    if "```" in raw:
        raw = raw.split("```")[1].replace("json", "").strip()
    return json.loads(raw)


def save_to_notion(my_stats, my_recent, new_videos, all_videos, analysis):
    today = datetime.now()
    title = f"유튜브 채널 리포트 — {today.year}년 {today.month}월 {today.day}일"

    ideas = analysis.get("아이디어", [{}, {}, {}])
    trends = analysis.get("트렌드키워드", "")
    advice = analysis.get("성장조언", "")

    def idea_title(i, idx):
        t1 = i.get("제목1", "")
        t2 = i.get("제목2", "")
        return f"[제목A] {t1}\n[제목B] {t2}"[:1990] if idx < len(ideas) else ""

    def idea_thumb(i, idx):
        return i.get("썸네일", "")[:1990] if idx < len(ideas) else ""

    my_videos_table = "| 제목 | 조회수 | 좋아요 |\n|------|--------|--------|\n"
    for v in my_recent:
        my_videos_table += f"| {v['title']} | {v['views']:,} | {v['likes']:,} |\n"

    top5 = sorted(all_videos, key=lambda x: x['views'], reverse=True)[:5]
    top5_table = "| 채널 | 제목 | 조회수 |\n|------|------|--------|\n"
    for v in top5:
        top5_table += f"| {v['channel']} | {v['title'][:30]} | {v['views']:,} |\n"

    new_section = ""
    if new_videos:
        new_section = f"\n## 🆕 오늘 새로 올라온 영상 ({len(new_videos)}개)\n\n"
        for v in new_videos[:10]:
            new_section += f"- **[{v['channel']}]** [{v['title']}]({v['url']}) — 조회수 {v['views']:,}\n"

    idea_section = ""
    for idx, idea in enumerate(ideas[:3], 1):
        idea_section += f"""
### 아이디어 {idx}
- 제목A: {idea.get('제목1', '')}
- 제목B: {idea.get('제목2', '')}
- 썸네일: {idea.get('썸네일', '')}
- 핵심내용: {idea.get('핵심내용', '')}
"""

    content = f"""## 📊 내 채널 현황

| 항목 | 수치 |
|------|------|
| 구독자 | {my_stats['subscribers']:,}명 |
| 총 조회수 | {my_stats['total_views']:,} |
| 총 영상수 | {my_stats['video_count']}개 |

## 🎬 최근 내 영상 성과

{my_videos_table}
## 🔥 경쟁 채널 TOP 5 (조회수 기준)

{top5_table}{new_section}
## 💡 오늘의 트렌드 키워드
{trends}

## 🎯 다음 영상 아이디어 TOP 3
{idea_section}
## 📌 성장 조언
{advice}"""

    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    i1 = ideas[0] if len(ideas) > 0 else {}
    i2 = ideas[1] if len(ideas) > 1 else {}
    i3 = ideas[2] if len(ideas) > 2 else {}

    db_data = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "icon": {"type": "emoji", "emoji": "📊"},
        "properties": {
            "Name": {"title": [{"text": {"content": title}}]},
            "날짜": {"date": {"start": today.strftime("%Y-%m-%d")}},
            "구독자": {"number": my_stats["subscribers"]},
            "총조회수": {"number": my_stats["total_views"]},
            "신규영상수": {"number": len(new_videos)},
            "트렌드키워드": {"rich_text": [{"text": {"content": trends[:1990]}}]},
            "아이디어1_제목": {"rich_text": [{"text": {"content": idea_title(i1, 0)}}]},
            "아이디어1_썸네일": {"rich_text": [{"text": {"content": idea_thumb(i1, 0)}}]},
            "아이디어2_제목": {"rich_text": [{"text": {"content": idea_title(i2, 1)}}]},
            "아이디어2_썸네일": {"rich_text": [{"text": {"content": idea_thumb(i2, 1)}}]},
            "아이디어3_제목": {"rich_text": [{"text": {"content": idea_title(i3, 2)}}]},
            "아이디어3_썸네일": {"rich_text": [{"text": {"content": idea_thumb(i3, 2)}}]},
            "AI분석요약": {"rich_text": [{"text": {"content": advice[:1990]}}]},
        },
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": content[:1900]}}]
                }
            }
        ]
    }

    res = requests.post("https://api.notion.com/v1/pages", headers=headers, json=db_data)
    result = res.json()
    return result.get("url", "URL 없음")


def run():
    print("📊 내 채널 분석 중...")
    my_stats = get_my_channel_stats()

    print("🎬 최근 영상 수집 중...")
    my_recent = get_my_recent_videos(5)

    print("📡 모니터링 채널 수집 중...")
    seen_ids = load_seen()
    new_videos, all_videos, seen_ids = collect_monitored_channels(seen_ids)
    save_seen(seen_ids)
    print(f"  수집된 전체 영상: {len(all_videos)}개")
    print(f"  신규 영상: {len(new_videos)}개")
    for v in sorted(all_videos, key=lambda x: x['views'], reverse=True)[:5]:
        print(f"  [{v['channel']}] {v['title'][:40]} | 조회수: {v['views']:,}")

    print("🤖 Claude AI 분석 중...")
    analysis = analyze_with_claude(my_stats, my_recent, all_videos)

    print("📝 노션에 저장 중...")
    url = save_to_notion(my_stats, my_recent, new_videos, all_videos, analysis)
    print(f"✅ 완료! 노션 페이지: {url}")


if __name__ == "__main__":
    run()
