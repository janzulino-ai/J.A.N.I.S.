@echo off
:: JANIS — esponi brain WSL sulla LAN (Mac, iPhone, VPN)
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \"%~dp0setup-lan-forward.ps1\"'"
