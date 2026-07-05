@echo off
chcp 65001 >nul
title Football Predictor - pi with Arabic Support

echo ============================================
echo  Football Predictor - pi مع العربية
echo ============================================
echo.
echo  يشتغل من Windows Terminal (يدعم العربية أحسن)
echo  لو ما عندك Windows Terminal، يفتح CMD عادي
echo.

cd /d "C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor"

echo 1. جاري فتح التيرمنال...
where wt.exe >nul 2>nul
if %errorlevel%==0 (
    echo    ✅ Windows Terminal موجود - راح يفتح مع pi
    start "" wt.exe -d "C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor" -p "Git Bash" bash -lc "export LANG=en_US.UTF-8; export LC_ALL=en_US.UTF-8; pi; exec bash"
) else (
    echo    ⚠️ Windows Terminal مش موجود - استخدم CMD
    start "pi" cmd /k "cd /d C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor && pi"
)

echo.
echo  ✅ تم! pi شغال دلوقتي
echo  📝 Tip: افتح VS Code واستخدم Ctrl+Shift+T عشان RTL Terminal
echo.
echo  تم التحميل...
timeout /t 3 /nobreak >nul
exit
