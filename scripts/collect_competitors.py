"""
일요일 09:00 KST — 경쟁 채널 최신 영상 수집 → 노션 저장
"""
import os
import json
import subprocess
import requests
from datetime import datetime

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
NOTION_DB_ID = os.environ["NOTION_DATABASE_ID"]  # 경쟁 채널 분석 DB

CHANNELS = [
    "@stockingssam",
    "@jamtoori",
    "@MickeyPedia",
    "@wsaj",
    "@sosumonkey",
]

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


def fetch_channel_videos(handle: str, count: int = 5) -> list[dict]:
    result = subprocess.run(
        [
            "yt-dlp",
            "--flat-playlist",
            f"--playlist-end={count}",
            "--print", "%(view_count)s\t%(title)s\t%(webpage_url)s\t%(upload_date)s",
            f"https://www.youtube.com/{handle}/videos",
        ],
        capture_output=True,
        text=True,
    )
    videos = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("\t", 3)
        if len(parts) == 4:
            views_raw, title, url, date = parts
            try:
                views = int(views_raw)
            except ValueError:
                views = 0
            videos.append({"title": title, "views": views, "url": url, "date": date})
    return videos


def save_to_notion(channel: str, videos: list[dict]):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    for v in videos:
        body = {
            "parent": {"database_id": NOTION_DB_ID},
            "properties": {
                "채널": {"title": [{"text": {"content": channel}}]},
                "제목": {"rich_text": [{"text": {"content": v["title"][:200]}}]},
                "조회수": {"number": v["views"]},
                "URL": {"url": v["url"]},
                "수집일": {"date": {"start": today}},
            },
        }
        resp = requests.post(
            "https://api.notion.com/v1/pages",
            headers=NOTION_HEADERS,
            json=body,
        )
        if resp.status_code != 200:
            print(f"  ⚠️  노션 저장 실패: {resp.text[:200]}")


def save_collection_json(data: dict):
    """월요일 작업이 참조할 수 있도록 JSON도 저장"""
    path = os.path.join(os.path.dirname(__file__), "..", "latest_collection.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    all_data = {}
    for handle in CHANNELS:
        print(f"수집 중: {handle}")
        videos = fetch_channel_videos(handle)
        save_to_notion(handle, videos)
        all_data[handle] = videos
        print(f"  → {len(videos)}개 저장 완료")

    save_collection_json(all_data)
    print("\n✅ 경쟁 채널 수집 완료 — 노션 + latest_collection.json 저장됨")


if __name__ == "__main__":
    main()
