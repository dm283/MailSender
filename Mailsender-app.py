import configparser
import tkinter as tk
import smtplib, ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import pyodbc
from time import sleep
import datetime
import json

config = configparser.ConfigParser()
config.read('config.ini')

IS_MOCK_DB = True if config['database']['is_mock_db'] == 'True' else False # для локального тестирования приложение работает с симулятором базы данных файл mock-db.json
CONNECTION_STRING = f"DSN={config['database']['dsn']}"  # odbc driver system dsn name
CHECK_DB_PERIOD = int(config['common']['check_db_period'])  # период проверки новых записей в базе данных

MY_ADDRESS, PASSWORD = config['smtp_server']['my_address'], config['smtp_server']['password']
HOST, PORT = config['smtp_server']['host'], config['smtp_server']['port']
RECEIVER_TEST_MESSAGE = config['smtp_server']['receiver_test_message']

SIGN_IN_FLAG = False
THEME_COLOR = 'Gainsboro'
LBL_COLOR = THEME_COLOR
ENT_COLOR = 'White'
BTN_COLOR = 'Green'
BTN_1_COLOR = 'Green'
BTN_2_COLOR = 'OrangeRed'
BTN_3_COLOR = 'SlateGray'


# === INTERFACE FUNCTIONS ===
def btn_sign_click():
    # кнопка sign-in
    global SIGN_IN_FLAG
    user = ent_user.get()
    password = ent_password.get()
    if user == 'admin' and password == 'admin':
        lbl_msg_sign["text"] = ''
        SIGN_IN_FLAG = True
        window.destroy()
    else:
        lbl_msg_sign["text"] = 'Incorrect username or password'

def btn_test_click():
    # кнопка Send test email
    test_send_email()
    lbl_msg_admin["text"] = f'Test e-mail was send to \n {RECEIVER_TEST_MESSAGE}'

def btn_robot_run_click():
    # кнопка Start robot
    lbl_msg_admin["text"] = 'Robot start'
    robot()

def btn_robot_stop_click():
    # кнопка Stop robot
    lbl_msg_admin["text"] = 'Robot stop'

def window_signin():
    # рисует окно входа
    frm.pack()
    lbl_sign.place(x=95, y=30)
    lbl_user.place(x=95, y=83)
    ent_user.place(x=95, y=126)
    lbl_password.place(x=95, y=150)
    ent_password.place(x=95, y=193)
    btn_sign.place(x=95, y=250)
    lbl_msg_sign.place(x=95, y=300)

def window_admin():
    # рисует окно админки
    frm.pack()
    lbl_admin.place(x=95, y=30)
    btn_robot_run.place(x=95, y=93)
    btn_robot_stop.place(x=95, y=136)
    btn_test.place(x=125, y=195)
    lbl_msg_admin.place(x=95, y=245)

# === EMAIL FUNCTIONS ===
def test_send_email():
    # отправляет тестовое сообщение
    context = ssl.create_default_context()

    with smtplib.SMTP_SSL(HOST, PORT, context=context) as server:
        server.login(MY_ADDRESS, PASSWORD)
        msg = MIMEMultipart()       
        message = 'this is test for send'
        msg['From']= MY_ADDRESS
        msg['To'] = RECEIVER_TEST_MESSAGE
        msg['Subject'] = 'test send'
        msg.attach(MIMEText(message, 'plain'))
        server.send_message(msg)

def robot():
    # стартует сервис отправки сообщений из базы данных
    print('MOCK_DB =', IS_MOCK_DB, type(IS_MOCK_DB))
    if IS_MOCK_DB:
        #  при IS_MOCK_DB приложение работает с mock-database (файл mock-db.json)
        create_mock_db()
        cnxn, cursor = '', ''
    else:
        cnxn = pyodbc.connect(CONNECTION_STRING)
        cursor = cnxn.cursor()
        print('Создано подключение к базе данных.')  ###

    while True:
        emails_data = db_emails_query(cursor)
        if len(emails_data) > 0:
            send_mail(cnxn, cursor, emails_data)
        else:
            print('НЕТ НОВЫХ СООБЩЕНИЙ')  ### test
        sleep(CHECK_DB_PERIOD)

def send_mail(cnxn, cursor, emails_data):
    # отправляет e-mail сообщения
    context = ssl.create_default_context()

    with smtplib.SMTP_SSL(HOST, PORT, context=context) as server:
        server.login(MY_ADDRESS, PASSWORD)
        for e in emails_data:
            print("НОВОЕ СООБЩЕНИЕ  ", e)  ### test
            addrs = e[3].split(';')
            for a in addrs:
                msg = MIMEMultipart()       
                message = e[2]
                msg['From']= MY_ADDRESS
                msg['To'] = a.strip()
                msg['Subject'] = e[1]
                msg.attach(MIMEText(message, 'plain'))
                server.send_message(msg)
                rec_to_log(a.strip(), e[0])
            db_emails_rec_date(cnxn, cursor, id=e[0])

