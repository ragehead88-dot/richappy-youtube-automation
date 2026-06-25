$envFile = Join-Path $PSScriptRoot ".env"
$envVars = @{}
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') {
        $envVars[$matches[1].Trim()] = $matches[2].Trim()
    }
}
$YT_KEY = $envVars["YOUTUBE_API_KEY"]

$handle = "richappy_youtube"

$channelUrl = "https://www.googleapis.com/youtube/v3/channels?part=snippet,contentDetails,statistics&forHandle=@$handle&key=$YT_KEY"
$channelResp = Invoke-RestMethod -Uri $channelUrl -Method Get

if (-not $channelResp.items -or $channelResp.items.Count -eq 0) {
    Write-Host "채널을 찾을 수 없음: @$handle"
    exit
}

$channelName = $channelResp.items[0].snippet.title
$channelDesc = $channelResp.items[0].snippet.description
$uploadsPlaylistId = $channelResp.items[0].contentDetails.relatedPlaylists.uploads
$subCount = $channelResp.items[0].statistics.subscriberCount

Write-Host "채널명: $channelName / 구독자: $subCount"

$allVideos = @()
$pageToken = ""
do {
    $url = "https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&maxResults=50&playlistId=$uploadsPlaylistId&key=$YT_KEY"
    if ($pageToken -ne "") { $url += "&pageToken=$pageToken" }
    $resp = Invoke-RestMethod -Uri $url -Method Get

    $ids = ($resp.items | ForEach-Object { $_.snippet.resourceId.videoId }) -join ","
    $statsResp = Invoke-RestMethod -Uri "https://www.googleapis.com/youtube/v3/videos?part=statistics,snippet&id=$ids&key=$YT_KEY" -Method Get
    $statsMap = @{}
    foreach ($s in $statsResp.items) { $statsMap[$s.id] = $s }

    foreach ($item in $resp.items) {
        $vid = $item.snippet.resourceId.videoId
        $stat = $statsMap[$vid]
        $allVideos += [PSCustomObject]@{
            title       = $item.snippet.title
            videoId     = $vid
            published   = $item.snippet.publishedAt
            views       = if ($stat) { [int]$stat.statistics.viewCount } else { 0 }
            description = $item.snippet.description
            thumbnail   = $item.snippet.thumbnails.high.url
        }
    }
    $pageToken = $resp.nextPageToken
} while ($pageToken)

Write-Host "총 $($allVideos.Count)개 영상 수집"

$output = [PSCustomObject]@{
    channelName = $channelName
    channelDesc = $channelDesc
    subCount    = $subCount
    videos      = $allVideos
}
$output | ConvertTo-Json -Depth 6 | Out-File -FilePath (Join-Path $PSScriptRoot "my_channel_data.json") -Encoding UTF8
Write-Host "my_channel_data.json 저장 완료"

