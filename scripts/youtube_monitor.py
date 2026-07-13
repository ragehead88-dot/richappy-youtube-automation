import requests
import json
import os
from datetime import datetime

YOUTUBE_API_KEY = os.environ["YOUTUBE_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
NOTION_TOKEN = os.environ["NOTION_TOKEN"].strip()
NOTION_PARENT_PAGE_ID = "39cccc610ced8124ac62de7748b10151"

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

    prompt = f"""당신은 유튜브 채널 전략 전문가입니다.

채널명: {MY_CHANNEL_NAME}
채널 컨셉: {MY_CHANNEL_CONCEPT}
구독자: {my_stats['subscribers']:,}명 | 총 조회수: {my_stats['total_views']:,}

내 최근 영상:
{my_summary}

경쟁 채널 인기 영상:
{monitored_summary}

다음을 분석해주세요:

### 1. 트렌드 분석
지금 뜨는 주제 3가지 (간략히)

### 2. 다음 영상 아이디어 TOP 3
리채피 컨셉(인문학+투자)에 맞게:
- 제목 2가지 버전
- 썸네일 텍스트 제안
- 핵심 내용 2줄

### 3. 채널 성장 한 줄 조언"""

    msg = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text


def save_to_notion(my_stats, my_recent, new_videos, all_videos, analysis):
    today = datetime.now()
    title = f"유튜브 채널 리포트 — {today.year}년 {today.month}월 {today.day}일"

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
## 🤖 AI 분석 및 아이디어 추천

{analysis}"""

    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    # 페이지 생성
    data = {
        "parent": {"page_id": NOTION_PARENT_PAGE_ID},
        "icon": {"type": "emoji", "emoji": "📊"},
        "properties": {
            "title": {"title": [{"text": {"content": title}}]}
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

    res = requests.post("https://api.notion.com/v1/pages", headers=headers, json=data)
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
    print(f"  신규 영상: {len(new_videos)}개")

    print("🤖 Claude AI 분석 중...")
    analysis = analyze_with_claude(my_stats, my_recent, all_videos)

    print("📝 노션에 저장 중...")
    url = save_to_notion(my_stats, my_recent, new_videos, all_videos, analysis)
    print(f"✅ 완료! 노션 페이지: {url}")


if __name__ == "__main__":
    run()
