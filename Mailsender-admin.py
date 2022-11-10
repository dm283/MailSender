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

# загрузка конфигурации
CONFIG_FILE = 'config.ini'
config = configparser.ConfigParser()
config.read(CONFIG_FILE, encoding='utf-8')

# загрузка крипто ключа
with open('rec-k.txt') as f:
    rkey = f.read().encode('utf-8')
refKey = Fernet(rkey)

# расшифровка паролей
password_section_key_list = [ ('user_credentials', 'password'), ('admin_credentials', 'password'), ('smtp_server', 'password'), ]
for s in password_section_key_list:
    hashed = config[s[0]][s[1]]
    config[s[0]][s[1]] = (refKey.decrypt(hashed).decode('utf-8')) if hashed != '' else config[s[0]][s[1]]

TEST_MESSAGE = f"""To: {config['common']['admin_email']}\nFrom: {config['smtp_server']['my_address']}
Subject: Mailsender - тестовое сообщение\n
Это тестовое сообщение отправленное сервисом Mailsender.""".encode('utf8')
UNDELIVERED_MESSAGE = f"""To: {config['common']['admin_email']}\nFrom: {config['smtp_server']['my_address']}
Subject: Mailsender - недоставленное сообщение\n
Это сообщение отправленно сервисом Mailsender.\n""".encode('utf8')

SIGN_IN_FLAG = False

THEME_COLOR = 'White' #'Gainsboro'
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
    if user == config['admin_credentials']['name'] and password == config['admin_credentials']['password']:
        lbl_msg_sign["text"] = ''
        SIGN_IN_FLAG = True
        root.destroy()
    else:
        lbl_msg_sign["text"] = 'Incorrect username or password'

async def show_password_signin():
    # показывает/скрывает пароль в окне входа
    ent_password['show'] = '' if(cbt_sign_show_pwd_v1.get() == 1) else '*'
        
async def show_password(s, k):
    # показывает/скрывает пароль
    ent[s][k]['show'] = '' if(cbt_v1[s][k].get() == 1) else '*'

async def btn_test_db_click():
    # тестирует подключение к базе данных
    if config['database'].getboolean('is_mock_db'):
        #  при IS_MOCK_DB приложение работает с mock-database (файл mock-db.json)
        lbl_msg_test_db['text'] = 'Используется mock-database'
        await asyncio.sleep(1)
        return
    else:
        lbl_msg_test_db['text'] = f"Подключение к базе данных {config['database']['db']} ....."
        await asyncio.sleep(1)
        try:
            cnxn = await aioodbc.connect(dsn=config['database']['connection_string'], loop=loop_admin)
            cursor = await cnxn.cursor()
            lbl_msg_test_db['text'] = f"Подключение к базе данных {config['database']['db']}  -  OK"
            await asyncio.sleep(1)
            try:
                lbl_msg_test_db['text'] = f"Обращение к таблице {config['database']['db_table']} ....."
                await cursor.execute(f"select UniqueIndexField, subj, textemail, adrto from {config['database']['db_table']} where dates is null")
                await cursor.fetchall()
                lbl_msg_test_db['text'] = f"Обращение к таблице {config['database']['db_table']}  -  OK"
                await asyncio.sleep(1)
                lbl_msg_test_db['text'] = 'Тестирование успешно завершено'
            except:
                lbl_msg_test_db['text'] = f"Обращение к таблице {config['database']['db_table']}  -  ошибка"
            await cursor.close()
            await cnxn.close()
        except:
            lbl_msg_test_db['text'] = f"Подключение к базе данных {config['database']['db']}  -  ошибка"

async def btn_test_smtp_click():
    # тестирует подключение к smtp-серверу: доступность smtp-сервера и отправка тестового сообщения
    lbl_msg_test_smtp['text'] = f"Подключение к {config['smtp_server']['host']}: {config['smtp_server']['port']} ....."
    try:
        smtp_client = SMTP(hostname=config['smtp_server']['host'], 
                    port=config['smtp_server']['port'], 
                    use_tls=True, 
                    username=config['smtp_server']['my_address'], 
                    password=config['smtp_server']['password'])
        await smtp_client.connect()
        lbl_msg_test_smtp['text'] = f"Подключение к {config['smtp_server']['host']}: {config['smtp_server']['port']}  -  OK"
        await asyncio.sleep(1)
        try:
            lbl_msg_test_smtp['text'] = f"Отправка тестового сообщения на почту {config['common']['admin_email']} ....."
            await smtp_client.sendmail(config['smtp_server']['my_address'], config['common']['admin_email'], TEST_MESSAGE)
            lbl_msg_test_smtp['text'] = 'Тестовое сообщение успешно отправлено'
            await asyncio.sleep(1)
            await smtp_client.quit()
            lbl_msg_test_smtp['text'] = 'Тестирование успешно завершено'
        except:
            lbl_msg_test_smtp['text'] = 'Отправка тестового сообщения  -  ошибка'
    except:
        lbl_msg_test_smtp['text'] = f"Подключение к {config['smtp_server']['host']}:{config['smtp_server']['port']}  -  ошибка"

