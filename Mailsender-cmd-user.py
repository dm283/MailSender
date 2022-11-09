import sys
import configparser
from cryptography.fernet import Fernet
import re
import datetime
import json
import tkinter as tk
from tkinter import ttk
import asyncio
from aiosmtplib import SMTP
import aioodbc
from aioimaplib import aioimaplib
import email

config = configparser.ConfigParser()
config.read('config.ini')

with open('rec-k.txt') as f:
    rkey = f.read().encode('utf-8')

hashed_user_credentials_password = config['user_credentials']['password']
hashed_smtp_server_password = config['smtp_server']['password']

refKey = Fernet(rkey)
user_credentials_password = (refKey.decrypt(hashed_user_credentials_password).decode('utf-8'))
smtp_server_password = (refKey.decrypt(hashed_smtp_server_password).decode('utf-8'))


# запуск приложения без аргументов - используется дефолтное (из конфига) кол-во записей читаемых из бд
scheduler_handling_db_recs = config['common']['scheduler_handling_db_recs']
if scheduler_handling_db_recs.isdigit():
    CNT_RECS = int(config['common']['scheduler_handling_db_recs'])  # кол-во записей читаемых из бд
    IS_ALL_RECS = False                                             # флаг чтения всех записей из бд
elif scheduler_handling_db_recs == 'all':
    IS_ALL_RECS = True
    
if len(sys.argv) > 1 and sys.argv[1].isdigit(): # при запуске приложения с аргументом (равным кол-ву записей читаемых из бд)
    CNT_RECS = int(sys.argv[1])
    IS_ALL_RECS = False

print('АРГУМЕНТ ЗАПУСКА ПРИЛОЖЕНИЯ = ', sys.argv)
#print('кол-во записей для обработки = ', cnt_recs)


IS_MOCK_DB = True if config['database']['is_mock_db'] == 'True' else False # для локального тестирования приложение работает с симулятором базы данных файл mock-db.json
DB = config['database']['db']  # база данных mssql/posgres
DB_TABLE = config['database']['db_table']  # db.schema.table
CONNECTION_STRING = config['database']['connection_string']  # odbc driver system dsn name
CHECK_DB_PERIOD = int(config['common']['check_db_period'])  # период проверки новых записей в базе данных

USER_NAME = config['user_credentials']['name']
# USER_PASSWORD = config['user_credentials']['password']
USER_PASSWORD = user_credentials_password
ADMIN_EMAIL = config['common']['admin_email']  # почта админа
MY_ADDRESS, PASSWORD = config['smtp_server']['my_address'], smtp_server_password  #config['smtp_server']['password']
HOST, PORT = config['smtp_server']['host'], config['smtp_server']['port']
TEST_MESSAGE = f"""To: {ADMIN_EMAIL}\nFrom: {MY_ADDRESS}
Subject: Mailsender - тестовое сообщение\n
Это тестовое сообщение отправленное сервисом Mailsender.""".encode('utf8')
UNDELIVERED_MESSAGE = f"""To: {ADMIN_EMAIL}\nFrom: {MY_ADDRESS}
Subject: Mailsender - недоставленное сообщение\n
Это сообщение отправленно сервисом Mailsender.\n""".encode('utf8')
HOST_IMAP, PORT_IMAP = config['imap_server']['host'], config['imap_server']['port']

# === EMAIL FUNCTIONS ===
async def robot():
    # запускает робота
    print('Запуск робота .....')
    if IS_MOCK_DB:
        #  при IS_MOCK_DB приложение работает с mock-database (файл mock-db.json)
        await create_mock_db()
        cnxn, cursor = '', ''
    else:
        print(f'Подключение к базе данных {DB} ..... ', end='')
        cnxn = await aioodbc.connect(dsn=CONNECTION_STRING, loop=loop_robot)
        cursor = await cnxn.cursor()
        print('OK')

    print('Чтение новых записей из базы данных .....')
    emails_data = await db_emails_query(cursor)

    if len(emails_data) > 0:
        print(f'Загружено {len(emails_data)} новых записей')
        await send_mail(cnxn, cursor, emails_data)
    else:
        print('Нет новых сообщений для отправки')

    #  недоставленные сообщения: проверка оповещений, запись в лог и отправка на почту админа
    print('Проверка неотправленных сообщений .....')
    undelivereds = await check_undelivered(HOST_IMAP, MY_ADDRESS, PASSWORD)
    if len(undelivereds) > 0:
        smtp_client = SMTP(hostname=HOST, port=PORT, use_tls=True, username=MY_ADDRESS, password=PASSWORD)
        await smtp_client.connect()
        for u in undelivereds:
            #print(f'undelivered:  {u}')
            log_rec = f'Недоставлено сообщение, отправленное {u[0]} на несуществующий адрес {u[1]}'
            await rec_to_log(log_rec)
            msg = UNDELIVERED_MESSAGE + log_rec.encode('utf-8')
            await smtp_client.sendmail(MY_ADDRESS, ADMIN_EMAIL, msg)
        await smtp_client.quit()

    #  действия после остановки робота
    await cursor.close()
    await cnxn.close()
    print("Робот остановлен")

