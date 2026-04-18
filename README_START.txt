Запуск:
1. В pgAdmin создайте базу cake_demo.
2. В psql задайте пароль пользователю postgres = 1234.
3. В терминале:
py -3.11 -m pip install -r requirements.txt
py -3.11 import_data.py
py -3.11 run.py

Открыть: http://127.0.0.1:5000

Логины берутся из import/user_import.xlsx
Пример администратора:
kondratieva@cake-shop.ru / AdCk76#
