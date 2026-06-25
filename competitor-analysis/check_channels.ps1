# check_channels.ps1
# 고정 채널 대신 키워드 검색으로 이번 주 잘 된 콘텐츠를 동적 발굴

$envFile = Join-Path $PSScriptRoot ".env"
$envVars = @{}
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') {
        $envVars[$matches[1].Trim()] = $matches[2].Trim()
    }
}
$YT_KEY        = $envVars["YOUTUBE_API_KEY"]
$NOTION_TOKEN  = $envVars["NOTION_TOKEN"]
$NOTION_DB     = $envVars["NOTION_DATABASE_ID"]

$notionHeaders = @{
    "Authorization"  = "Bearer $NOTION_TOKEN"
    "Notion-Version" = "2022-06-28"
    "Content-Type"   = "application/json; charset=utf-8"
}

# ── 리채피 채널 관련 검색 키워드 (매주 이 키워드로 상위 콘텐츠 발굴) ──
$keywords = @(
    "주식투자 방법",
    "ETF 배당주 추천",
    "행동경제학 투자심리",
    "부자 되는 법 재테크",
    "주식 초보 공부"
)

$MAX_RESULTS_PER_KEYWORD = 8   # 키워드당 검색 결과 수
$MAX_VIDEOS_PER_CHANNEL  = 3   # 채널당 최신 영상 수

$allVideosCollected = @()
$seenChannelIds     = @{}   # 채널 중복 방지
$discoveredChannels = @()   # 발굴된 채널 목록

Write-Host "=== 키워드 검색으로 이번 주 상위 채널 발굴 ==="

foreach ($keyword in $keywords) {
    Write-Host "`n[키워드] $keyword"

    $searchUrl = "https://www.googleapis.com/youtube/v3/search" +
        "?part=snippet&type=video&q=" + [Uri]::EscapeDataString($keyword) +
        "&order=viewCount&regionCode=KR&relevanceLanguage=ko" +
        "&maxResults=$MAX_RESULTS_PER_KEYWORD&key=$YT_KEY"

    try {
        $searchResp = Invoke-RestMethod -Uri $searchUrl -Method Get
    } catch {
        Write-Host "  검색 실패: $_"
        continue
    }

    foreach ($item in $searchResp.items) {
        $channelId   = $item.snippet.channelId
        $channelName = $item.snippet.channelTitle
        $videoId     = $item.id.videoId
        $videoTitle  = $item.snippet.title

        if ($seenChannelIds.ContainsKey($channelId)) { continue }
        $seenChannelIds[$channelId] = $true

        $discoveredChannels += [PSCustomObject]@{
            channelId   = $channelId
            channelName = $channelName
            foundBy     = $keyword
        }
        Write-Host "  발굴: $channelName (키워드: $keyword)"
    }
}

Write-Host "`n=== 발굴된 채널 $($discoveredChannels.Count)개 최신 영상 수집 ==="

foreach ($ch in $discoveredChannels) {
    Write-Host "`n채널: $($ch.channelName)"

    # 채널의 uploads 플레이리스트 ID 조회
    $chUrl = "https://www.googleapis.com/youtube/v3/channels" +
        "?part=contentDetails,statistics&id=$($ch.channelId)&key=$YT_KEY"
    try {
        $chResp = Invoke-RestMethod -Uri $chUrl -Method Get
    } catch { continue }
    if (-not $chResp.items -or $chResp.items.Count -eq 0) { continue }

    $uploadsId    = $chResp.items[0].contentDetails.relatedPlaylists.uploads
    $subscriberCount = $chResp.items[0].statistics.subscriberCount

    # 최신 영상 목록
    $plUrl = "https://www.googleapis.com/youtube/v3/playlistItems" +
        "?part=snippet&maxResults=$MAX_VIDEOS_PER_CHANNEL&playlistId=$uploadsId&key=$YT_KEY"
    try {
        $plResp = Invoke-RestMethod -Uri $plUrl -Method Get
    } catch { continue }

    if (-not $plResp.items -or $plResp.items.Count -eq 0) { continue }

    $videoIds = ($plResp.items | ForEach-Object { $_.snippet.resourceId.videoId }) -join ","
    $statsResp = Invoke-RestMethod -Uri "https://www.googleapis.com/youtube/v3/videos?part=statistics&id=$videoIds&key=$YT_KEY" -Method Get
    $statsMap  = @{}
    foreach ($s in $statsResp.items) { $statsMap[$s.id] = [long]$s.statistics.viewCount }

    $today = (Get-Date).ToString("yyyy-MM-dd")

    foreach ($item in $plResp.items) {
        $videoTitle   = $item.snippet.title
        $videoId      = $item.snippet.resourceId.videoId
        $publishedAt  = $item.snippet.publishedAt
        $viewCount    = $statsMap[$videoId]
        $publishedDate = ([datetime]$publishedAt).ToString("yyyy-MM-dd")

        Write-Host "  - [$viewCount 회] $videoTitle"

        # Notion 저장
        $bodyObj = @{
            parent     = @{ database_id = $NOTION_DB }
            properties = @{
                "영상 제목"  = @{ title      = @(@{ text = @{ content = $videoTitle } }) }
                "채널명"     = @{ rich_text  = @(@{ text = @{ content = $ch.channelName } }) }
                "조회수"     = @{ number     = $viewCount }
                "업로드일"   = @{ date       = @{ start = $publishedDate } }
                "수집일"     = @{ date       = @{ start = $today } }
            }
        }
        $bodyJson  = $bodyObj | ConvertTo-Json -Depth 10
        $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($bodyJson)
        Invoke-RestMethod -Uri "https://api.notion.com/v1/pages" -Method Post -Headers $notionHeaders -Body $bodyBytes | Out-Null

        $allVideosCollected += [PSCustomObject]@{
            channel      = $ch.channelName
            channelId    = $ch.channelId
            foundByKeyword = $ch.foundBy
            title        = $videoTitle
            videoId      = $videoId
            views        = $viewCount
            published    = $publishedDate
        }
    }
}

# 조회수 기준 정렬해서 저장 (제안 생성 시 상위 콘텐츠 우선 참고)
$allVideosCollected = $allVideosCollected | Sort-Object views -Descending

$allVideosCollected | ConvertTo-Json -Depth 5 |
    Out-File -FilePath (Join-Path $PSScriptRoot "latest_collection.json") -Encoding UTF8

Write-Host "`n총 $($allVideosCollected.Count)개 영상 수집 완료 (조회수 순 정렬)"
Write-Host "발굴 채널: $($discoveredChannels.Count)개"
Write-Host "latest_collection.json 저장됨"
