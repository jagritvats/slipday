# Container check for Slipday: build the image, run it under a memory limit, ask for the first screen and
# one cold request, and print the peak memory of the container's memory group.
#
# NOT RUN by its author.  Written on 15 Nov 2026 on a machine where Docker was not started; only its syntax
# was checked (the PowerShell parser).  No figure in the README comes from this script yet.  Read its first
# output with care.  It does the same as scripts/container_check.sh.
#
# One command, from anywhere:
#     .\scripts\container_check.ps1 [-Memory 1g] [-Port 8010] [-Grid80] [-Keep]
#         -Memory   memory limit in Docker's notation (default 1g; also try 768m, 512m, 2g)
#         -Port     port published on this machine (default 8010)
#         -Grid80   when data\dem\ldem_80s_80m_f32.npy is absent, pass --build-arg GRID80=1 so that the build
#                   downloads NASA's 80 m file (189 MB from pgda.gsfc.nasa.gov, sha256 checked, network
#                   needed).  Without it an image built from a folder that lacks the file runs on 240 m.
#         -Keep     leave the container running at the end (for scripts\stress_check.py)
#         -Image    image tag (default slipday-check)     -Name   container name (default slipday-check-<pid>)
#
# How the 80 m grid gets into the image (see the Dockerfile): "COPY . ." copies data/dem/ as it is, so a
# folder that has ldem_80s_80m_f32.npy gives an image that has it; .dockerignore does not exclude it.
#
# What it does: (a) docker build, (b) docker run with --memory, --memory-swap of the same size (no swap, so
# the limit is a hard one, as on a hosting plan) and --cpus 2, (c) waits for /api/health, (d) fetches the
# page, the stored opening card, the slip map for that date, one 3-D frame and one cold request (landing
# circles at a point no cache has seen), printing each status and time, (e) prints the peak of the memory
# group, whether the kernel killed the container for memory, and the image size, (f) stops and removes the
# container.  This is the least a host must survive, not a load test.  For load: -Keep, then
#     python scripts\stress_check.py http://127.0.0.1:PORT --docker NAME
# Memory is printed in bytes and in MiB (1 MiB = 1,048,576 bytes), the unit stress_check.py and the
# first-pass table in the README call "MB".
param(
    [string]$Memory = "1g",
    [int]$Port = 8010,
    [switch]$Grid80,
    [switch]$Keep,
    [string]$Image = "slipday-check",
    [string]$Name = "slipday-check-$PID"
)
$ProgressPreference = "SilentlyContinue"
$Base = "http://127.0.0.1:$Port"
$Landing = "2026-11-18T00:00:00Z"
$Root = Split-Path -Parent $PSScriptRoot
$Grid = Join-Path $Root "data\dem\ldem_80s_80m_f32.npy"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Write-Output "docker is not on the PATH"; exit 2 }
docker info *> $null
if ($LASTEXITCODE -ne 0) { Write-Output "the Docker engine is not running"; exit 2 }

Write-Output ("== build ({0}), folder {1}" -f (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"), $Root)
if (Test-Path $Grid) {
    Write-Output "80 m grid present ($Grid): the image will include it"
    docker build -t $Image $Root
} elseif ($Grid80) {
    Write-Output "80 m grid absent: building with --build-arg GRID80=1 (downloads 189 MB, sha256 checked)"
    docker build --build-arg GRID80=1 -t $Image $Root
} else {
    Write-Output "80 m grid absent and -Grid80 not given: THIS IMAGE RUNS ON THE 240 m GRID"
    docker build -t $Image $Root
}
if ($LASTEXITCODE -ne 0) { Write-Output "build failed"; exit 2 }

$script:Peak = $null          # last reading of the memory group's peak, in bytes
$script:PeakFrom = ""
$script:Fail = 0

function Test-Running {
    $r = docker inspect -f '{{.State.Running}}' $Name 2>$null
    return ("$r".Trim() -eq "true")
}

function Read-Peak {
    $v = docker exec $Name sh -c 'cat /sys/fs/cgroup/memory.peak 2>/dev/null' 2>$null
    if ("$v".Trim() -match '^\d+$') { $script:Peak = [long]"$v".Trim(); $script:PeakFrom = "cgroup v2 memory.peak"; return }
    $v = docker exec $Name sh -c 'cat /sys/fs/cgroup/memory/memory.max_usage_in_bytes 2>/dev/null' 2>$null
    if ("$v".Trim() -match '^\d+$') { $script:Peak = [long]"$v".Trim(); $script:PeakFrom = "cgroup v1 memory.max_usage_in_bytes" }
}

function Format-MiB([long]$Bytes) { return ("{0} MiB" -f [math]::Floor($Bytes / 1048576)) }

# One request: prints one line with the status and the time.
function Invoke-Check([string]$Label, [string]$Method, [string]$Path, [string]$Body = "", [int]$Limit = 300) {
    $code = 0
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        if ($Method -eq "POST") {
            $resp = Invoke-WebRequest -Uri ($Base + $Path) -Method Post -Body $Body -ContentType "application/json" -TimeoutSec $Limit -UseBasicParsing
        } else {
            $resp = Invoke-WebRequest -Uri ($Base + $Path) -TimeoutSec $Limit -UseBasicParsing
        }
        $code = [int]$resp.StatusCode
    } catch {
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode) { $code = [int]$_.Exception.Response.StatusCode }
    }
    $sw.Stop()
    Read-Peak
    $peakText = if ($null -ne $script:Peak) { Format-MiB $script:Peak } else { "not read" }
    Write-Output ("{0,-34} {1,-4} {2,-22} status {3}  {4:N2} s  group peak {5}" -f $Label, $Method, $Path, $code, $sw.Elapsed.TotalSeconds, $peakText)
    if ($code -ne 200) { $script:Fail = 1 }
}

