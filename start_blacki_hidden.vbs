Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
command = "cmd /c cd /d """ & folder & """ && python -B blacki_sales_edit_NEW.py"
shell.Run command, 0, False
