Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
public class WinAPI {
    [DllImport("user32.dll", CharSet=CharSet.Auto, SetLastError=true)]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
    [DllImport("user32.dll", CharSet=CharSet.Auto, SetLastError=true)]
    public static extern int GetWindowTextLength(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern bool EnumWindows(EnumWindowsProc enumProc, IntPtr lParam);
    [DllImport("user32.dll")]
    public static extern bool IsWindowVisible(IntPtr hWnd);
    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
}
"@

[WinAPI]::EnumWindows({
    param($hWnd, $lParam)
    $length = [WinAPI]::GetWindowTextLength($hWnd)
    if ($length -gt 0) {
        $sb = New-Object System.Text.StringBuilder 256
        [WinAPI]::GetWindowText($hWnd, $sb, 256)
        $title = $sb.ToString()
        if ($title -match "Code|VS Code|Visual Studio") {
            Write-Host "Found: $title"
        }
    }
    return $true
}, [IntPtr]::Zero)