Write-Output "== run: --memory $Memory --memory-swap $Memory --cpus 2, port $Port"
docker run -d --name $Name --memory $Memory --memory-swap $Memory --cpus 2 -p "${Port}:8000" $Image | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Output "docker run failed"; exit 2 }

try {
    Write-Output "== wait for /api/health (up to 180 s)"
    $ok = $false
    $health = $null
    $waited = [System.Diagnostics.Stopwatch]::StartNew()
    while ($waited.Elapsed.TotalSeconds -lt 180) {
        if (-not (Test-Running)) { Write-Output "the container stopped before it answered"; break }
        try {
            $health = Invoke-RestMethod -Uri "$Base/api/health" -TimeoutSec 5
            $ok = $true
            break
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    if ($ok) {
        Write-Output ("healthy after about {0:N0} s" -f $waited.Elapsed.TotalSeconds)
        Write-Output ("terrain label: {0}" -f $health.terrain.label)
        Write-Output ("malloc_arena_limit: {0}" -f $health.malloc_arena_limit)
    } else {
        $script:Fail = 1
        docker logs --tail 30 $Name 2>&1 | ForEach-Object { "$_" }
    }

    if ($ok) {
        Write-Output "== requests"
        $card = '{"site":{"id":"robust_pick"},"landing":"' + $Landing + '"}'
        Invoke-Check "page" "GET" "/"
        Invoke-Check "stored opening card" "POST" "/api/mission" $card
        Invoke-Check "slip map, 13-point re-check" "POST" "/api/robust-map" ('{"start":"' + $Landing + '","n_dates":60}') 900
        Invoke-Check "one 3-D frame" "GET" ("/api/terrain3d?site=robust_pick&at=" + $Landing) "" 600
        Invoke-Check "cold: landing circles, new point" "POST" "/api/landing-circles" ('{"site":{"lat":-86.4321,"lon":17.123},"landing":"' + $Landing + '"}') 1800
        Invoke-Check "stored opening card again" "POST" "/api/mission" $card
    }

    Write-Output "== memory"
    if (Test-Running) {
        Read-Peak
        if ($null -ne $script:Peak) {
            Write-Output ("peak of the container's memory group: {0} bytes = {1}  ({2}), limit {3}" -f $script:Peak, (Format-MiB $script:Peak), $script:PeakFrom, $Memory)
        } else {
            Write-Output "no cgroup peak file could be read; docker stats gives the usage NOW, not a peak:"
            docker stats --no-stream --format '{{.Name}}  {{.MemUsage}}  {{.MemPerc}}' $Name
        }
        docker exec $Name sh -c 'grep oom_kill /sys/fs/cgroup/memory.events 2>/dev/null' 2>$null
    } else {
        $script:Fail = 1
        if ($null -ne $script:Peak) {
            Write-Output ("the container is no longer running; last reading before it stopped: {0} bytes = {1}  ({2})" -f $script:Peak, (Format-MiB $script:Peak), $script:PeakFrom)
        } else {
            Write-Output "the container is no longer running and no peak was read"
        }
    }
    $oom = "$(docker inspect -f '{{.State.OOMKilled}}' $Name 2>$null)".Trim()
    $exitCode = "$(docker inspect -f '{{.State.ExitCode}}' $Name 2>$null)".Trim()
    if (-not $oom) { $oom = "unknown" }
    Write-Output "killed by the kernel for memory (State.OOMKilled): $oom; exit code $exitCode"
    if ($oom -eq "true") { $script:Fail = 1 }
    $size = "$(docker image inspect -f '{{.Size}}' $Image 2>$null)".Trim()
    if ($size -match '^\d+$') {
        Write-Output ("image {0}: {1} bytes = {2} MB" -f $Image, $size, [math]::Floor([long]$size / 1000000))
    }

    if ($script:Fail -eq 0) {
        Write-Output "== RESULT: every request answered 200 inside $Memory"
    } else {
        Write-Output "== RESULT: NOT CLEAN inside $Memory (a request did not answer 200, or the container stopped)"
    }
} finally {
    if ($Keep) {
        Write-Output "container $Name left running on $Base (-Keep); remove it with: docker rm -f $Name"
    } else {
        docker stop -t 5 $Name *> $null
        docker rm -f $Name *> $null
        Write-Output "container $Name stopped and removed"
    }
}
exit $script:Fail