async def send_mail(cnxn, cursor, emails_data):
    # отправляет почту
    smtp_client = SMTP(hostname=HOST, port=PORT, use_tls=True, username=MY_ADDRESS, password=PASSWORD)
    await smtp_client.connect() 
    for e in emails_data:
        # e =  (1, 'test1', 'This is the test message 1!', 'testbox283@yandex.ru; testbox283@mail.ru')
        # print("Новая запись ", e)  ### test
        addrs = e[3].split(';')
        for a in addrs:
            msg = f'To: {a.strip()}\nFrom: {MY_ADDRESS}\nSubject: {e[1]}\n\n{e[2]}'.encode("utf-8")
            await smtp_client.sendmail(MY_ADDRESS, a.strip(), msg)
            log_rec = f'send message to {a.strip()} [ id = {e[0]} ]'
            await rec_to_log(log_rec)
        await db_emails_rec_date(cnxn, cursor, id=e[0])
        print('Сообщения успешно отправлены')
    await smtp_client.quit()

async def check_undelivered(host, user, password):
    # проверяет неотправленные сообщения, написано для imap@yandex, для других серверов может потребоваться корректировка функции
    imap_client = aioimaplib.IMAP4_SSL(host=host)
    await imap_client.wait_hello_from_server()
    await imap_client.login(user, password)
    await imap_client.select('INBOX')
    typ, msg_nums_unseen = await imap_client.search('UNSEEN')
    typ, msg_nums_from_subject = await imap_client.search('(FROM "mailer-daemon@yandex.ru" SUBJECT "Недоставленное сообщение")')
    msg_nums_unseen = set(msg_nums_unseen[0].decode().split())
    msg_nums_from_subject = set(msg_nums_from_subject[0].decode().split())
    msg_nums = ' '.join(list(msg_nums_unseen & msg_nums_from_subject))
    #msg_nums = '7 8'  #  для разработки
    l = len(msg_nums.split())
    if l == 0:
        print('Нет новых оповещений о недоставленный почте')    ###
        await imap_client.close()
        await imap_client.logout()
        return []
    print(f'Получено {l} оповещений о недоставленной почте')    ###
    msg_nums = msg_nums.replace(' ', ',')
    typ, data = await imap_client.fetch(msg_nums, '(UID BODY[TEXT])')

    undelivered = []
    for m in range(1, len(data), 3):
        msg = email.message_from_bytes(data[m])
        msg = msg.get_payload()
        msg_arrival_date = re.search(r'(?<=Arrival-Date: ).*', msg)[0].strip()
        msg_recipient = re.search(r'(?<=Original-Recipient: rfc822;).*', msg)[0].strip()
        undelivered.append((msg_arrival_date, msg_recipient))

    await imap_client.close()
    await imap_client.logout()

    return undelivered


# === DATABASE FUNCTIONS ===
async def db_emails_rec_date(cnxn, cursor, id):
    # пишет в базу дату/время отправки сообщения
    if IS_MOCK_DB:
        await mock_db_emails_rec_date(id)
    else:
        dt_string = str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        await cursor.execute(f"update {DB_TABLE} set dates = '{dt_string}' where UniqueIndexField = {id}")
        await cnxn.commit()

async def mock_db_emails_rec_date(id):
    # mock-аналог db_emails_rec_date()
    with open('mock-db.json', 'r+') as f:
        data = json.load(f)
        for i in range( len(data['emails']) ):
            if data['emails'][i]['UniqueIndexField'] == id and not data['emails'][i]['dates']:
                data['emails'][i]['dates'] = str(datetime.datetime.now())
                f.seek(0)
                json.dump(data, f)

async def rec_to_log(rec):
    # пишет в лог-файл запись об отправке сообщения
    current_time = str(datetime.datetime.now())
    with open('log-mailsender.log', 'a') as f:
        f.write(f'{current_time}  --  {rec}\n')

async def db_emails_query(cursor):
    # выборка из базы данных необработанных (новых) записей
    if IS_MOCK_DB:
        rows = await mock_db_emails_query()
    else:
        # выборка всех необработанных сообщений
        await cursor.execute(f"""select UniqueIndexField, subj, textemail, adrto from {DB_TABLE} where dates is null order by datep""")
        rows = await cursor.fetchall()  # список кортежей
        # оставляем заданное в аргументах приложения кол-во записей (все записи при all)
        rows = rows[:CNT_RECS] if not IS_ALL_RECS and len(rows) > 0 else rows
    return rows

async def mock_db_emails_query():
    # mock-аналог db_emails_query()
    rows = []
    with open('mock-db.json') as f:
        data = json.load(f)
    for i in data['emails']:
        if not i['dates']:
            row = (i['UniqueIndexField'], i['subj'], i['textemail'], i['adrto'])
            rows.append(row)
    return rows

async def create_mock_db():
    # создает mock-database при запуске приложения, если IS_MOCK_DB = True
    data = {'emails': [
        {'UniqueIndexField': 1, 'subj': 'test1', 'textemail': 'This is the test message 1!', 'adrto': 'testbox283@yandex.ru; testbox283@mail.ru', 'dates': None}, 
        {'UniqueIndexField': 2, 'subj': 'test2', 'textemail': 'This is the test message 2!', 'adrto': 'testbox283@yandex.ru; t34rfe94fewf@mail.ru', 'dates': None}, 
        {'UniqueIndexField': 3, 'subj': 'test3', 'textemail': 'This is the test message 3!', 'adrto': 'testbox283@yandex.ru', 'dates': None}
        ]}
    with open('mock-db.json', 'w') as f:
        json.dump(data, f)
    print('Создана MOCK база данных  -  файл mock-db.json')


loop_robot = asyncio.get_event_loop()
loop_robot.run_until_complete(robot())
