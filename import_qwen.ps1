# This script will import the Qwen3.5 model into Ollama once LM Studio finishes downloading it.
# You can run this file by right-clicking it and selecting "Run with PowerShell" 
# OR by typing .\import_qwen.ps1 in your terminal.

$modelfilePath = "Modelfile.qwen"
$ggufPath = "C:\Users\eva\.lmstudio\models\lmstudio-community\Qwen3.5-9B-GGUF\Qwen3.5-9B-Q4_K_M.gguf"

if (Test-Path $ggufPath) {
    Write-Host "Found the downloaded model! Creating Ollama Modelfile..." -ForegroundColor Green
    "FROM `"$ggufPath`"" | Out-File -FilePath $modelfilePath -Encoding utf8
    
    Write-Host "Importing into Ollama (this might take a minute)..." -ForegroundColor Cyan
    ollama create qwen3.5-9b -f $modelfilePath
    
    Write-Host "Successfully imported Qwen3.5-9B into Ollama!" -ForegroundColor Green
    Write-Host "CifikAI is already configured to use it for coding tasks." -ForegroundColor Yellow
} else {
    Write-Host "The model file was not found. It might still be downloading in LM Studio." -ForegroundColor Red
    Write-Host "Expected path: $ggufPath" -ForegroundColor Red
    Write-Host "Please wait for the download to finish, then run this script again." -ForegroundColor Yellow
}

pause
