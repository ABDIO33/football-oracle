' Eternal Engine Launcher — VBS script (invisible, no console window)
' Runs the orchestrator daemon silently in background

Dim objShell, objFSO, pythonExe, scriptPath, logDir, stdoutFile, stderrFile

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' Paths
scriptPath = "C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor\harvesters\eternal_orchestrator.py"
logDir = "C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor\harvesters\harvest_logs"
pythonExe = "C:\Python314\python.exe"

' Ensure log dir exists
If Not objFSO.FolderExists(logDir) Then
    objFSO.CreateFolder(logDir)
End If

' Timestamp
Dim ts
ts = Year(Now) & Month(Now) & Day(Now) & "_" & Hour(Now) & Minute(Now) & Second(Now)

stdoutFile = logDir & "\daemon_" & ts & ".log"
stderrFile = logDir & "\daemon_" & ts & "_err.log"

' Run hidden (0 = hidden window)
Dim cmd
cmd = pythonExe & " -X utf8 """ & scriptPath & """ --daemon"

' Use Run with 0 (hidden window) and waitOnReturn=False (async)
objShell.Run cmd, 0, False
