@echo off

del /f /s /q c:\windows\temp\*.* 
rd /s /q c:\windows\temp
md c:\windows\temp

del /f /s /q c:\windows\Prefetch\*.*
rd /s /q c:\windows\Prefetch
md c:\windows\Prefetch

del /f /s /q %temp%\*.*
rd /s /q %temp%
md %temp%

del /f /s /q %homepath%\Config~1\Temp\*.* 
rd /s /q %homepath%\Config~1\Temp
md %homepath%\Config~1\Temp

del /f /s /q %windir%\Tempor~1\*.* 
rd /s /q %windir%\Tempor~1
md %windir%\Tempor~1

deltree /y c:\windows\tempor~1
deltree /y c:\windows\temp
deltree /y c:\windows\tmp
deltree /y c:\windows\ff*.tmp
deltree /y c:\windows\history
deltree /y c:\windows\cookies
deltree /y c:\windows\recent
deltree /y c:\windows\spool\printers
del c:\WIN386.SWP
cls