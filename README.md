# Mailsender

СЕРВИС АВТОМАТИЗАЦИИ ОТПРАВКИ E-MAIL СООБЩЕНИЙ

Файлы приложений: пользовательское Mailsender-app.py, администрирование Mailsender-admin-app.py. Возможна их компиляция в exe-файлы.<br/>
Внешние python-библиотеки:  aiosmtplib, aioodbc, aioimaplib.

1) В директорию с файлами приложений добавляем файл config.ini, при необходимости настраиваем его (файл у разработчика приложения).

2) Возможны 2 варианта работы приложения с базой данных:</br>
   -  при использовании базы данных Microsoft SQL/PostgreSQL в config.ini устанавливаем is_mock_db=False, и соответствующие db, dsn, db_table.<br/>
   -  для работы с симулятором базы данных (локальный json-файл) устанавливаем is_mock_db = True в config.ini, файл с бд будет создан автоматически при запуске робота.

3) Запускаем файл соответствующего приложения.

Пользователю доступен следующий функционал:
- Запуск робота - стартует робота, периодически загружающего новые записи из базы данных и отправляющего сообщения (период check_db_period в config.ini).<br/>
- Остановка робота - завершает текущий процесс приема/отправки сообщений и останавливает робота.<br/>
- Выход - производит остановку робота и выходит из приложения.

После отправки e-mail, в базу данных пишется дата и время отправки, в лог-файл пишутся отправки по каждому адресу.<br/>
Если e-mail недоставлен, происходит оповещение админа по e-mail и запись в лог.<br/>
Для отправки роботом новых сообщений добавляем записи в базу данных или в файл mock-db.json с dates = null.

Функционл администрирования:
- Просмотр и корректировка конфигурации приложения.<br/>
- Тестирование окружения (база данных, smtp и imap серверы).<br/>