async def btn_test_imap_click():
    # тестирует подключение к imap-сервер
    lbl_msg_test_imap['text'] = f"Подключение к {config['imap_server']['host']}: {config['imap_server']['port']} ....."
    try:
        imap_client = aioimaplib.IMAP4_SSL(host=config['imap_server']['host'])  # не ловиться исключение здесь!
        await imap_client.wait_hello_from_server()
        lbl_msg_test_imap['text'] = f"Подключение к {config['imap_server']['host']}: {config['imap_server']['port']}  -  OK"
        await asyncio.sleep(1)
        try:
            await imap_client.login(config['smtp_server']['my_address'], config['smtp_server']['password'])
            await imap_client.select('INBOX')
            lbl_msg_test_imap['text'] = f'Чтение входящих сообщений  -  OK'
            await asyncio.sleep(1)
            await imap_client.close()
            await imap_client.logout()
            lbl_msg_test_imap['text'] = 'Тестирование успешно завершено'
        except:
                lbl_msg_test_imap['text'] = f'Чтение входящих сообщений  -  ошибка'
    except:
        lbl_msg_test_imap['text'] = f"Подключение к {config['imap_server']['host']}:{config['imap_server']['port']}  -  ошибка"

async def btn_save_config_click():
    global config
    # сохраняет установленные значения конфига
    for s in config.sections():
        for k, v in config.items(s):
            # описания секций остаются неизменными
            if k == 'section_description':
                continue
            if (s, k) in password_section_key_list:
                # если параметр подлежит шифрованию - хэширование перед записью в config
                scrt_value = ent[s][k].get().encode('utf-8')
                hashed_scrt_value = refKey.encrypt(scrt_value)
                config[s][k] = hashed_scrt_value.decode('utf-8')
            else:
                # обычный параметр
                config[s][k] = ent[s][k].get()
    with open(CONFIG_FILE, 'w', encoding='utf-8') as configfile:
        config.write(configfile)
    lbl_config_msg['text'] = f'Конфигурация сохранена в файл {CONFIG_FILE}'
    # после сохранения конфига сообщения о тестировании обнуляются
    lbl_msg_test_imap['text'], lbl_msg_test_smtp['text'], lbl_msg_test_db['text'] = '', '', ''
    # запись в переменную расшифрованного пароля (инче остается хэшированный, который нельзя использовать)
    for (s, k) in password_section_key_list:
        config[s][k] = ent[s][k].get()

async def show_signin():
    # рисует окно входа
    frm.pack()
    lbl_sign.place(x=95, y=30)
    lbl_user.place(x=95, y=83)
    ent_user.place(x=95, y=126)
    lbl_password.place(x=95, y=150)
    ent_password.place(x=95, y=193)
    cbt_sign_show_pwd.place(x=95, y=220)
    btn_sign.place(x=95, y=260)
    lbl_msg_sign.place(x=95, y=310)
    while not SIGN_IN_FLAG:
        root.update()
        await asyncio.sleep(.1)

async def show_admin():
    # рисует окно администрирования
    notebook.pack(padx=10, pady=10, fill='both', expand=True)
    for s in config.sections():
        notebook.add(frm[s], text = s)
        frm_params[s].pack(padx=5, pady=(5, 0), fill='both', expand=True)
        frm_test[s].pack(padx=5, pady=(1, 5), fill='both', expand=True)
        lbl[s]['section_description'].grid(row = 0, columnspan = 3, sticky = 'w', padx = 5, pady = 5)
        r = 1
        for k, v in config.items(s):
            if k == 'section_description':
                continue
            lbl[s][k].grid(row = r, column = 0, sticky = 'w', padx = 5, pady = 5)
            ent[s][k].grid(row = r, column = 1, sticky = 'w', padx = 5, pady = 5)
            ent[s][k].insert(0, v)
            if (s, k) in password_section_key_list:
                cbt[s][k].grid(row = r, column = 2, sticky = 'w', )
            r += 1
        if s == 'database':
            btn_test_db.grid(row = 0, column = 0, padx = 5, pady = 5)
            lbl_msg_test_db.grid(row = 0, column = 1, padx = 5, pady = 5)
        elif s == 'smtp_server':
            btn_test_smtp.grid(row = 0, column = 0, padx = 5, pady = 5)
            lbl_msg_test_smtp.grid(row = 0, column = 1, padx = 5, pady = 5)
        elif s == 'imap_server':
            btn_test_imap.place(x=5, y=19)
            lbl_msg_test_imap.place(x=130, y=21)

    frm_footer.pack(padx=10, pady=(0, 10), fill='both', expand=True)  
    btn_save_config.grid(row = 0, column = 0)
    lbl_config_msg.grid(row = 0, column = 1, padx = 10)

    while True:
        root_admin.update()
        await asyncio.sleep(.1)



