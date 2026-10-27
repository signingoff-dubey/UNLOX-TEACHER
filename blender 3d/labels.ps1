# Render text labels to PNG masks (white text on black) with Windows text shaping, which handles Indic scripts
# correctly (conjuncts, vowel signs). Input: a JSON file [{"text": "...", "out": "C:\\...\\label.png"}].
# Output (stdout): JSON [{"out": ..., "width": px, "height": px}].
param([Parameter(Mandatory)][string]$Spec, [string]$Font = "Nirmala UI", [int]$Size = 56)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing, System.Windows.Forms
$items = Get-Content -Raw -Encoding UTF8 $Spec | ConvertFrom-Json
$typeface = [System.Drawing.Font]::new($Font,   # not $font: PowerShell names ignore case
    [single]$Size, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
$flags = [System.Windows.Forms.TextFormatFlags]::NoPadding -bor [System.Windows.Forms.TextFormatFlags]::SingleLine
$pad = [int]($Size * 0.45)
$result = @()
foreach ($it in $items) {
    $sz = [System.Windows.Forms.TextRenderer]::MeasureText($it.text, $typeface, (New-Object System.Drawing.Size 4000, 400), $flags)
    $w = $sz.Width + 2 * $pad; $h = $sz.Height + $pad
    $bmp = New-Object System.Drawing.Bitmap $w, $h
    $g = [System.Drawing.Graphics]::FromImage($bmp); $g.Clear([System.Drawing.Color]::Black)
    [System.Windows.Forms.TextRenderer]::DrawText($g, $it.text, $typeface, (New-Object System.Drawing.Point $pad, ([int]($pad / 2))), [System.Drawing.Color]::White, $flags)
    $g.Dispose(); $bmp.Save($it.out, [System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()
    $result += @{ out = $it.out; width = $w; height = $h }
}
ConvertTo-Json -InputObject @($result) -Compress
