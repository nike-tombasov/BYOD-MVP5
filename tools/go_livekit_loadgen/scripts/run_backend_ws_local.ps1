param(
  [int]$Listeners = 10,
  [int]$RampPerSec = 5,
  [int]$HoldSec = 60,
  [string]$RunnerId = "win-dev-1",
  [string]$LoadgenKey = "byod_loadgen_key_01",
  [string]$OutDir = "./out"
)

go run ./cmd/byod-loadgen `
  -profile local-direct `
  -mode backend-ws-only `
  -server http://127.0.0.1:8000 `
  -listeners $Listeners `
  -ramp-per-sec $RampPerSec `
  -hold-sec $HoldSec `
  -runner-id $RunnerId `
  -loadgen-key $LoadgenKey `
  -out-dir $OutDir
