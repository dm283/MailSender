import configparser
import tkinter as tk
from tkinter import ttk
import asyncio
from aiosmtplib import SMTP
import datetime
import json
import aioodbc

config = configparser.ConfigParser()
config.read('config.ini')

IS_MOCK_DB = True if config['database']['is_mock_db'] == 'True' else False # для локального тестирования приложение работает с симулятором базы данных файл mock-db.json
DB = config['database']['db']  # база данных mssql/posgres
DB_TABLE = config['database']['db_table']  # db.schema.table
CONNECTION_STRING = f"DSN={config['database']['dsn']}"  # odbc driver system dsn name
CHECK_DB_PERIOD = int(config['common']['check_db_period'])  # период проверки новых записей в базе данных

MY_ADDRESS, PASSWORD = config['smtp_server']['my_address'], config['smtp_server']['password']
HOST, PORT = config['smtp_server']['host'], config['smtp_server']['port']
RECEIVER_TEST_MESSAGE = config['smtp_server']['receiver_test_message']
TEST_MESSAGE = f"""To: {RECEIVER_TEST_MESSAGE}\nFrom: {MY_ADDRESS}\nSubject: ***AioSmtplib TEST message***\n\nThis is the test message sent via aiosmtplib and tkinter async"""

SIGN_IN_FLAG = False
THEME_COLOR = 'Gainsboro'
LBL_COLOR = THEME_COLOR
ENT_COLOR = 'White'
BTN_COLOR = 'Green'
BTN_1_COLOR = 'Green'
BTN_2_COLOR = 'OrangeRed'
BTN_3_COLOR = 'SlateGray'

# === INTERFACE FUNCTIONS ===
async def btn_sign_click():
    # кнопка sign-in
    global SIGN_IN_FLAG
    user = ent_user.get()
    password = ent_password.get()
    if user == 'admin' and password == 'admin':
        lbl_msg_sign["text"] = ''
        SIGN_IN_FLAG = True
        root.destroy()
    else:
        lbl_msg_sign["text"] = 'Incorrect username or password'

async def btn_test_click():
    # кнопка Send test email
    await test_send_email()
    lbl_msg_admin["text"] = f'Test e-mail was send to \n {RECEIVER_TEST_MESSAGE}'

async def btn_robot_run_click():
    # кнопка Start robot
    lbl_msg_admin["text"] = 'Robot start'
    await robot()

async def btn_robot_stop_click():
    # кнопка Stop robot
    lbl_msg_admin["text"] = 'Robot stop'

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

async def window_admin():
    # рисует окно админки
    frm.pack()
    lbl_admin.place(x=95, y=30)
    btn_robot_run.place(x=95, y=93)
    btn_robot_stop.place(x=95, y=136)
    btn_test.place(x=125, y=195)
    lbl_msg_admin.place(x=95, y=245)

# === EMAIL FUNCTIONS ===
async def test_send_email():
    # отправляет тестовое сообщение
    print(' test msg is sending...')
    smtp_client = SMTP(hostname=HOST, port=PORT, use_tls=True, username=MY_ADDRESS, password=PASSWORD)
    await smtp_client.connect()
    await smtp_client.sendmail(MY_ADDRESS, RECEIVER_TEST_MESSAGE, TEST_MESSAGE)
    await smtp_client.quit()
    print('TEST MSG WAS SEND!')

async def robot():
    # стартует сервис отправки сообщений из базы данных
    print('MOCK_DB =', IS_MOCK_DB, type(IS_MOCK_DB))
    if IS_MOCK_DB:
        #  при IS_MOCK_DB приложение работает с mock-database (файл mock-db.json)
        await create_mock_db()
        cnxn, cursor = '', ''
    else:
        cnxn = await aioodbc.connect(dsn=CONNECTION_STRING, loop=loop_admin)
        cursor = await cnxn.cursor()
        print(f'Создано подключение к базе данных {DB}')  ###

    while True:
        emails_data = await db_emails_query(cursor)
        print(emails_data)
        print()
        if len(emails_data) > 0:
            await send_mail(cnxn, cursor, emails_data)
        else:
            print('НЕТ НОВЫХ СООБЩЕНИЙ')  ### test
        await asyncio.sleep(CHECK_DB_PERIOD)

async def send_mail(cnxn, cursor, emails_data):
    smtp_client = SMTP(hostname=HOST, port=PORT, use_tls=True, username=MY_ADDRESS, password=PASSWORD)
    await smtp_client.connect() 
    for e in emails_data:
        # e =  (1, 'test1', 'This is the test message 1!', 'testbox283@yandex.ru; testbox283@mail.ru')
        print("НОВОЕ СООБЩЕНИЕ  ", e)  ### test
        addrs = e[3].split(';')
        for a in addrs:
            msg = f'To: {a.strip()}\nFrom: {MY_ADDRESS}\nSubject: {e[1]}\n\n{e[2]}'
            await smtp_client.sendmail(MY_ADDRESS, a.strip(), msg)
            await rec_to_log(a.strip(), e[0])
        await db_emails_rec_date(cnxn, cursor, id=e[0])
        print('SEND MAIL IS OK!!!')
    await smtp_client.quit()

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

async def rec_to_log(receiver, id):
    # пишет в лог-файл запись об отправке сообщения
    current_time = str(datetime.datetime.now())
    rec = f'{current_time}  --  send message to {receiver} [ id = {id} ]\n'
    with open('log-mailsender.log', 'a') as f:
        f.write(rec)

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
        {'UniqueIndexField': 2, 'subj': 'test2', 'textemail': 'This is the test message 2!', 'adrto': 'testbox283@yandex.ru; testbox283@mail.ru', 'dates': None}, 
        {'UniqueIndexField': 3, 'subj': 'test3', 'textemail': 'This is the test message 3!', 'adrto': 'testbox283@yandex.ru; testbox283@mail.ru', 'dates': None}
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

loop = asyncio.get_event_loop()
loop.run_until_complete(show())

# выход из приложения если принудительно закрыто окно логина
# c asyncio не работает, надо выяснять!
if not SIGN_IN_FLAG:
    print('SIGN IN FALSE')
    print('loop = ', loop)
    quit()


# ============== window admin
root_admin = tk.Tk()
root_admin.title('MailSender')
frm = tk.Frame(bg=THEME_COLOR, width=400, height=400)
lbl_admin = tk.Label(master=frm, text='MailSender', bg=LBL_COLOR, font=("Arial", 15), width=20, height=2)
btn_robot_run = tk.Button(master=frm, bg=BTN_2_COLOR, fg='White', text='Start robot', font=("Arial", 12, "bold"), 
                    width=22, height=1, command=lambda: loop_admin.create_task(btn_robot_run_click()))
btn_robot_stop = tk.Button(master=frm, bg=BTN_3_COLOR, fg='White', text='Stop robot', font=("Arial", 12, "bold"), 
                    width=22, height=1, command=lambda: loop_admin.create_task(btn_robot_stop_click()))
btn_test = tk.Button(master=frm, bg=BTN_1_COLOR, fg='Black', text='Send test e-mail', font=("Arial", 12), 
                    width=16, height=1, command=lambda: loop_admin.create_task(btn_test_click()))
lbl_msg_admin = tk.Label(master=frm, bg=LBL_COLOR, font=("Arial", 12), width=25, height=2)

async def show_admin():
    #
    await window_admin()
    while True:
        root_admin.update()
        await asyncio.sleep(.1)

loop_admin = asyncio.get_event_loop()
loop_admin.run_until_complete(show_admin())
