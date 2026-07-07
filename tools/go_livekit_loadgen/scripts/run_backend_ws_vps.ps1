param(
  [Parameter(Mandatory=$true)][string]$Server,
  [int]$Listeners = 500,
  [int]$RampPerSec = 50,
  [int]$HoldSec = 600,
  [string]$RunnerId = "win-home-1",
  [string]$LoadgenKey = "byod_loadgen_key_01",
  [string]$OutDir = "./out"
)

go run ./cmd/byod-loadgen `
  -profile vps-nginx `
  -mode backend-ws-only `
  -server $Server `
  -listeners $Listeners `
  -ramp-per-sec $RampPerSec `
  -hold-sec $HoldSec `
  -runner-id $RunnerId `
  -loadgen-key $LoadgenKey `
  -out-dir $OutDir
