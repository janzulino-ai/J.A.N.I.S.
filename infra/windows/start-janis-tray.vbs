Set sh = CreateObject("WScript.Shell")
root = "C:\\APP IA\\JANIS"
sh.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & root & "\infra\windows\janis-tray.ps1""", 0, False
