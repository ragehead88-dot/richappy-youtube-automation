$envFile = Join-Path $PSScriptRoot ".env"
$envVars = @{}
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') { $envVars[$matches[1].Trim()] = $matches[2].Trim() }
}
$NOTION_TOKEN = $envVars["NOTION_TOKEN"]
$NOTION_PROPOSAL_DB = $envVars["NOTION_PROPOSAL_DB_ID"]

$notionHeaders = @{
    "Authorization"  = "Bearer $NOTION_TOKEN"
    "Notion-Version" = "2022-06-28"
    "Content-Type"   = "application/json; charset=utf-8"
}

$proposals = Get-Content -Raw -Encoding UTF8 (Join-Path $PSScriptRoot "proposals_this_week.json") | ConvertFrom-Json
$today = (Get-Date).ToString("yyyy-MM-dd")

foreach ($p in $proposals) {
    $bodyObj = @{
        parent     = @{ database_id = $NOTION_PROPOSAL_DB }
        properties = @{
            "제목 제안"        = @{ title = @(@{ text = @{ content = $p.title } }) }
            "썸네일 메인카피"   = @{ rich_text = @(@{ text = @{ content = $p.mainCopy } }) }
            "상단 라벨 워딩"    = @{ rich_text = @(@{ text = @{ content = $p.label } }) }
            "디자인 컨셉"       = @{ rich_text = @(@{ text = @{ content = $p.design } }) }
            "참고 경쟁 콘텐츠"  = @{ rich_text = @(@{ text = @{ content = $p.ref } }) }
            "주차"              = @{ date = @{ start = $today } }
            "상태"              = @{ select = @{ name = "대기" } }
        }
    }
    $bodyJson = $bodyObj | ConvertTo-Json -Depth 10
    $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($bodyJson)
    Invoke-RestMethod -Uri "https://api.notion.com/v1/pages" -Method Post -Headers $notionHeaders -Body $bodyBytes | Out-Null
    Write-Host "저장됨: $($p.title)"
}

