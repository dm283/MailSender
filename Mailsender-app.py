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

IS_MOCK_DB = True if config['database']['is_mock_db'] == 'True' else False # для локального тестирования приложение работает с симулятором базы данных файл mock-db.json
DB = config['database']['db']  # база данных mssql/posgres
DB_TABLE = config['database']['db_table']  # db.schema.table
CONNECTION_STRING = f"DSN={config['database']['dsn']}"  # odbc driver system dsn name
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

ROBOT_START = False
ROBOT_STOP = False
APP_EXIT = False
SIGN_IN_FLAG = False
THEME_COLOR = 'Gainsboro'
LBL_COLOR = THEME_COLOR
ENT_COLOR = 'White'
BTN_COLOR = 'Green'
BTN_1_COLOR = 'IndianRed'
BTN_2_COLOR = 'OrangeRed'
BTN_3_COLOR = 'SlateGray'

# === INTERFACE FUNCTIONS ===
async def btn_sign_click():
    # кнопка sign-in
    global SIGN_IN_FLAG
    user = ent_user.get()
    password = ent_password.get()
    if user == USER_NAME and password == USER_PASSWORD:
        lbl_msg_sign["text"] = ''
        SIGN_IN_FLAG = True
        root.destroy()
    else:
        lbl_msg_sign["text"] = 'Incorrect username or password'

async def btn_exit_click():
    # кнопка Send test email
    global ROBOT_START, ROBOT_STOP, APP_EXIT
    if ROBOT_START:
        lbl_msg_robot["text"] = 'Остановка робота...\nВыход из приложения...'
        ROBOT_STOP = True
        APP_EXIT = True
    else:
        sys.exit()

async def btn_robot_run_click():
    # кнопка Start robot
    global ROBOT_START, ROBOT_STOP
    if not ROBOT_START:
        lbl_msg_robot["text"] = 'Запуск робота...'
    await robot()

async def btn_robot_stop_click():
    # кнопка Stop robot
    global ROBOT_START, ROBOT_STOP
    if ROBOT_START:
        lbl_msg_robot["text"] = 'Остановка робота...'
        ROBOT_STOP = True

async def window_signin():
    # рисует окно входа
    frm.pack()
    lbl_sign.place(x=95, y=30)
    lbl_user.place(x=95, y=83)
    ent_user.place(x=95, y=126)
    lbl_password.place(x=95, y=150)
    ent_password.place(x=95, y=193)
    btn_sign.place(x=95, y=250)
    lbl_msg_sign.place(x=95, y=300)

async def window_robot():
    # рисует окно админки
    frm.pack()
    lbl_robot.place(x=95, y=30)
    btn_robot_run.place(x=95, y=93)
    btn_robot_stop.place(x=95, y=136)
    btn_exit.place(x=125, y=195)
    lbl_runner.place(x=95, y=240)
    lbl_msg_robot.place(x=95, y=280)

