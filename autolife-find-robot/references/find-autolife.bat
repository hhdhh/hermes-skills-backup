@echo off
setlocal enabledelayedexpansion

echo ==================================================
echo  Find ARP devices whose hostname contains "autolife"
echo ==================================================
echo.

set "count=0"

for /f "tokens=1" %%a in ('arp -a ^| findstr /r "^ *[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*"') do (
    set "ip=%%a"
    set "skip=0"

    rem skip multicast / broadcast
    echo !ip! | findstr /b /c:"224." /c:"239." /c:"255." /c:"0." >nul && set "skip=1"

    if !skip!==0 (
        set "hostname="

        rem run nslookup, keep only lines containing autolife
        for /f "tokens=2 delims=:" %%x in ('nslookup !ip! 2^>nul ^| findstr /i "autolife"') do (
            if not defined hostname (
                set "hostname=%%x"
                rem trim leading spaces
                for /f "tokens=* delims= " %%z in ("!hostname!") do set "hostname=%%z"
            )
        )

        if defined hostname (
            echo !ip!    !hostname!
            set /a count+=1
        )
    )
)

echo.
echo Found !count! device^(s^) with "autolife" in hostname.
echo.
pause
endlocal