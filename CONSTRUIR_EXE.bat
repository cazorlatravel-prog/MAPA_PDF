@echo off
chcp 65001 >nul
title EstelaGis - Construir ejecutable portable
cd /d "%~dp0"

echo ============================================================
echo   EstelaGis - Planos Forestales
echo   Construccion del ejecutable portable (un solo .exe)
echo ============================================================
echo.

if not exist "%~dp0requirements.txt" (
    echo [ERROR] Este archivo .bat debe estar DENTRO de la carpeta del proyecto,
    echo   junto a requirements.txt, build_portable.py y la carpeta generador_planos.
    echo.
    echo   Descarga el proyecto completo desde GitHub ^(Code ^> Download ZIP^),
    echo   descomprimelo y ejecuta el CONSTRUIR_EXE.bat que hay dentro.
    echo.
    echo   Alternativa sin instalar nada: el .exe ya construido esta en la
    echo   pestana Actions del repositorio ^(apartado Artifacts^).
    echo.
    pause
    exit /b 1
)

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] No se encuentra Python en el PATH.
    echo   Instala Python 3.10 o superior desde https://www.python.org/downloads/
    echo   y marca la casilla "Add python.exe to PATH" durante la instalacion.
    echo.
    pause
    exit /b 1
)

echo [1/3] Actualizando pip...
python -m pip install --upgrade pip --quiet

echo [2/3] Instalando dependencias (puede tardar unos minutos la primera vez)...
python -m pip install -r requirements.txt pyinstaller --quiet
if errorlevel 1 (
    echo.
    echo [ERROR] Fallo la instalacion de dependencias. Revisa los mensajes anteriores.
    pause
    exit /b 1
)

echo [3/3] Construyendo el ejecutable (5-15 minutos)...
echo.
python build_portable.py
if errorlevel 1 (
    echo.
    echo [ERROR] Fallo la construccion del ejecutable. Revisa los mensajes anteriores.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   LISTO. El ejecutable esta en:
echo     %~dp0dist\EstelaGis_Portable.exe
echo   (y una copia en %~dp0EstelaGis_Portable.exe)
echo ============================================================
echo.
pause
