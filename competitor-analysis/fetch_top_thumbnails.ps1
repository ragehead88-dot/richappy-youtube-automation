$envFile = Join-Path $PSScriptRoot ".env"
$envVars = @{}
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') { $envVars[$matches[1].Trim()] = $matches[2].Trim() }
}
$YT_KEY = $envVars["YOUTUBE_API_KEY"]

$handles = @("jamtoori", "MickeyPedia", "3protv")
$thumbDir = Join-Path $PSScriptRoot "thumbnails"
New-Item -ItemType Directory -Force -Path $thumbDir | Out-Null

foreach ($handle in $handles) {
    $channelUrl = "https://www.googleapis.com/youtube/v3/channels?part=contentDetails&forHandle=@$handle&key=$YT_KEY"
    $channelResp = Invoke-RestMethod -Uri $channelUrl -Method Get
    $uploadsPlaylistId = $channelResp.items[0].contentDetails.relatedPlaylists.uploads

    $videosUrl = "https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&maxResults=5&playlistId=$uploadsPlaylistId&key=$YT_KEY"
    $videosResp = Invoke-RestMethod -Uri $videosUrl -Method Get

    $ids = ($videosResp.items | ForEach-Object { $_.snippet.resourceId.videoId }) -join ","
    $statsResp = Invoke-RestMethod -Uri "https://www.googleapis.com/youtube/v3/videos?part=statistics&id=$ids&key=$YT_KEY" -Method Get
    $statsMap = @{}
    foreach ($s in $statsResp.items) { $statsMap[$s.id] = [int]$s.statistics.viewCount }

    foreach ($item in $videosResp.items) {
        $vid = $item.snippet.resourceId.videoId
        $views = $statsMap[$vid]
        $thumbUrl = $item.snippet.thumbnails.high.url
        $fileName = "$handle`_$vid.jpg"
        Invoke-WebRequest -Uri $thumbUrl -OutFile (Join-Path $thumbDir $fileName)
        Write-Host "$handle | $views 회 | $($item.snippet.title) -> $fileName"
    }
}