# === EMAIL FUNCTIONS ===
async def robot():
    # запускает робота
    global ROBOT_START, ROBOT_STOP
    if ROBOT_START or ROBOT_STOP:
        return
    ROBOT_START = True  # флаг старта робота, предотвращает запуск нескольких экземпляров робота
    print('MOCK_DB =', IS_MOCK_DB)
    if IS_MOCK_DB:
        #  при IS_MOCK_DB приложение работает с mock-database (файл mock-db.json)
        await create_mock_db()
        cnxn, cursor = '', ''
    else:
        cnxn = await aioodbc.connect(dsn=CONNECTION_STRING, loop=loop_robot)
        cursor = await cnxn.cursor()
        print(f'Создано подключение к базе данных {DB}')  ###

    lbl_msg_robot["text"] = 'Робот в рабочем режиме'

    while not ROBOT_STOP:
        emails_data = await db_emails_query(cursor)
        print(emails_data)
        print()
        if len(emails_data) > 0:
            await send_mail(cnxn, cursor, emails_data)
        else:
            print('НЕТ НОВЫХ СООБЩЕНИЙ')  ### test

        #  недоставленные сообщения: проверка оповещений, запись в лог и отправка на почту админа
        undelivereds = await check_undelivered(HOST_IMAP, MY_ADDRESS, PASSWORD)
        if len(undelivereds) > 0:
            smtp_client = SMTP(hostname=HOST, port=PORT, use_tls=True, username=MY_ADDRESS, password=PASSWORD)
            await smtp_client.connect()
            for u in undelivereds:
                print(f'undelivered:  {u}')
                log_rec = f'Недоставлено сообщение, отправленное {u[0]} на несуществующий адрес {u[1]}'
                await rec_to_log(log_rec)
                msg = UNDELIVERED_MESSAGE + log_rec.encode('utf-8')
                await smtp_client.sendmail(MY_ADDRESS, ADMIN_EMAIL, msg)
            await smtp_client.quit()

        await asyncio.sleep(CHECK_DB_PERIOD)

    #  действия после остановки робота
    await cursor.close()
    await cnxn.close()
    print("Робот остановлен")
    ROBOT_START, ROBOT_STOP = False, False
    lbl_msg_robot["text"] = 'Робот остановлен'
    if APP_EXIT:
        sys.exit()


async def send_mail(cnxn, cursor, emails_data):
    # отправляет почту
    smtp_client = SMTP(hostname=HOST, port=PORT, use_tls=True, username=MY_ADDRESS, password=PASSWORD)
    await smtp_client.connect() 
    for e in emails_data:
        # e =  (1, 'test1', 'This is the test message 1!', 'testbox283@yandex.ru; testbox283@mail.ru')
        print("НОВОЕ СООБЩЕНИЕ  ", e)  ### test
        addrs = e[3].split(';')
        for a in addrs:
            msg = f'To: {a.strip()}\nFrom: {MY_ADDRESS}\nSubject: {e[1]}\n\n{e[2]}'.encode("utf-8")
            await smtp_client.sendmail(MY_ADDRESS, a.strip(), msg)
            log_rec = f'send message to {a.strip()} [ id = {e[0]} ]'
            await rec_to_log(log_rec)
        await db_emails_rec_date(cnxn, cursor, id=e[0])
        print('SEND MAIL IS OK!!!')
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
        print('НЕТ НОВЫХ ОПОВЕЩЕНИЙ О НЕДОСТАВЛЕННОЙ ПОЧТЕ')    ###
        await imap_client.close()
        await imap_client.logout()
        return []
    print(f'ПОЛУЧЕНО {l} ОПОВЕЩЕНИЙ О НЕДОСТАВЛЕННОЙ ПОЧТЕ')    ###
    msg_nums = msg_nums.replace(' ', ',')
    typ, data = await imap_client.fetch(msg_nums, '(UID BODY[TEXT])')

    undelivered = []
    for m in range(1, len(data), 3):
        msg = email.message_from_bytes(data[m])
        msg = msg.get_payload()
        msg_arrival_date = re.search(r'(?<=Arrival-Date: ).*', msg)[0].strip()
        msg_recipient = re.search(r'(?<=Original-Recipient: rfc822;).*', msg)[0].strip()
        print(msg_arrival_date, msg_recipient)  ###
        undelivered.append((msg_arrival_date, msg_recipient))

    await imap_client.close()
    await imap_client.logout()

    print(undelivered)  ###
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

#async def rec_to_log(receiver, id):
async def rec_to_log(rec):
    # пишет в лог-файл запись об отправке сообщения
    current_time = str(datetime.datetime.now())
    #rec = f'{current_time}  --  send message to {receiver} [ id = {id} ]\n'
    with open('log-mailsender.log', 'a') as f:
        f.write(f'{current_time}  --  {rec}\n')

