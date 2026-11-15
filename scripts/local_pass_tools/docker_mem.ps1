# Memory under load inside a Linux container with a memory limit.
#   docker_mem.ps1 -Root <entry root> -Out <folder for the logs> [-Only a,b,c,d,e,f]
# Each run: start the image built from the entry's Dockerfile, wait for /api/health, run scripts/stress_check.py
# from the host against it, then ask Docker whether the kernel killed it.  Two CPUs are given to the container
# (cpuset), like a small host.  Containers are named slipday-mem-* and removed afterwards; port 8101.
param([string]$Root, [string]$Out, [string[]]$Only = @())
$py = Join-Path $Root ".venv\Scripts\python.exe"
$runs = @(
  @{ name = "a_240m_512mb_no_arena_limit"; mem = "512m"; env = @("SLIPDAY_SKIP_DEMS=ldem_80s_80m", "MALLOC_ARENA_MAX=", "SLIPDAY_ARENA_LIMIT=0") },
  @{ name = "b_240m_512mb_limit_set_in_code"; mem = "512m"; env = @("SLIPDAY_SKIP_DEMS=ldem_80s_80m", "MALLOC_ARENA_MAX=") },
  @{ name = "c_240m_512mb_env_variable"; mem = "512m"; env = @("SLIPDAY_SKIP_DEMS=ldem_80s_80m") },
  @{ name = "d_80m_1gb_env_variable"; mem = "1g"; env = @() },
  @{ name = "e_80m_512mb_env_variable"; mem = "512m"; env = @() },
  @{ name = "f_80m_768mb_env_variable"; mem = "768m"; env = @() }
)
foreach ($r in $runs) {
  if ($Only.Count -gt 0 -and ($Only -notcontains $r.name.Substring(0, 1))) { continue }
  $cn = "slipday-mem-" + $r.name.Substring(0, 1)
  $log = Join-Path $Out ("stress_" + $r.name + ".txt")
  docker rm -f $cn 2>$null | Out-Null
  $dargs = @("run", "-d", "--name", $cn, "-m", $r.mem, "--memory-swap", $r.mem, "--cpuset-cpus", "0,1", "-p", "127.0.0.1:8101:8000")
  foreach ($e in $r.env) { $dargs += @("-e", $e) }
  $dargs += "slipday-local:pass"
  "config: $($r.name)   docker " + ($dargs -join " ") | Set-Content $log
  "started " + (Get-Date -Format "HH:mm:ss") | Add-Content $log
  docker @dargs | Out-Null
  $up = $false
  foreach ($i in 1..120) { try { Invoke-RestMethod "http://127.0.0.1:8101/api/health" -TimeoutSec 2 | Out-Null; $up = $true; break } catch { Start-Sleep -Milliseconds 500 } }
  if ($up) { & $py -I (Join-Path $Root "scripts\stress_check.py") "http://127.0.0.1:8101" --docker $cn 2>&1 | Add-Content $log } else { "server did not come up" | Add-Content $log }
  $st = docker inspect $cn --format "running={{.State.Running}} oom_killed={{.State.OOMKilled}} exit_code={{.State.ExitCode}}" 2>&1
  "container state after the run: $st" | Add-Content $log
  "ended " + (Get-Date -Format "HH:mm:ss") | Add-Content $log
  docker rm -f $cn 2>$null | Out-Null
}
"all runs done " + (Get-Date -Format "HH:mm:ss")