# === DATABASE FUNCTIONS ===
def db_emails_query(cursor):
    # выборка из базы данных записей с e-mail
    if IS_MOCK_DB:
        rows = mock_db_emails_query()
    else:
        cursor.execute('select id, msg_subject, msg_text, receivers from mailsender_db.dbo.emails where handling_date is null')
        rows = cursor.fetchall()  # список кортежей
    return rows

def db_emails_rec_date(cnxn, cursor, id):
    # пишет в базу дату/время отправки сообщения
    if IS_MOCK_DB:
        mock_db_emails_rec_date(id)
    else:
        cursor.execute(f'update mailsender_db.dbo.emails set handling_date = getdate() where id = {id}')
        cnxn.commit()

def rec_to_log(receiver, id):
    # пишет в лог-файл запись об отправке сообщения
    current_time = str(datetime.datetime.now())
    rec = f'{current_time}  --  send message to {receiver} [ id = {id} ]\n'
    with open('log-mailsender.log', 'a') as f:
        f.write(rec)

def create_mock_db():
    # создает mock-database при запуске приложения, если IS_MOCK_DB = True
    data = {'emails': [
        {'id': 1, 'msg_subject': 'test1', 'msg_text': 'This is the test message 1!', 'receivers': 'testbox283@yandex.ru; testbox283@mail.ru', 'handling_date': None}, 
        {'id': 2, 'msg_subject': 'test2', 'msg_text': 'This is the test message 2!', 'receivers': 'testbox283@yandex.ru; testbox283@mail.ru', 'handling_date': None}, 
        {'id': 3, 'msg_subject': 'test3', 'msg_text': 'This is the test message 3!', 'receivers': 'testbox283@yandex.ru; testbox283@mail.ru', 'handling_date': None}
        ]}
    with open('mock-db.json', 'w') as f:
        json.dump(data, f)
    print('Создана MOCK база данных  -  файл mock-db.json')

def mock_db_emails_query():
    # mock-аналог select * from data where handling_date is null
    rows = []
    with open('mock-db.json') as f:
        data = json.load(f)
    for i in data['emails']:
        if not i['handling_date']:
            row = (i['id'], i['msg_subject'], i['msg_text'], i['receivers'])
            rows.append(row)
    return rows

def mock_db_emails_rec_date(id):
    # mock-аналог f'update mailsender_db.dbo.emails set handling_date = getdate() where id = {id}'
    with open('mock-db.json', 'r+') as f:
        data = json.load(f)
        for i in range( len(data['emails']) ):
            if data['emails'][i]['id'] == id and not data['emails'][i]['handling_date']:
                data['emails'][i]['handling_date'] = str(datetime.datetime.now())
                f.seek(0)
                json.dump(data, f)

# ============== window sign in
window = tk.Tk()
window.title('MailSender')

frm = tk.Frame(master=window, bg=THEME_COLOR, width=400, height=400)

lbl_sign = tk.Label(master=frm, text='Sign in to MailSender', bg=LBL_COLOR, font=("Arial", 15), width=20, height=2)
lbl_user = tk.Label(master=frm, text='Username', bg=LBL_COLOR, font=("Arial", 12), anchor='w', width=25, height=2)
ent_user = tk.Entry(master=frm, bg=ENT_COLOR, font=("Arial", 12), width=25, )
lbl_password = tk.Label(master=frm, text='Password', bg=LBL_COLOR, font=("Arial", 12), anchor='w', width=25, height=2)
ent_password = tk.Entry(master=frm, bg=ENT_COLOR, font=("Arial", 12), width=25, )
btn_sign = tk.Button(master=frm, bg=BTN_COLOR, fg='White', text='Sign in', font=("Arial", 12, "bold"), 
                    width=22, height=1, command=btn_sign_click)
lbl_msg_sign = tk.Label(master=frm, bg=LBL_COLOR, fg='PaleVioletRed', font=("Arial", 12), width=25, height=2)

window_signin()

window.mainloop()

if not SIGN_IN_FLAG:
    quit()

# ============== window admin
window = tk.Tk()
window.title('MailSender')

frm = tk.Frame(master=window, bg=THEME_COLOR, width=400, height=400)

lbl_admin = tk.Label(master=frm, text='MailSender', bg=LBL_COLOR, font=("Arial", 15), width=20, height=2)
btn_robot_run = tk.Button(master=frm, bg=BTN_2_COLOR, fg='White', text='Start robot', font=("Arial", 12, "bold"), 
                    width=22, height=1, command=btn_robot_run_click)
btn_robot_stop = tk.Button(master=frm, bg=BTN_3_COLOR, fg='White', text='Stop robot', font=("Arial", 12, "bold"), 
                    width=22, height=1, command=btn_robot_stop_click)
btn_test = tk.Button(master=frm, bg=BTN_1_COLOR, fg='Black', text='Send test e-mail', font=("Arial", 12), 
                    width=16, height=1, command=btn_test_click)
lbl_msg_admin = tk.Label(master=frm, bg=LBL_COLOR, font=("Arial", 12), width=25, height=2)

window_admin()

window.mainloop()
