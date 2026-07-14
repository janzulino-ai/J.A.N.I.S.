from backend.core.security import mac_path_hint, windows_path_to_wsl


def test_windows_path_to_wsl():
    assert windows_path_to_wsl(r"C:\Users\agenz\Documents") == "/mnt/c/Users/agenz/Documents"
    assert windows_path_to_wsl("/home/agenz") is None


def test_mac_path_hint():
    assert mac_path_hint("/Users/janzu/Documents/Obsidian Vault")
    assert mac_path_hint("C:\\Users\\x") is None
