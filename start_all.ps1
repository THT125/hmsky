# 苍穹外卖重构版 — 一键启动脚本
# 使用方式: powershell -File start_all.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "    苍穹外卖 (FastAPI + Vue3 + MySQL)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$py = "D:\anaconda\envs\sky-take-out-master-cg\python.exe"

Write-Host "`n[1/3] 启动后端 (端口 8000)..." -ForegroundColor Green
Start-Process -FilePath $py -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--reload" -WorkingDirectory "$PSScriptRoot\backend" -NoNewWindow
Start-Sleep -Seconds 3

Write-Host "`n[2/3] 启动管理端前端 (端口 5173)..." -ForegroundColor Green
Start-Process -FilePath "npx" -ArgumentList "vite", "--host" -WorkingDirectory "$PSScriptRoot\frontend-admin" -NoNewWindow
Start-Sleep -Seconds 3

Write-Host "`n[3/3] 启动用户端前端 (端口 5174)..." -ForegroundColor Green
Start-Process -FilePath "npx" -ArgumentList "vite", "--port", "5174" -WorkingDirectory "$PSScriptRoot\frontend-user" -NoNewWindow

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  启动完成！" -ForegroundColor Yellow
Write-Host "  管理端: http://localhost:5173" -ForegroundColor Yellow
Write-Host "  用户端: http://localhost:5174" -ForegroundColor Yellow
Write-Host "  API文档: http://127.0.0.1:8000/docs" -ForegroundColor Yellow
Write-Host "  管理端默认账号: admin / 123456" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