async def db_emails_query(cursor):
    # выборка из базы данных необработанных (новых) записей
    if IS_MOCK_DB:
        rows = await mock_db_emails_query()
    else:
        #await cursor.execute(f'select id, msg_subject, msg_text, receivers from {DB_TABLE} where handling_date is null')
        await cursor.execute(f'select UniqueIndexField, subj, textemail, adrto from {DB_TABLE} where dates is null')
        rows = await cursor.fetchall()  # список кортежей
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

# ============== window sign in
root = tk.Tk()
root.title('MailSender')
frm = tk.Frame(bg=THEME_COLOR, width=400, height=400)
lbl_sign = tk.Label(master=frm, text='Sign in to MailSender', bg=LBL_COLOR, font=("Arial", 15), width=20, height=2)
lbl_user = tk.Label(master=frm, text='Username', bg=LBL_COLOR, font=("Arial", 12), anchor='w', width=25, height=2)
ent_user = tk.Entry(master=frm, bg=ENT_COLOR, font=("Arial", 12), width=25, )
lbl_password = tk.Label(master=frm, text='Password', bg=LBL_COLOR, font=("Arial", 12), anchor='w', width=25, height=2)
ent_password = tk.Entry(master=frm, bg=ENT_COLOR, font=("Arial", 12), width=25, )
btn_sign = tk.Button(master=frm, bg=BTN_COLOR, fg='White', text='Sign in', font=("Arial", 12, "bold"), 
                    width=22, height=1, command=lambda: loop.create_task(btn_sign_click()))
lbl_msg_sign = tk.Label(master=frm, bg=LBL_COLOR, fg='PaleVioletRed', font=("Arial", 12), width=25, height=2)

async def show():
    #
    await window_signin()
    while not SIGN_IN_FLAG:
        root.update()
        await asyncio.sleep(.1)

development_mode = False     # True - для разработки окна робота переход сразу на него без sign in
if development_mode:    # для разработки окна робота переход сразу на него без sign in
    SIGN_IN_FLAG = True
else:
    loop = asyncio.get_event_loop()
    loop.run_until_complete(show())

# выход из приложения если принудительно закрыто окно логина
# c asyncio не работает, надо выяснять!
if not SIGN_IN_FLAG:
    print('SIGN IN FALSE')
    #print('loop = ', loop)
    sys.exit()


# ============== window robot
root_robot = tk.Tk()
root_robot.title('MailSender')
frm = tk.Frame(bg=THEME_COLOR, width=400, height=400)
lbl_robot = tk.Label(master=frm, text='MailSender', bg=LBL_COLOR, font=("Arial", 15), width=20, height=2)

animation = "░▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒"
lbl_runner = tk.Label(master=frm, fg='DodgerBlue', text="")

btn_robot_run = tk.Button(master=frm, bg=BTN_2_COLOR, fg='White', text='Запуск робота', font=("Arial", 12, "bold"), 
                    width=22, height=1, command=lambda: loop_robot.create_task(btn_robot_run_click()))
btn_robot_stop = tk.Button(master=frm, bg=BTN_3_COLOR, fg='White', text='Остановка робота', font=("Arial", 12, "bold"), 
                    width=22, height=1, command=lambda: loop_robot.create_task(btn_robot_stop_click()))
btn_exit = tk.Button(master=frm, bg=BTN_1_COLOR, fg='Black', text='Выход', font=("Arial", 12), 
                    width=16, height=1, command=lambda: loop_robot.create_task(btn_exit_click()))
lbl_msg_robot = tk.Label(master=frm, bg=LBL_COLOR, font=("Arial", 10), width=25, height=2)

async def show_robot():
    #
    global animation

    await window_robot()
    while True:
        lbl_runner["text"] = animation
        if ROBOT_START:
            animation = animation[1:] + animation[0]

        root_robot.update()
        await asyncio.sleep(.1)

loop_robot = asyncio.get_event_loop()
loop_robot.run_until_complete(show_robot())
