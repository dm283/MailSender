-- create database mailsender_db
USE master;
GO
IF DB_ID (N'mailsender_db') IS NULL
CREATE DATABASE mailsender_db;
GO

USE [mailsender_db]
GO

/****** Object:  Table [dbo].[uemail]    Script Date: 26.10.2022 18:35:52 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
SET ANSI_PADDING ON
GO

IF OBJECT_ID(N'mailsender_db.dbo.uemail') is null
CREATE TABLE [dbo].[uemail](
	[id] [varchar](8) NULL,
	[app] [varchar](4) NULL,
	[forms] [varchar](6) NULL,
	[ids] [varchar](16) NULL,
	[client] [int] NULL,
	[adrto] [varchar](500) NULL,
	[subj] [varchar](100) NULL,
	[textemail] [varchar](600) NULL,
	[attachmentfiles] [varchar](255) NULL,
	[guid_doc] [varchar](36) NULL,
	[datep] [datetime] NULL,
	[dates] [datetime] NULL,
	[datet] [datetime] NULL,
	[datef] [datetime] NULL,
	[fl] [int] NULL,
	[user_id] [varchar](3) NULL,
	[status] [int] NULL,
	[UniqueIndexField] [int] IDENTITY(10000,1) NOT NULL,
 CONSTRAINT [PK_uemail] PRIMARY KEY CLUSTERED 
(
	[UniqueIndexField] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON) ON [PRIMARY]
) ON [PRIMARY]

GO

SET ANSI_PADDING OFF
GO

-----------
insert into mailsender_db.dbo.uemail (subj, textemail, adrto, datep) values
('test1 uemail ms', 'This is the test message 1 uemail ms!', 'testbox283@yandex.ru; testbox283@mail.ru', getdate()),
('test2 uemail ms', 'This is the test message 2 uemail ms!', 'testbox283@yandex.ru; testbox283@mail.ru', getdate()),
('test3 uemail ms', 'This is the test message 3 uemail ms!', 'testbox283@mail.ru', getdate());

-- select UniqueIndexField, subj, textemail, adrto, datep, dates from mailsender_db.dbo.uemail order by UniqueIndexField desc

-- drop table mailsender_db.dbo.uemail;

-- update mailsender_db.dbo.uemail set dates = getdate()
