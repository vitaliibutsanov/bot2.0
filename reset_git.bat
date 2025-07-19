@echo off
:: Перенастройка Git для проекта Bot 2.0

cd /d "E:\bot2.0"

git init
git remote set-url origin https://github.com/vitaliibutsanov/bot2.0.git
git branch -M main
git add .
git commit -m "Перенос в новую папку"
git push -u origin main

echo ===============================
echo Git успешно перенастроен!
echo ===============================
pause
