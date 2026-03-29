# Windows Setup

## 1. Install Python

1. Go to https://www.python.org/downloads/windows/ or use [Python Installer](windows/python-3.13.12-amd64.exe)
2. Download Python 3.13 or newer for Windows.
3. Run the installer.
4. Enable `Add Python to PATH`.
5. Choose `Install Now`.

After installation, open Command Prompt and verify:

```bat
py --version
```

## 2. Install Reader Support

Install the official ACS ACR38U Windows driver package [ACS ACR38U Driver Package](windows/ACS-Unified-MSI-Win-4310-1-.zip).

Do not rely only on the generic Microsoft smart-card reader driver if card access is unreliable or slow.

Also make sure the Windows Smart Card service is available.

Check that the reader appears in Device Manager before testing the app.

## 3. Create a Virtual Environment

From the project folder in Command Prompt:

```bat
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
```

## 4. Install Project Dependencies

```bat
.\.venv\Scripts\python.exe -m pip install -e .
```

If `pyscard` fails to build, install Visual Studio Build Tools and try again.

## 5. Run The App

```bat
.\.venv\Scripts\python.exe app.py
```

Optional:

```bat
set PYCARD_LOG_LEVEL=DEBUG
.\.venv\Scripts\python.exe app.py
```

```bat
set PYCARD_LANG=en
.\.venv\Scripts\python.exe app.py
```

## 6. Build a Windows Executable

Install the packaging tool:

```bat
.\.venv\Scripts\python.exe -m pip install -e ".[windows-build]"
```

Build the app:

```bat
windows\build-windows.bat
```

Clean and rebuild:

```bat
windows\build-windows.bat clean
```

This uses the repository PyInstaller config:

- [`pycard.spec`](pycard.spec)
- [`windows/build-windows.bat`](windows/build-windows.bat)

The built executable will be:

```text
dist\pycard\pycard.exe
```

You can create a desktop shortcut to that file and launch the app by double-clicking it.

## 7. What To Expect

- The app should start even without a reader.
- The reader can be plugged in after startup.
- A card can be inserted or removed while the app is running.
- Slovenian is the default UI language.
- The language can be changed in the app header.

## 8. Windows Smart Card Delays

If Windows shows a smart-card setup toast or the reader LED blinks for a long time after card insertion, Windows may be accessing the card before the app does.

Keep the Smart Card service enabled:

- service name: `SCardSvr`

PowerShell as Administrator:

```powershell
Set-Service SCardSvr -StartupType Automatic
Start-Service SCardSvr
```

To verify:

```powershell
Get-Service SCardSvr
```

You want to see it as `Running`.


If the first card access is still very slow, disable Certificate Propagation.

PowerShell as Administrator:

```powershell
Stop-Service CertPropSvc -Force
Set-Service CertPropSvc -StartupType Disabled
sc.exe config CertPropSvc start= disabled
reg add "HKLM\SYSTEM\CurrentControlSet\Services\CertPropSvc" /v Start /t REG_DWORD /d 4 /f

reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\ScPnP" /v EnableScPnP /t REG_DWORD /d 0 /f

reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\CertProp" /v CertPropEnabled /t REG_DWORD /d 0 /f
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\CertProp" /v EnableRootCertificatePropagation /t REG_DWORD /d 0 /f

Stop-Service ScDeviceEnum -Force
Set-Service ScDeviceEnum -StartupType Disabled
sc.exe config ScDeviceEnum start= disabled

```

You might need to reboot after changing the policy.

This has been confirmed to remove the long delay on Windows 10 in this project setup.
