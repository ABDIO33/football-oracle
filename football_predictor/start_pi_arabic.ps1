# VS Code + RTL Terminal + pi launcher
# Uses .NET SendKeys for reliable keystroke sending

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Football Predictor - pi with Arabic" -ForegroundColor Cyan
Write-Host "========================================"
Write-Host ""

$projectPath = "C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor"
$codePath = "C:\Users\zake.exe\AppData\Local\Programs\Microsoft VS Code\Code.exe"

Write-Host "1. Starting VS Code..." -ForegroundColor Green

# Kill any existing VS Code first
Get-Process Code -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# Start VS Code fresh
Start-Process -FilePath $codePath -ArgumentList "-n `"$projectPath`""
Start-Sleep -Seconds 6

Write-Host "2. Activating VS Code window..." -ForegroundColor Green

# Load WinAPI for window management
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
public class WinAPI {
    [DllImport("user32.dll")]
    public static extern bool EnumWindows(EnumWindowsProc enumProc, IntPtr lParam);
    [DllImport("user32.dll")]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
    [DllImport("user32.dll")]
    public static extern int GetWindowTextLength(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")]
    public static extern bool IsIconic(IntPtr hWnd);
    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
    
    public static IntPtr FindWindow(string partialTitle) {
        IntPtr found = IntPtr.Zero;
        EnumWindows((hWnd, lParam) => {
            int len = GetWindowTextLength(hWnd);
            if (len > 0) {
                StringBuilder sb = new StringBuilder(256);
                GetWindowText(hWnd, sb, 256);
                if (sb.ToString().IndexOf(partialTitle, StringComparison.OrdinalIgnoreCase) >= 0) {
                    found = hWnd;
                    return false;
                }
            }
            return true;
        }, IntPtr.Zero);
        return found;
    }
}
"@

# Load Windows Forms for SendKeys
Add-Type -AssemblyName System.Windows.Forms

# Find and activate VS Code window
$hWnd = [WinAPI]::FindWindow("Visual Studio Code")
if ($hWnd -ne [IntPtr]::Zero) {
    Write-Host "   Found VS Code window! Activating..." -ForegroundColor Yellow
    
    # Restore if minimized
    if ([WinAPI]::IsIconic($hWnd)) {
        [WinAPI]::ShowWindow($hWnd, 9)
        Start-Sleep -Milliseconds 500
    }
    
    # Bring to foreground
    [WinAPI]::SetForegroundWindow($hWnd)
    Start-Sleep -Milliseconds 1000
    
    Write-Host "3. Opening RTL Terminal (Ctrl+Shift+T)..." -ForegroundColor Green
    
    # Send the keystroke
    [System.Windows.Forms.SendKeys]::SendWait("^+T")
    Start-Sleep -Milliseconds 2000
    
    Write-Host "4. Starting pi..." -ForegroundColor Green
    [System.Windows.Forms.SendKeys]::SendWait("pi")
    Start-Sleep -Milliseconds 400
    [System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  DONE! pi is running in RTL Terminal!" -ForegroundColor Green
    Write-Host "  Arabic text will display correctly!" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Tips:" -ForegroundColor White
    Write-Host "  - Press F1 for a new RTL Terminal" -ForegroundColor Yellow
    Write-Host "  - Press Ctrl+Shift+T for RTL Terminal" -ForegroundColor Yellow
    Write-Host "  - Use /tree to navigate history" -ForegroundColor Yellow
    Write-Host "  - Use /resume for past sessions" -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host "ERROR: Could not find VS Code window!" -ForegroundColor Red
    Write-Host "Open VS Code manually, then press Ctrl+Shift+T and type: pi" -ForegroundColor Yellow
}

Start-Sleep -Seconds 3
