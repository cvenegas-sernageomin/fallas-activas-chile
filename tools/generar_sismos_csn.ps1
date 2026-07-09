# Genera una instantanea estatica de sismos recientes del CSN en GeoJSON.
# CSN (sismologia.cl) NO tiene CORS, asi que el navegador no puede pedirlo en vivo:
# se genera este snapshot server-side y se sirve como archivo estatico, igual que
# la capa historica de Harvard. Reutiliza Get-SismosCSN de alertas-redes.
#
# Uso:  powershell -File tools/generar_sismos_csn.ps1
# Salida: data/sismos/csn_reciente.geojson (schema compatible con el visor).

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$sismosApi = Join-Path (Split-Path -Parent $repo) 'alertas-redes\src\SismosApi.ps1'

if (-not (Test-Path $sismosApi)) {
    throw "No se encontro $sismosApi (se espera el repo hermano alertas-redes con src/SismosApi.ps1)."
}
. $sismosApi

Write-Host "Scrapeando CSN (sismologia.cl) ..."
$sismos = @(Get-SismosCSN)
Write-Host ("  CSN devolvio {0} eventos" -f $sismos.Count)

# Filtrar a profundidad <= 30 km (pedido del usuario); descartar sin profundidad/coord.
$feats = @()
foreach ($s in $sismos) {
    if ($null -eq $s.Prof -or $null -eq $s.Lat -or $null -eq $s.Lon) { continue }
    if ($s.Prof -gt 30) { continue }
    $props = [ordered]@{
        mag   = $s.Mag
        prof  = $s.Prof
        fecha = $s.Fecha
        place = $s.Lugar
        url   = $s.Url
    }
    $feats += [ordered]@{
        type     = 'Feature'
        geometry = [ordered]@{ type = 'Point'; coordinates = @($s.Lon, $s.Lat, $s.Prof) }
        properties = $props
    }
}

$fc = [ordered]@{ type = 'FeatureCollection'; features = $feats }
$outDir = Join-Path $repo 'data\sismos'
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir -Force | Out-Null }
$out = Join-Path $outDir 'csn_reciente.geojson'

$json = $fc | ConvertTo-Json -Depth 6 -Compress
[System.IO.File]::WriteAllText($out, $json, (New-Object System.Text.UTF8Encoding $false))
Write-Host ("Escrito: {0} ({1} eventos <=30 km)" -f $out, $feats.Count)
