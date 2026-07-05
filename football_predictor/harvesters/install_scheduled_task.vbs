' Install Windows Scheduled Task for Eternal Drain Engine
' Runs at user login and every 4 hours

Dim objShell, taskName, scriptPath, pythonPath, cmd

Set objShell = CreateObject("WScript.Shell")
taskName = "EternalDrainEngine"
scriptPath = "C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor\harvesters\eternal_orchestrator.py"
pythonPath = "C:\Python314\python.exe"
cmd = pythonPath & " -X utf8 """ & scriptPath & """ --daemon"

' Delete existing task if any
objShell.Run "schtasks /Delete /TN " & taskName & " /F", 0, True

' Create new task
Dim taskXML
taskXML = "<?xml version=""1.0"" encoding=""UTF-16""?>" & vbCrLf
taskXML = taskXML & "<Task version=""1.2"" xmlns=""http://schemas.microsoft.com/windows/2004/02/mit/task"">" & vbCrLf
taskXML = taskXML & "  <RegistrationInfo>" & vbCrLf
taskXML = taskXML & "    <Description>Eternal Drain System — Football Data Harvester. Runs 24/7, auto-restarts, self-healing.</Description>" & vbCrLf
taskXML = taskXML & "  </RegistrationInfo>" & vbCrLf
taskXML = taskXML & "  <Triggers>" & vbCrLf
taskXML = taskXML & "    <LogonTrigger><Enabled>true</Enabled></LogonTrigger>" & vbCrLf
taskXML = taskXML & "  </Triggers>" & vbCrLf
taskXML = taskXML & "  <Principals>" & vbCrLf
taskXML = taskXML & "    <Principal id=""Author"">" & vbCrLf
taskXML = taskXML & "      <RunLevel>LeastPrivilege</RunLevel>" & vbCrLf
taskXML = taskXML & "    </Principal>" & vbCrLf
taskXML = taskXML & "  </Principals>" & vbCrLf
taskXML = taskXML & "  <Settings>" & vbCrLf
taskXML = taskXML & "    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>" & vbCrLf
taskXML = taskXML & "    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>" & vbCrLf
taskXML = taskXML & "    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>" & vbCrLf
taskXML = taskXML & "    <AllowHardTerminate>true</AllowHardTerminate>" & vbCrLf
taskXML = taskXML & "    <StartWhenAvailable>true</StartWhenAvailable>" & vbCrLf
taskXML = taskXML & "    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>" & vbCrLf
taskXML = taskXML & "    <RestartOnFailure>" & vbCrLf
taskXML = taskXML & "      <Interval>PT1M</Interval>" & vbCrLf
taskXML = taskXML & "      <Count>10</Count>" & vbCrLf
taskXML = taskXML & "    </RestartOnFailure>" & vbCrLf
taskXML = taskXML & "  </Settings>" & vbCrLf
taskXML = taskXML & "  <Actions Context=""Author"">" & vbCrLf
taskXML = taskXML & "    <Exec>" & vbCrLf
taskXML = taskXML & "      <Command>" & pythonPath & "</Command>" & vbCrLf
taskXML = taskXML & "      <Arguments>-X utf8 """ & scriptPath & """ --daemon</Arguments>" & vbCrLf
taskXML = taskXML & "    </Exec>" & vbCrLf
taskXML = taskXML & "  </Actions>" & vbCrLf
taskXML = taskXML & "</Task>"

' Write XML to temp file
Dim tempFile
tempFile = objShell.ExpandEnvironmentStrings("%TEMP%") & "\eternal_task.xml"
Dim objFSO: Set objFSO = CreateObject("Scripting.FileSystemObject")
Dim objFile: Set objFile = objFSO.CreateTextFile(tempFile, True)
objFile.Write taskXML
objFile.Close

' Register task
objShell.Run "schtasks /Create /XML """ & tempFile & """ /TN " & taskName & " /F", 0, True

' Cleanup
objFSO.DeleteFile tempFile

WScript.Echo "Scheduled task '" & taskName & "' installed successfully!"
WScript.Echo "Runs at user login and auto-restarts on failure."
