Option Explicit

Dim shell, fso, rootDir, appScript, command

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

rootDir = fso.GetParentFolderName(WScript.ScriptFullName)
appScript = fso.BuildPath(fso.BuildPath(rootDir, "app"), "Install-SN2-Mod.pyw")
command = "pythonw.exe " & Quote(appScript)

On Error Resume Next
shell.Run command, 0, False
If Err.Number <> 0 Then
    Err.Clear
    command = "python.exe " & Quote(appScript)
    shell.Run command, 0, False
End If
On Error GoTo 0

Function Quote(value)
    Quote = Chr(34) & value & Chr(34)
End Function
