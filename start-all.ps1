# Скрипт для запуска всех сервисов одновременно (Windows PowerShell)
# Использование: .\start-all.ps1

param(
    [switch]$SkipDeps
)

Write-Host "🚀 Запуск сервисов Motivation Bot..." -ForegroundColor Green

# Проверка наличия Node.js
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Node.js не установлен. Установите Node.js и попробуйте снова." -ForegroundColor Red
    exit 1
}

# Проверка наличия Python
$pythonCmd = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    $pythonCmd = "python3"
} else {
    Write-Host "❌ Python не установлен. Установите Python и попробуйте снова." -ForegroundColor Red
    exit 1
}

# Функция для корректного завершения всех процессов
function Cleanup {
    Write-Host ""
    Write-Host "🛑 Завершение работы всех сервисов..." -ForegroundColor Yellow

    if ($nodejsJob) {
        Stop-Job $nodejsJob -ErrorAction SilentlyContinue
    }
    if ($botJob) {
        Stop-Job $botJob -ErrorAction SilentlyContinue
    }
    if ($moderatorJob) {
        Stop-Job $moderatorJob -ErrorAction SilentlyContinue
    }

    exit 0
}

# Обработчик сигналов для корректного завершения
$null = Register-ObjectEvent -InputObject ([Console]::CancelKeyPress) -EventName "CancelKeyPress" -Action {
    Cleanup
}

if (-not $SkipDeps) {
    Write-Host "📦 Установка зависимостей..." -ForegroundColor Blue

    # Установка Node.js зависимостей для генератора карточек
    if (Test-Path "Player Card Design\package.json") {
        Write-Host "📦 Установка Node.js зависимостей для генератора карточек..." -ForegroundColor Blue
        Push-Location "Player Card Design"
        npm install
        Pop-Location
    }

    # Установка Python зависимостей
    if (Test-Path "requirements.txt") {
        Write-Host "📦 Установка Python зависимостей..." -ForegroundColor Blue
        & $pythonCmd -m pip install -r requirements.txt
    }
}

Write-Host "🎮 Запуск Node.js сервиса генерации карточек..." -ForegroundColor Blue
if (Test-Path "Player Card Design") {
    $nodejsJob = Start-Job -ScriptBlock {
        Set-Location $using:PWD
        Set-Location "Player Card Design"
        npm start
    }
    Write-Host "📊 Node.js сервис запущен (Job ID: $($nodejsJob.Id))" -ForegroundColor Green
} else {
    Write-Host "⚠️ Папка 'Player Card Design' не найдена. Пропускаем запуск Node.js сервиса." -ForegroundColor Yellow
    $nodejsJob = $null
}

# Ждем запуска Node.js сервиса
Start-Sleep -Seconds 3

Write-Host "🤖 Запуск основного бота..." -ForegroundColor Blue
$botJob = Start-Job -ScriptBlock {
    param($pythonCmd)
    & $pythonCmd bot.py
} -ArgumentList $pythonCmd
Write-Host "🎯 Основной бот запущен (Job ID: $($botJob.Id))" -ForegroundColor Green

Write-Host "👑 Запуск модераторского бота..." -ForegroundColor Blue
$moderatorJob = Start-Job -ScriptBlock {
    param($pythonCmd)
    & $pythonCmd moderator_bot.py
} -ArgumentList $pythonCmd
Write-Host "⚔️ Модераторский бот запущен (Job ID: $($moderatorJob.Id))" -ForegroundColor Green

Write-Host ""
Write-Host "✅ Все сервисы запущены!" -ForegroundColor Green
Write-Host "📋 Job ID процессов:" -ForegroundColor Cyan
Write-Host "  • Node.js сервис: $($nodejsJob.Id)" -ForegroundColor Cyan
Write-Host "  • Основной бот: $($botJob.Id)" -ForegroundColor Cyan
Write-Host "  • Модераторский бот: $($moderatorJob.Id)" -ForegroundColor Cyan
Write-Host ""
Write-Host "🛑 Для остановки нажмите Ctrl+C или закройте окно PowerShell" -ForegroundColor Yellow

# Мониторинг состояния процессов
while ($true) {
    $nodejsState = $nodejsJob.State
    $botState = $botJob.State
    $moderatorState = $moderatorJob.State

    if ($nodejsState -eq "Failed" -or $botState -eq "Failed" -or $moderatorState -eq "Failed") {
        Write-Host "❌ Один из сервисов завершился с ошибкой!" -ForegroundColor Red
        Cleanup
    }

    if ($nodejsState -eq "Completed" -or $botState -eq "Completed" -or $moderatorState -eq "Completed") {
        Write-Host "⚠️ Один из сервисов завершил работу" -ForegroundColor Yellow
        Cleanup
    }

    Start-Sleep -Seconds 5
}
