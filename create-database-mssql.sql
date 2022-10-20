-- create database mailsender_db
USE master;
GO
IF DB_ID (N'mailsender_db') IS NOT NULL
DROP DATABASE mailsender_db;
GO
CREATE DATABASE mailsender_db;
GO

USE mailsender_db;

if object_id(N'dbo.emails_id_seq') is null
create sequence dbo.emails_id_seq  
    start with 1  
    increment by 1; 

if object_id(N'mailsender_db.dbo.emails') is null
create table mailsender_db.dbo.emails(
	id int primary key default next value for dbo.emails_id_seq,
	msg_subject varchar(8000) not null,
	msg_text varchar(8000) not null,
	receivers varchar(8000) not null,
	handling_date datetime default null,
);

insert into mailsender_db.dbo.emails (msg_subject, msg_text, receivers) values
('test1', 'This is the test message 1!', 'testbox283@yandex.ru; testbox283@mail.ru'),
('test2', 'This is the test message 2!', 'testbox283@yandex.ru; testbox283@mail.ru'),
('test3', 'This is the test message 3!', 'testbox283@mail.ru');

-- select * from mailsender_db.dbo.emails order by id desc
-- select next value for dbo.emails_id_seq

-- drop table dbo.emails;
-- drop sequence dbo.emails_id_seq;

-- update mytest.dbo.emails set handling_date = getdate()