# ============== window sign in
root = tk.Tk()
root.title('MailSender administration panel')
frm = tk.Frame(bg=THEME_COLOR, width=400, height=400)
lbl_sign = tk.Label(master=frm, text='Sign in to MailSender', bg=LBL_COLOR, font=("Arial", 15), width=20, height=2)
lbl_user = tk.Label(master=frm, text='Username', bg=LBL_COLOR, font=("Arial", 12), anchor='w', width=25, height=2)
ent_user = tk.Entry(master=frm, bg=ENT_COLOR, font=("Arial", 12), width=25, )
lbl_password = tk.Label(master=frm, text='Password', bg=LBL_COLOR, font=("Arial", 12), anchor='w', width=25, height=2)
ent_password = tk.Entry(master=frm, show = '*', bg=ENT_COLOR, font=("Arial", 12), width=25, )

cbt_sign_show_pwd_v1 = tk.IntVar(value = 0)
cbt_sign_show_pwd = tk.Checkbutton(frm, bg=THEME_COLOR, text='Show password', variable=cbt_sign_show_pwd_v1, onvalue=1, offvalue=0, 
                                    command=lambda: loop.create_task(show_password_signin()))

btn_sign = tk.Button(master=frm, bg=BTN_COLOR, fg='White', text='Sign in', font=("Arial", 12, "bold"), 
                    width=22, height=1, command=lambda: loop.create_task(btn_sign_click()))
lbl_msg_sign = tk.Label(master=frm, bg=LBL_COLOR, fg='PaleVioletRed', font=("Arial", 12), width=25, height=2)

development_mode = False     # True - для разработки окна робота переход сразу на него без sign in
if development_mode:    # для разработки окна робота переход сразу на него без sign in
    SIGN_IN_FLAG = True
else:
    loop = asyncio.get_event_loop()
    loop.run_until_complete(show_signin())

# выход из приложения если принудительно закрыто окно логина
# c asyncio не работает, надо выяснять!
if not SIGN_IN_FLAG:
    print('SIGN IN FALSE')
    #print('loop = ', loop)
    sys.exit()

# ============== window admin
root_admin = tk.Tk()
root_admin.title('MailSender administration panel')
notebook = ttk.Notebook(root_admin)

# в каждом Frame (section) создаются подфреймы с Labels и Enrty (key и key-value)
frm, frm_params, frm_test, lbl, ent = {}, {}, {}, {}, {}

for s in config.sections():
    frm[s], lbl[s], ent[s] = tk.Frame(notebook, bg=THEME_COLOR, width=400, ), {}, {}
    
    frm_params[s] = tk.Frame(frm[s], bg=THEME_COLOR, width=400, )
    frm_test[s] = tk.Frame(frm[s], bg=THEME_COLOR, width=400, )

    for k, v in config.items(s):
        if k == 'section_description':
            lbl[s][k] = tk.Label(frm_params[s], bg=THEME_COLOR, text = v, )
            continue
        lbl[s][k] = tk.Label(frm_params[s], bg=THEME_COLOR, text = k, width=20, anchor='w', )
        ent[s][k] = tk.Entry(frm_params[s], width=30, highlightthickness=1, highlightcolor = "Gainsboro", )

# формирование виджетов для полей со скрытием контента
cbt_v1, cbt = {}, {}
for s, k in password_section_key_list:
    cbt_v1[s], cbt[s] = {}, {}
    cbt_v1[s][k] = tk.IntVar(value = 0)
    cbt[s][k] = tk.Checkbutton(frm_params[s], bg=THEME_COLOR, text = 'Show password', variable = cbt_v1[s][k], onvalue = 1, offvalue = 0)
    ent[s][k]['show'] = '*'
cbt['user_credentials']['password']['command'] = lambda: loop_admin.create_task(show_password('user_credentials', 'password'))
cbt['admin_credentials']['password']['command'] = lambda: loop_admin.create_task(show_password('admin_credentials', 'password'))
cbt['smtp_server']['password']['command'] = lambda: loop_admin.create_task(show_password('smtp_server', 'password'))

# формирование элемнтов с функционалом тестирования
btn_test_db = tk.Button(frm_test['database'], text='Тест', width = 15, command=lambda: loop_admin.create_task(btn_test_db_click()))
lbl_msg_test_db = tk.Label(frm_test['database'], bg=THEME_COLOR, width = 45, anchor='w', )

btn_test_smtp = tk.Button(frm_test['smtp_server'], text='Тест', width = 15, command=lambda: loop_admin.create_task(btn_test_smtp_click()))
lbl_msg_test_smtp = tk.Label(frm_test['smtp_server'], bg=THEME_COLOR, width = 45, anchor='w', )

btn_test_imap = tk.Button(frm_test['imap_server'], text='Тест', width = 15, command=lambda: loop_admin.create_task(btn_test_imap_click()))
lbl_msg_test_imap = tk.Label(frm_test['imap_server'], bg=THEME_COLOR, width = 45, anchor='w', )

# формирование фрейма с общим функционалом (сохранение конфига)
frm_footer = tk.Frame(root_admin, width=400, height=280, )
btn_save_config = tk.Button(frm_footer, text='Сохранить', width = 15, command=lambda: loop_admin.create_task(btn_save_config_click()))
lbl_config_msg = tk.Label(frm_footer, )


loop_admin = asyncio.get_event_loop()
loop_admin.run_until_complete(show_admin())
