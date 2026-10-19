param([string]$Voice = 'Microsoft Zira Desktop')
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$VideoRoot = $PSScriptRoot
$BuildRoot = Join-Path $VideoRoot 'build'
$AudioRoot = Join-Path $BuildRoot 'audio'
New-Item -ItemType Directory -Force -Path $AudioRoot | Out-Null
$Story = Get-Content -LiteralPath (Join-Path $VideoRoot 'storyboard.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$Narrator = New-Object System.Speech.Synthesis.SpeechSynthesizer
$Narrator.SelectVoice($Voice)
$Narrator.Rate = 1
$Narrator.Volume = 100
try {
    foreach ($Scene in $Story.scenes) {
        for ($Index = 0; $Index -lt $Scene.captions.Count; $Index++) {
            $OutputPath = Join-Path $AudioRoot ('{0}-{1}.wav' -f $Scene.id, $Index)
            $Narrator.SetOutputToWaveFile($OutputPath)
            $Narrator.Speak($Scene.captions[$Index])
            $Narrator.SetOutputToNull()
        }
    }
} finally {
    $Narrator.Dispose()
}
Write-Output ('Narration saved to {0}' -f $AudioRoot)
