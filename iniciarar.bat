@echo off
:: Cambiar al directorio del proyecto
cd /d "C:\Users\brian\OneDrive\Escritorio\app-libros"

echo ===================================================
echo 1. Actualizando precios de Buscalibre...
echo ===================================================
:: Activar el entorno virtual y ejecutar el scraper
call .venv\Scripts\activate.bat
python app-libros.py

echo.
echo ===================================================
echo 2. Iniciando servidor web local...
echo ===================================================
echo Abre tu navegador en: http://localhost:8000
echo ===================================================
:: Levantar el servidor
python -m http.server 8000