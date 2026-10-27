param(
    [Parameter(Mandatory = $true)]
    [string]$ImagePath,
    [int]$Repeats = 5
)

Add-Type -AssemblyName System.Runtime.WindowsRuntime

function Invoke-WinRtAsync {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Operation,
        [Parameter(Mandatory = $true)]
        [type]$ResultType
    )

    $method = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetGenericArguments().Count -eq 1 -and $_.GetParameters().Count -eq 1
    } | Select-Object -First 1
    $task = $method.MakeGenericMethod($ResultType).Invoke($null, [object[]]@($Operation))
    return $task.GetAwaiter().GetResult()
}

function Convert-OcrLine {
    param([object]$Line)

    $words = @($Line.Words)
    $x1 = [double]::PositiveInfinity
    $y1 = [double]::PositiveInfinity
    $x2 = [double]::NegativeInfinity
    $y2 = [double]::NegativeInfinity
    foreach ($word in $words) {
        $rect = $word.BoundingRect
        $x1 = [Math]::Min($x1, [double]$rect.X)
        $y1 = [Math]::Min($y1, [double]$rect.Y)
        $x2 = [Math]::Max($x2, [double]$rect.X + [double]$rect.Width)
        $y2 = [Math]::Max($y2, [double]$rect.Y + [double]$rect.Height)
    }
    if ([double]::IsInfinity($x1)) {
        $box = @()
    } else {
        $box = @(
            @($x1, $y1),
            @($x2, $y1),
            @($x2, $y2),
            @($x1, $y2)
        )
    }
    return [ordered]@{
        text = [string]$Line.Text
        score = 1.0
        box = $box
    }
}

$imagePath = (Resolve-Path $ImagePath).Path
$initWatch = [System.Diagnostics.Stopwatch]::StartNew()
$storageFileType = [Windows.Storage.StorageFile, Windows, ContentType=WindowsRuntime]
$file = Invoke-WinRtAsync $storageFileType::GetFileFromPathAsync($imagePath) ([Windows.Storage.StorageFile, Windows, ContentType=WindowsRuntime])
$stream = Invoke-WinRtAsync $file.OpenAsync([Windows.Storage.FileAccessMode]::Read) ([Windows.Storage.Streams.IRandomAccessStream, Windows, ContentType=WindowsRuntime])
$decoder = Invoke-WinRtAsync ([Windows.Graphics.Imaging.BitmapDecoder, Windows, ContentType=WindowsRuntime]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder, Windows, ContentType=WindowsRuntime])
$bitmap = Invoke-WinRtAsync $decoder.GetSoftwareBitmapAsync(
    [Windows.Graphics.Imaging.BitmapPixelFormat]::Bgra8,
    [Windows.Graphics.Imaging.BitmapAlphaMode]::Premultiplied
) ([Windows.Graphics.Imaging.SoftwareBitmap, Windows, ContentType=WindowsRuntime])
$language = [Windows.Globalization.Language, Windows, ContentType=WindowsRuntime]::new('zh-Hans-CN')
$engine = [Windows.Media.Ocr.OcrEngine, Windows, ContentType=WindowsRuntime]::TryCreateFromLanguage($language)
if ($null -eq $engine) {
    throw 'Windows.Media.Ocr could not create the zh-Hans-CN engine.'
}
$initWatch.Stop()

$warmup = Invoke-WinRtAsync $engine.RecognizeAsync($bitmap) ([Windows.Media.Ocr.OcrResult, Windows, ContentType=WindowsRuntime])
$times = New-Object System.Collections.Generic.List[double]
$result = $null
for ($index = 0; $index -lt $Repeats; $index++) {
    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    $result = Invoke-WinRtAsync $engine.RecognizeAsync($bitmap) ([Windows.Media.Ocr.OcrResult, Windows, ContentType=WindowsRuntime])
    $watch.Stop()
    $times.Add($watch.Elapsed.TotalMilliseconds)
}

$detections = New-Object System.Collections.Generic.List[object]
foreach ($line in $result.Lines) {
    $detections.Add((Convert-OcrLine $line))
}
[ordered]@{
    engine = 'WinRT OCR'
    model = 'Windows.Media.Ocr zh-Hans-CN'
    backend = 'Windows Runtime / system OCR'
    confidence_available = $false
    init_ms = $initWatch.Elapsed.TotalMilliseconds
    inference_ms = @($times)
    average_ms = ($times | Measure-Object -Average).Average
    detections = $detections
    text = [string]$result.Text
} | ConvertTo-Json -Depth 10 -Compress
