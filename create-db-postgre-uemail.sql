CREATE DATABASE mailsender_db
    WITH
    ENCODING = 'UTF8'
    LC_COLLATE = 'Russian_Russia.1251'
    LC_CTYPE = 'Russian_Russia.1251'
    TABLESPACE = pg_default;
	
create table if not exists public.uemail(
	id varchar(8) NULL,
	app varchar(4) NULL,
	forms varchar(6) NULL,
	ids varchar(16) NULL,
	client int NULL,
	adrto varchar(500) NULL,
	subj varchar(100) NULL,
	textemail varchar(600) NULL,
	attachmentfiles varchar(255) NULL,
	guid_doc varchar(36) NULL,
	datep timestamp NULL,
	dates timestamp NULL,
	datet timestamp NULL,
	datef timestamp NULL,
	fl int NULL,
	user_id varchar(3) NULL,
	status int NULL,
	UniqueIndexField serial primary key
);

-------
insert into public.uemail (subj, textemail, adrto, datep) values
('test1_pg', 'This is the test message 1 pg !', 'testbox283@yandex.ru; testbox283@mail.ru', now()),
('test2_pg', 'This is the test message 2 pg !', 'testbox283@yandex.ru; testbox283@mail.ru', now()),
('test3_pg', 'This is the test message 3 pg !', 'testbox283@yandex.ru', now());

-- select UniqueIndexField, subj, textemail, adrto, datep, dates from mailsender_db.public.uemail order by UniqueIndexField desc

-- drop table mailsender_db.public.uemail;

-- update mailsender_db.public.uemail set dates = getdate()