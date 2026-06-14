BEGIN TRANSACTION;
CREATE TABLE IF NOT EXISTS "auth_group" (
	"id"	integer NOT NULL,
	"name"	varchar(150) NOT NULL UNIQUE,
	PRIMARY KEY("id" AUTOINCREMENT)
);
CREATE TABLE IF NOT EXISTS "auth_group_permissions" (
	"id"	integer NOT NULL,
	"group_id"	integer NOT NULL,
	"permission_id"	integer NOT NULL,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("group_id") REFERENCES "auth_group"("id") DEFERRABLE INITIALLY DEFERRED,
	FOREIGN KEY("permission_id") REFERENCES "auth_permission"("id") DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE IF NOT EXISTS "auth_permission" (
	"id"	integer NOT NULL,
	"content_type_id"	integer NOT NULL,
	"codename"	varchar(100) NOT NULL,
	"name"	varchar(255) NOT NULL,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("content_type_id") REFERENCES "django_content_type"("id") DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE IF NOT EXISTS "author_profiles" (
	"id"	integer NOT NULL,
	"bio"	text NOT NULL,
	"website"	varchar(200) NOT NULL,
	"author_pseudonym"	varchar(100) NOT NULL,
	"facebook_url"	varchar(200) NOT NULL,
	"twitter_url"	varchar(200) NOT NULL,
	"instagram_url"	varchar(200) NOT NULL,
	"linkedin_url"	varchar(200) NOT NULL,
	"bank_account_name"	varchar(100) NOT NULL,
	"bank_account_number"	varchar(50) NOT NULL,
	"bank_name"	varchar(100) NOT NULL,
	"tax_id"	varchar(50) NOT NULL,
	"tin_number"	varchar(20) NOT NULL,
	"author_image"	varchar(100),
	"agreement_signed"	bool NOT NULL,
	"agreement_signed_at"	datetime,
	"verification_status"	varchar(20) NOT NULL,
	"verification_documents"	text NOT NULL,
	"verified_at"	datetime,
	"commission_rate"	decimal NOT NULL,
	"total_royalties_earned"	decimal NOT NULL,
	"total_paid"	decimal NOT NULL,
	"pending_payout"	decimal NOT NULL,
	"last_payment_date"	datetime,
	"total_books_published"	integer NOT NULL,
	"total_downloads"	integer NOT NULL,
	"created_at"	datetime NOT NULL,
	"updated_at"	datetime NOT NULL,
	"user_id"	bigint NOT NULL UNIQUE,
	"verified_by_id"	bigint,
	"agreement_version"	varchar(20) NOT NULL,
	"author_signature"	varchar(100),
	"average_rating"	decimal NOT NULL,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("user_id") REFERENCES "users"("id") DEFERRABLE INITIALLY DEFERRED,
	FOREIGN KEY("verified_by_id") REFERENCES "users"("id") DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE IF NOT EXISTS "books" (
	"id"	integer NOT NULL,
	"title"	varchar(255) NOT NULL,
	"subtitle"	varchar(255) NOT NULL,
	"description"	text NOT NULL,
	"language"	varchar(20) NOT NULL,
	"edition"	varchar(50) NOT NULL,
	"page_count"	integer NOT NULL,
	"publication_year"	integer NOT NULL,
	"price"	decimal NOT NULL,
	"is_free"	bool NOT NULL,
	"file"	varchar(100),
	"cover_image"	varchar(100),
	"sample_file"	varchar(100),
	"keywords"	text NOT NULL,
	"downloads_count"	integer NOT NULL,
	"purchase_count"	integer NOT NULL,
	"views_count"	integer NOT NULL,
	"avg_rating"	decimal NOT NULL,
	"total_reviews"	integer NOT NULL,
	"status"	varchar(20) NOT NULL,
	"revision_notes"	text NOT NULL,
	"revision_attempts"	integer NOT NULL,
	"submitted_for_review_at"	datetime,
	"checker_reviewed_at"	datetime,
	"maker_approved_at"	datetime,
	"published_at"	datetime,
	"created_at"	datetime NOT NULL,
	"updated_at"	datetime NOT NULL,
	"author_id"	bigint NOT NULL,
	"genre_id"	bigint,
	"isbn"	varchar(20) NOT NULL UNIQUE,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("author_id") REFERENCES "users"("id") DEFERRABLE INITIALLY DEFERRED,
	FOREIGN KEY("genre_id") REFERENCES "genres"("id") DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE IF NOT EXISTS "clients" (
	"id"	integer NOT NULL,
	"phone_number"	varchar(20) NOT NULL,
	"national_id_verified"	bool NOT NULL,
	"wallet_balance"	decimal NOT NULL,
	"total_purchases"	integer NOT NULL,
	"total_spent"	decimal NOT NULL,
	"preferred_genres"	text NOT NULL,
	"newsletter_subscribed"	bool NOT NULL,
	"created_at"	datetime NOT NULL,
	"updated_at"	datetime NOT NULL,
	"user_id"	bigint NOT NULL UNIQUE,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("user_id") REFERENCES "users"("id") DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE IF NOT EXISTS "django_admin_log" (
	"id"	integer NOT NULL,
	"object_id"	text,
	"object_repr"	varchar(200) NOT NULL,
	"action_flag"	smallint unsigned NOT NULL CHECK("action_flag" >= 0),
	"change_message"	text NOT NULL,
	"content_type_id"	integer,
	"user_id"	bigint NOT NULL,
	"action_time"	datetime NOT NULL,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("content_type_id") REFERENCES "django_content_type"("id") DEFERRABLE INITIALLY DEFERRED,
	FOREIGN KEY("user_id") REFERENCES "users"("id") DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE IF NOT EXISTS "django_content_type" (
	"id"	integer NOT NULL,
	"app_label"	varchar(100) NOT NULL,
	"model"	varchar(100) NOT NULL,
	PRIMARY KEY("id" AUTOINCREMENT)
);
CREATE TABLE IF NOT EXISTS "django_migrations" (
	"id"	integer NOT NULL,
	"app"	varchar(255) NOT NULL,
	"name"	varchar(255) NOT NULL,
	"applied"	datetime NOT NULL,
	PRIMARY KEY("id" AUTOINCREMENT)
);
CREATE TABLE IF NOT EXISTS "django_session" (
	"session_key"	varchar(40) NOT NULL,
	"session_data"	text NOT NULL,
	"expire_date"	datetime NOT NULL,
	PRIMARY KEY("session_key")
);
CREATE TABLE IF NOT EXISTS "genres" (
	"id"	integer NOT NULL,
	"name"	varchar(100) NOT NULL UNIQUE,
	"slug"	varchar(50) NOT NULL UNIQUE,
	"description"	text NOT NULL,
	"is_active"	bool NOT NULL,
	"created_at"	datetime NOT NULL,
	PRIMARY KEY("id" AUTOINCREMENT)
);
CREATE TABLE IF NOT EXISTS "notifications" (
	"id"	integer NOT NULL,
	"type"	varchar(20) NOT NULL,
	"title"	varchar(255) NOT NULL,
	"message"	text NOT NULL,
	"link"	varchar(500) NOT NULL,
	"is_read"	bool NOT NULL,
	"created_at"	datetime NOT NULL,
	"user_id"	bigint NOT NULL,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("user_id") REFERENCES "users"("id") DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE IF NOT EXISTS "payment_requests" (
	"id"	integer NOT NULL,
	"amount"	decimal NOT NULL,
	"currency"	varchar(3) NOT NULL,
	"payment_method"	varchar(20) NOT NULL,
	"bank_account_name"	varchar(100) NOT NULL,
	"bank_account_number"	varchar(50) NOT NULL,
	"bank_name"	varchar(100) NOT NULL,
	"telebirr_phone"	varchar(20) NOT NULL,
	"chapa_email"	varchar(254) NOT NULL,
	"status"	varchar(20) NOT NULL,
	"admin_notes"	text NOT NULL,
	"user_notes"	text NOT NULL,
	"transaction_reference"	varchar(100) NOT NULL,
	"requested_at"	datetime NOT NULL,
	"approved_at"	datetime,
	"processed_at"	datetime,
	"completed_at"	datetime,
	"approved_by_id"	bigint,
	"author_id"	bigint NOT NULL,
	"processed_by_id"	bigint,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("approved_by_id") REFERENCES "users"("id") DEFERRABLE INITIALLY DEFERRED,
	FOREIGN KEY("author_id") REFERENCES "users"("id") DEFERRABLE INITIALLY DEFERRED,
	FOREIGN KEY("processed_by_id") REFERENCES "users"("id") DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE IF NOT EXISTS "purchases" (
	"id"	integer NOT NULL,
	"transaction_id"	varchar(100) NOT NULL UNIQUE,
	"amount"	decimal NOT NULL,
	"status"	varchar(20) NOT NULL,
	"completed_at"	datetime,
	"created_at"	datetime NOT NULL,
	"updated_at"	datetime NOT NULL,
	"book_id"	bigint NOT NULL,
	"client_id"	bigint NOT NULL,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("book_id") REFERENCES "books"("id") DEFERRABLE INITIALLY DEFERRED,
	FOREIGN KEY("client_id") REFERENCES "users"("id") DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE IF NOT EXISTS "quality_reviews" (
	"id"	integer NOT NULL,
	"review_type"	varchar(10) NOT NULL,
	"content_quality"	decimal,
	"editorial_quality"	decimal,
	"technical_quality"	decimal,
	"overall_score"	decimal,
	"comments"	text NOT NULL,
	"recommendation"	varchar(20),
	"created_at"	datetime NOT NULL,
	"updated_at"	datetime NOT NULL,
	"book_id"	bigint NOT NULL,
	"reviewer_id"	bigint NOT NULL,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("book_id") REFERENCES "books"("id") DEFERRABLE INITIALLY DEFERRED,
	FOREIGN KEY("reviewer_id") REFERENCES "users"("id") DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE IF NOT EXISTS "royalties" (
	"id"	integer NOT NULL,
	"total_sales"	integer NOT NULL,
	"total_revenue"	decimal NOT NULL,
	"platform_fee"	decimal NOT NULL,
	"tax_amount"	decimal NOT NULL,
	"gross_amount"	decimal NOT NULL,
	"commission_rate"	decimal NOT NULL,
	"commission_amount"	decimal NOT NULL,
	"net_payment"	decimal NOT NULL,
	"period_start"	date,
	"period_end"	date,
	"status"	varchar(20) NOT NULL,
	"payment_date"	datetime,
	"payment_reference"	varchar(100) NOT NULL,
	"notes"	text NOT NULL,
	"created_at"	datetime NOT NULL,
	"updated_at"	datetime NOT NULL,
	"author_id"	bigint NOT NULL,
	"book_id"	bigint NOT NULL,
	"purchase_id"	bigint,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("author_id") REFERENCES "users"("id") DEFERRABLE INITIALLY DEFERRED,
	FOREIGN KEY("book_id") REFERENCES "books"("id") DEFERRABLE INITIALLY DEFERRED,
	FOREIGN KEY("purchase_id") REFERENCES "purchases"("id") DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE IF NOT EXISTS "users" (
	"id"	integer NOT NULL,
	"password"	varchar(128) NOT NULL,
	"last_login"	datetime,
	"is_superuser"	bool NOT NULL,
	"username"	varchar(150) NOT NULL UNIQUE,
	"first_name"	varchar(150) NOT NULL,
	"last_name"	varchar(150) NOT NULL,
	"is_staff"	bool NOT NULL,
	"date_joined"	datetime NOT NULL,
	"email"	varchar(254) NOT NULL UNIQUE,
	"full_name"	varchar(255) NOT NULL,
	"national_id"	varchar(16) UNIQUE,
	"national_id_verified"	bool NOT NULL,
	"phone"	varchar(20) NOT NULL,
	"phone_verified"	bool NOT NULL,
	"address"	text NOT NULL,
	"date_of_birth"	date,
	"gender"	varchar(10) NOT NULL,
	"region"	varchar(100) NOT NULL,
	"zone"	varchar(100) NOT NULL,
	"woreda"	varchar(100) NOT NULL,
	"role"	varchar(20) NOT NULL,
	"is_active"	bool NOT NULL,
	"email_verified"	bool NOT NULL,
	"email_verification_token"	varchar(255) NOT NULL,
	"verification_token_expires"	datetime,
	"last_login_ip"	char(39),
	"last_seen"	datetime,
	"profile_image"	varchar(100),
	"bio"	text NOT NULL,
	"created_at"	datetime NOT NULL,
	"updated_at"	datetime NOT NULL,
	"locked_until"	datetime,
	"login_attempts"	integer NOT NULL,
	"two_factor_enabled"	bool NOT NULL,
	"two_factor_secret"	varchar(255) NOT NULL,
	PRIMARY KEY("id" AUTOINCREMENT)
);
CREATE TABLE IF NOT EXISTS "users_groups" (
	"id"	integer NOT NULL,
	"customuser_id"	bigint NOT NULL,
	"group_id"	integer NOT NULL,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("customuser_id") REFERENCES "users"("id") DEFERRABLE INITIALLY DEFERRED,
	FOREIGN KEY("group_id") REFERENCES "auth_group"("id") DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE IF NOT EXISTS "users_user_permissions" (
	"id"	integer NOT NULL,
	"customuser_id"	bigint NOT NULL,
	"permission_id"	integer NOT NULL,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("customuser_id") REFERENCES "users"("id") DEFERRABLE INITIALLY DEFERRED,
	FOREIGN KEY("permission_id") REFERENCES "auth_permission"("id") DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE IF NOT EXISTS "wishlists" (
	"id"	integer NOT NULL,
	"notes"	text NOT NULL,
	"created_at"	datetime NOT NULL,
	"book_id"	bigint NOT NULL,
	"client_id"	bigint NOT NULL,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("book_id") REFERENCES "books"("id") DEFERRABLE INITIALLY DEFERRED,
	FOREIGN KEY("client_id") REFERENCES "users"("id") DEFERRABLE INITIALLY DEFERRED
);
INSERT INTO "auth_permission" VALUES (1,1,'add_logentry','Can add log entry');
INSERT INTO "auth_permission" VALUES (2,1,'change_logentry','Can change log entry');
INSERT INTO "auth_permission" VALUES (3,1,'delete_logentry','Can delete log entry');
INSERT INTO "auth_permission" VALUES (4,1,'view_logentry','Can view log entry');
INSERT INTO "auth_permission" VALUES (5,2,'add_permission','Can add permission');
INSERT INTO "auth_permission" VALUES (6,2,'change_permission','Can change permission');
INSERT INTO "auth_permission" VALUES (7,2,'delete_permission','Can delete permission');
INSERT INTO "auth_permission" VALUES (8,2,'view_permission','Can view permission');
INSERT INTO "auth_permission" VALUES (9,3,'add_group','Can add group');
INSERT INTO "auth_permission" VALUES (10,3,'change_group','Can change group');
INSERT INTO "auth_permission" VALUES (11,3,'delete_group','Can delete group');
INSERT INTO "auth_permission" VALUES (12,3,'view_group','Can view group');
INSERT INTO "auth_permission" VALUES (13,4,'add_contenttype','Can add content type');
INSERT INTO "auth_permission" VALUES (14,4,'change_contenttype','Can change content type');
INSERT INTO "auth_permission" VALUES (15,4,'delete_contenttype','Can delete content type');
INSERT INTO "auth_permission" VALUES (16,4,'view_contenttype','Can view content type');
INSERT INTO "auth_permission" VALUES (17,5,'add_session','Can add session');
INSERT INTO "auth_permission" VALUES (18,5,'change_session','Can change session');
INSERT INTO "auth_permission" VALUES (19,5,'delete_session','Can delete session');
INSERT INTO "auth_permission" VALUES (20,5,'view_session','Can view session');
INSERT INTO "auth_permission" VALUES (21,6,'add_customuser','Can add custom user');
INSERT INTO "auth_permission" VALUES (22,6,'change_customuser','Can change custom user');
INSERT INTO "auth_permission" VALUES (23,6,'delete_customuser','Can delete custom user');
INSERT INTO "auth_permission" VALUES (24,6,'view_customuser','Can view custom user');
INSERT INTO "auth_permission" VALUES (25,7,'add_authorprofile','Can add author profile');
INSERT INTO "auth_permission" VALUES (26,7,'change_authorprofile','Can change author profile');
INSERT INTO "auth_permission" VALUES (27,7,'delete_authorprofile','Can delete author profile');
INSERT INTO "auth_permission" VALUES (28,7,'view_authorprofile','Can view author profile');
INSERT INTO "auth_permission" VALUES (29,8,'add_clientprofile','Can add client profile');
INSERT INTO "auth_permission" VALUES (30,8,'change_clientprofile','Can change client profile');
INSERT INTO "auth_permission" VALUES (31,8,'delete_clientprofile','Can delete client profile');
INSERT INTO "auth_permission" VALUES (32,8,'view_clientprofile','Can view client profile');
INSERT INTO "auth_permission" VALUES (33,9,'add_genre','Can add genre');
INSERT INTO "auth_permission" VALUES (34,9,'change_genre','Can change genre');
INSERT INTO "auth_permission" VALUES (35,9,'delete_genre','Can delete genre');
INSERT INTO "auth_permission" VALUES (36,9,'view_genre','Can view genre');
INSERT INTO "auth_permission" VALUES (37,10,'add_book','Can add book');
INSERT INTO "auth_permission" VALUES (38,10,'change_book','Can change book');
INSERT INTO "auth_permission" VALUES (39,10,'delete_book','Can delete book');
INSERT INTO "auth_permission" VALUES (40,10,'view_book','Can view book');
INSERT INTO "auth_permission" VALUES (41,11,'add_wishlist','Can add wishlist');
INSERT INTO "auth_permission" VALUES (42,11,'change_wishlist','Can change wishlist');
INSERT INTO "auth_permission" VALUES (43,11,'delete_wishlist','Can delete wishlist');
INSERT INTO "auth_permission" VALUES (44,11,'view_wishlist','Can view wishlist');
INSERT INTO "auth_permission" VALUES (45,12,'add_qualityreview','Can add quality review');
INSERT INTO "auth_permission" VALUES (46,12,'change_qualityreview','Can change quality review');
INSERT INTO "auth_permission" VALUES (47,12,'delete_qualityreview','Can delete quality review');
INSERT INTO "auth_permission" VALUES (48,12,'view_qualityreview','Can view quality review');
INSERT INTO "auth_permission" VALUES (49,13,'add_paymentrequest','Can add payment request');
INSERT INTO "auth_permission" VALUES (50,13,'change_paymentrequest','Can change payment request');
INSERT INTO "auth_permission" VALUES (51,13,'delete_paymentrequest','Can delete payment request');
INSERT INTO "auth_permission" VALUES (52,13,'view_paymentrequest','Can view payment request');
INSERT INTO "auth_permission" VALUES (53,14,'add_royalty','Can add royalty');
INSERT INTO "auth_permission" VALUES (54,14,'change_royalty','Can change royalty');
INSERT INTO "auth_permission" VALUES (55,14,'delete_royalty','Can delete royalty');
INSERT INTO "auth_permission" VALUES (56,14,'view_royalty','Can view royalty');
INSERT INTO "auth_permission" VALUES (57,15,'add_purchase','Can add purchase');
INSERT INTO "auth_permission" VALUES (58,15,'change_purchase','Can change purchase');
INSERT INTO "auth_permission" VALUES (59,15,'delete_purchase','Can delete purchase');
INSERT INTO "auth_permission" VALUES (60,15,'view_purchase','Can view purchase');
INSERT INTO "auth_permission" VALUES (61,16,'add_notification','Can add notification');
INSERT INTO "auth_permission" VALUES (62,16,'change_notification','Can change notification');
INSERT INTO "auth_permission" VALUES (63,16,'delete_notification','Can delete notification');
INSERT INTO "auth_permission" VALUES (64,16,'view_notification','Can view notification');
INSERT INTO "author_profiles" VALUES (1,'','','','','','','','','','','','','',0,NULL,'not_submitted','',NULL,70,0,0,0,NULL,0,0,'2026-06-12 12:39:43.560455','2026-06-12 12:39:43.560491',2,NULL,'1.0',NULL,0);
INSERT INTO "clients" VALUES (1,'',0,0,0,0,'',1,'2026-06-12 12:22:44.337463','2026-06-12 12:22:44.337510',1);
INSERT INTO "clients" VALUES (2,'0912131415',0,0,0,0,'',1,'2026-06-12 12:44:57.136316','2026-06-12 12:44:57.136348',3);
INSERT INTO "clients" VALUES (3,'',0,0,0,0,'',1,'2026-06-12 13:02:59.174807','2026-06-12 13:02:59.174829',4);
INSERT INTO "django_content_type" VALUES (1,'admin','logentry');
INSERT INTO "django_content_type" VALUES (2,'auth','permission');
INSERT INTO "django_content_type" VALUES (3,'auth','group');
INSERT INTO "django_content_type" VALUES (4,'contenttypes','contenttype');
INSERT INTO "django_content_type" VALUES (5,'sessions','session');
INSERT INTO "django_content_type" VALUES (6,'accounts','customuser');
INSERT INTO "django_content_type" VALUES (7,'accounts','authorprofile');
INSERT INTO "django_content_type" VALUES (8,'accounts','clientprofile');
INSERT INTO "django_content_type" VALUES (9,'books','genre');
INSERT INTO "django_content_type" VALUES (10,'books','book');
INSERT INTO "django_content_type" VALUES (11,'books','wishlist');
INSERT INTO "django_content_type" VALUES (12,'reviews','qualityreview');
INSERT INTO "django_content_type" VALUES (13,'royalties','paymentrequest');
INSERT INTO "django_content_type" VALUES (14,'royalties','royalty');
INSERT INTO "django_content_type" VALUES (15,'payments','purchase');
INSERT INTO "django_content_type" VALUES (16,'notifications','notification');
INSERT INTO "django_migrations" VALUES (1,'contenttypes','0001_initial','2026-06-12 06:50:52.732953');
INSERT INTO "django_migrations" VALUES (2,'contenttypes','0002_remove_content_type_name','2026-06-12 06:50:52.748845');
INSERT INTO "django_migrations" VALUES (3,'auth','0001_initial','2026-06-12 06:50:52.780465');
INSERT INTO "django_migrations" VALUES (4,'auth','0002_alter_permission_name_max_length','2026-06-12 06:50:52.797033');
INSERT INTO "django_migrations" VALUES (5,'auth','0003_alter_user_email_max_length','2026-06-12 06:50:52.809447');
INSERT INTO "django_migrations" VALUES (6,'auth','0004_alter_user_username_opts','2026-06-12 06:50:52.823454');
INSERT INTO "django_migrations" VALUES (7,'auth','0005_alter_user_last_login_null','2026-06-12 06:50:52.837284');
INSERT INTO "django_migrations" VALUES (8,'auth','0006_require_contenttypes_0002','2026-06-12 06:50:52.845027');
INSERT INTO "django_migrations" VALUES (9,'auth','0007_alter_validators_add_error_messages','2026-06-12 06:50:52.856370');
INSERT INTO "django_migrations" VALUES (10,'auth','0008_alter_user_username_max_length','2026-06-12 06:50:52.872533');
INSERT INTO "django_migrations" VALUES (11,'auth','0009_alter_user_last_name_max_length','2026-06-12 06:50:52.884932');
INSERT INTO "django_migrations" VALUES (12,'auth','0010_alter_group_name_max_length','2026-06-12 06:50:52.901613');
INSERT INTO "django_migrations" VALUES (13,'auth','0011_update_proxy_permissions','2026-06-12 06:50:52.914042');
INSERT INTO "django_migrations" VALUES (14,'auth','0012_alter_user_first_name_max_length','2026-06-12 06:50:52.927349');
INSERT INTO "django_migrations" VALUES (15,'accounts','0001_initial','2026-06-12 06:50:52.984036');
INSERT INTO "django_migrations" VALUES (16,'admin','0001_initial','2026-06-12 06:50:53.020712');
INSERT INTO "django_migrations" VALUES (17,'admin','0002_logentry_remove_auto_add','2026-06-12 06:50:53.049353');
INSERT INTO "django_migrations" VALUES (18,'admin','0003_logentry_add_action_flag_choices','2026-06-12 06:50:53.067533');
INSERT INTO "django_migrations" VALUES (19,'books','0001_initial','2026-06-12 06:50:53.205082');
INSERT INTO "django_migrations" VALUES (20,'books','0002_alter_book_isbn','2026-06-12 06:50:53.250611');
INSERT INTO "django_migrations" VALUES (21,'books','0003_alter_book_isbn','2026-06-12 06:50:53.294367');
INSERT INTO "django_migrations" VALUES (22,'notifications','0001_initial','2026-06-12 06:50:53.339735');
INSERT INTO "django_migrations" VALUES (23,'payments','0001_initial','2026-06-12 06:50:53.382524');
INSERT INTO "django_migrations" VALUES (24,'reviews','0001_initial','2026-06-12 06:50:53.418918');
INSERT INTO "django_migrations" VALUES (25,'royalties','0001_initial','2026-06-12 06:50:53.496784');
INSERT INTO "django_migrations" VALUES (26,'sessions','0001_initial','2026-06-12 06:50:53.514494');
INSERT INTO "django_migrations" VALUES (27,'accounts','0002_alter_customuser_options_and_more','2026-06-12 13:12:20.319386');
INSERT INTO "django_migrations" VALUES (28,'books','0004_alter_book_isbn','2026-06-12 13:12:20.347935');
INSERT INTO "django_migrations" VALUES (29,'books','0005_existing_tables','2026-06-12 14:07:19.294048');
INSERT INTO "django_migrations" VALUES (30,'books','0006_remove_book_books_status_08b8fa_idx_and_more','2026-06-13 07:40:27.276774');
INSERT INTO "django_session" VALUES ('oued2u3t9cg89xri4fv0zkw07k35ctnw','.eJxVjMsKwjAQAP9lzxLSZ5oevfsNYTfZtVFJStOCIv67FHrQ68wwb3C4rZPbCi8uBhihhdMvI_R3TrsIN0zXrHxO6xJJ7Yk6bFGXHPhxPtq_wYRlghGk70xPXpiGGlGqmkxDFXWhRS3GohhrfCW1ldbYXoswc8OeSPzQUND7tHApMSfHzzkuLxj15wvfLkDO:1wYHFQ:nhVfPOfuLguHjc75DiVTAGEGJmdLJFHCVkrmj03fPCg','2026-06-14 05:49:36.917033');
INSERT INTO "django_session" VALUES ('wtcu3o7uvadwgimow1nnu3thfu2ivi8d','e30:1wYJMZ:Ypd6j6o3Lw4SQezxUhvmtMQj9Lb5gC9Bx7cleqPkMpY','2026-06-14 08:05:07.239670');
INSERT INTO "django_session" VALUES ('xcg49e1o2mlvohe2zikie68xl0bdhmt5','.eJxVjEEOwiAQRe_C2hCgtJ126d4zkGEYLGrAlDbRGO-uTbrQ7X_vv5dwuC6TWyvPLgUxCiMOv5tHunLeQLhgPhdJJS9z8nJT5E6rPJXAt-Pu_gUmrNP3DdxG9OD7QQ--aXw00ANH7DqwzETEYKzuNUcLrbGtIhOjtToMitGQ2qKVa00lO37c0_wUo3p_AKpmP38:1wYJVx:UbAIrbjKzce1nesqTksy_gr2joHlB3SjV5ODfU7xzyg','2026-06-14 08:14:49.127705');
INSERT INTO "django_session" VALUES ('1kamliwn3gq40x56s2cj0y0d8v79785j','.eJxVjEsOwiAUAO_C2hAeWB506d4zkMenFjVgSptojHc3JF3odmYyb-ZoW2e3tbS4HNnIjuzwyzyFWypdxCuVS-WhlnXJnveE77bxc43pftrbv8FMbe7bQaBHkABgNCm0WlsUZtBeAHmlhAQLhhIKCwEsKj0RBivQRC8nOfRpS63lWlx6PvLyYqP4fAENxT0w:1wYJyK:qwNVWF5ePcscmgOvlKCdkrhHfGufVIfL-PvbVfKYPnQ','2026-06-14 08:44:08.613302');
INSERT INTO "users" VALUES (1,'pbkdf2_sha256$720000$scTgTVCv9kvZjpIRd9wquM$DYI4Voif2rxkQ2+FvmHLxDpCLFbPpoTyCdzLMi+BHqM=','2026-06-12 12:57:25.962054',1,'admin','','',1,'2026-06-12 06:51:25.584201','get2015@gmail.com','',NULL,0,'',0,'',NULL,'','','','','client',1,0,'',NULL,'127.0.0.1','2026-06-12 12:57:25.968537','','','2026-06-12 06:51:26.045661','2026-06-12 06:51:26.045711',NULL,0,0,'');
INSERT INTO "users" VALUES (2,'pbkdf2_sha256$600000$GbDV9tco8CoJTDMrYEyQuo$7Ra+10w6u4B6EGpR5DfWKfaQFGE6pyLhn1uGNbQ+nxM=','2026-06-13 08:12:42.931107',0,'wendimu','','',0,'2026-06-12 12:39:42.327704','wendimu@yahoo.com','Wondimu Tadesse','1234567890123456',1,'0911223344',0,'',NULL,'','','','','author',1,1,'bb0b6f630cfb4a569c1789758bc8cf1d','2026-06-19 12:39:43.545919','127.0.0.1','2026-06-13 08:12:42.945093','','','2026-06-12 12:39:43.548430','2026-06-12 12:39:43.548451',NULL,0,0,'');
INSERT INTO "users" VALUES (3,'pbkdf2_sha256$720000$NTHoLOZVLC3RFQ50ps581z$syYygYZDCMxaLwd+c2GH/bMjbXCppdGRPGdTyz0Aa9Q=','2026-06-12 12:44:57.153938',0,'wendimu@y','','',0,'2026-06-12 12:44:55.749518','wendimu@gmail.com','Wondimu Tadesse',NULL,0,'0912131415',0,'',NULL,'','','','','client',1,1,'',NULL,NULL,NULL,'','','2026-06-12 12:44:57.126346','2026-06-12 12:44:57.126366',NULL,0,0,'');
INSERT INTO "users" VALUES (4,'pbkdf2_sha256$600000$hva6iKu1y0fZtyrKteNrvC$8+klma6/fJ/3gTwcT9DD3eMnxnDYZUfWAxPTDkys+E0=','2026-06-13 08:41:40.583540',1,'administrator','','',1,'2026-06-12 13:02:30.771618','getu@gmail.com','',NULL,0,'',0,'',NULL,'','','','','client',1,0,'',NULL,'127.0.0.1','2026-06-13 08:41:40.589545','','','2026-06-12 13:02:31.122580','2026-06-12 13:02:31.122592',NULL,0,0,'');
INSERT INTO "users" VALUES (5,'pbkdf2_sha256$600000$hPgyr9yNZovWxF9JGONma1$mYGg2WNTvSVDt7iO0NDUNOVEp5QiA6J0su7vPP8TyIs=',NULL,1,'admin_0','','',1,'2026-06-13 08:40:11.849985','admin0@abay.com','Admin User 0',NULL,0,'',0,'',NULL,'','','','','admin',1,0,'',NULL,NULL,NULL,'','','2026-06-13 08:40:11.851207','2026-06-13 08:40:12.210232',NULL,0,0,'');
INSERT INTO "users" VALUES (6,'pbkdf2_sha256$600000$DsfUfKGc783F7Sm2XfIDwa$rIHUwaYs1YnWkDjx+lX/v/H9R2+BCcYG6cjaUJv8oZY=',NULL,0,'checker_0','','',1,'2026-06-13 08:40:12.227596','checker0@abay.com','Checker User 0',NULL,0,'',0,'',NULL,'','','','','checker',1,0,'',NULL,NULL,NULL,'','','2026-06-13 08:40:12.228600','2026-06-13 08:40:12.594299',NULL,0,0,'');
INSERT INTO "users" VALUES (7,'pbkdf2_sha256$600000$QohcESdBQJ1PzrIYBH4xv9$JPyXiLtSQYq5BDPrmD7AFycvuqUlPOwKJFhz6XgDVUQ=',NULL,0,'checker_1','','',1,'2026-06-13 08:40:12.601897','checker1@abay.com','Checker User 1',NULL,0,'',0,'',NULL,'','','','','checker',1,0,'',NULL,NULL,NULL,'','','2026-06-13 08:40:12.601897','2026-06-13 08:40:12.968249',NULL,0,0,'');
INSERT INTO "users" VALUES (8,'pbkdf2_sha256$600000$HsLI60mlrqyEpE30rF9sya$rXFI426h+gW1YdkjyN3By/gUyayyYxNUKbPeT3XRWg4=',NULL,0,'author_bekele_0','','',0,'2026-06-13 08:40:12.977423','author0@abay.com','Bekele Getachew',NULL,0,'',0,'',NULL,'','','','','author',1,0,'',NULL,NULL,NULL,'','','2026-06-13 08:40:12.978590','2026-06-13 08:40:13.341759',NULL,0,0,'');
INSERT INTO "users" VALUES (9,'pbkdf2_sha256$600000$rqUbcdoUL5hOv3wivJpPUG$K6lTfz35+9SfpqHBZqBVRt0HwM+/dOnSJ30a3XFFTHQ=',NULL,0,'author_elsabet_1','','',0,'2026-06-13 08:40:13.351712','author1@abay.com','Elsabet Tadesse',NULL,0,'',0,'',NULL,'','','','','author',1,0,'',NULL,NULL,NULL,'','','2026-06-13 08:40:13.351712','2026-06-13 08:40:13.719175',NULL,0,0,'');
INSERT INTO "users" VALUES (10,'pbkdf2_sha256$600000$9z169BYOZQvbbeuzs0fjb5$H+Axvme9jzh58ij7goITUOJifmJ4q9Smx5g+5rMKuXk=',NULL,0,'author_genet_2','','',0,'2026-06-13 08:40:13.728105','author2@abay.com','Genet Haile',NULL,0,'',0,'',NULL,'','','','','author',1,0,'',NULL,NULL,NULL,'','','2026-06-13 08:40:13.729104','2026-06-13 08:40:14.087590',NULL,0,0,'');
INSERT INTO "users" VALUES (11,'pbkdf2_sha256$600000$apFFI2fQjAxNbqsxQnlKRx$WMFIWVmW0ckYauoZjPCIngppGHnMrT8LBQgDVqE78gs=',NULL,0,'author_elsabet_3','','',0,'2026-06-13 08:40:14.094778','author3@abay.com','Elsabet Alemayehu',NULL,0,'',0,'',NULL,'','','','','author',1,0,'',NULL,NULL,NULL,'','','2026-06-13 08:40:14.094778','2026-06-13 08:40:14.451650',NULL,0,0,'');
INSERT INTO "users" VALUES (12,'pbkdf2_sha256$600000$nwvKYfzLvkQ0w8DyxCKqqH$1hKTBzlBqYqbiNEjKhi36GRR6JS5wSUZWW06sU2GK54=',NULL,0,'author_liya_4','','',0,'2026-06-13 08:40:14.461010','author4@abay.com','Liya Assefa',NULL,0,'',0,'',NULL,'','','','','author',1,0,'',NULL,NULL,NULL,'','','2026-06-13 08:40:14.461010','2026-06-13 08:40:14.815602',NULL,0,0,'');
INSERT INTO "users" VALUES (13,'pbkdf2_sha256$600000$g15OuygTC65joDAsx1JOr6$YR9Wg8ixAadjFYMs6QmyV80zbv6gQi92xDX8/FhSe7Y=',NULL,0,'reader_almaz_0','','',0,'2026-06-13 08:40:14.824579','reader0@gmail.com','Almaz Tesfaye',NULL,0,'',0,'',NULL,'','','','','client',1,0,'',NULL,NULL,NULL,'','','2026-06-13 08:40:14.824579','2026-06-13 08:40:15.183282',NULL,0,0,'');
INSERT INTO "users" VALUES (14,'pbkdf2_sha256$600000$39R8Nvq10I9mDWgdXtL0xc$zNwEf/gKi6q4NxZWk6BaWw4xsOai6BqxWHyaIoiM7W8=',NULL,0,'reader_liya_1','','',0,'2026-06-13 08:40:15.189797','reader1@gmail.com','Liya Haile',NULL,0,'',0,'',NULL,'','','','','client',1,0,'',NULL,NULL,NULL,'','','2026-06-13 08:40:15.190830','2026-06-13 08:40:15.549351',NULL,0,0,'');
INSERT INTO "users" VALUES (15,'pbkdf2_sha256$600000$hX3ChiSK0IO6AFBNRYbZIL$vju0DmUywAoROaM7RMQJAInRTTtFHbiMGO6Rd2ggG0w=',NULL,0,'reader_genet_2','','',0,'2026-06-13 08:40:15.557670','reader2@gmail.com','Genet Desta',NULL,0,'',0,'',NULL,'','','','','client',1,0,'',NULL,NULL,NULL,'','','2026-06-13 08:40:15.557670','2026-06-13 08:40:15.908320',NULL,0,0,'');
INSERT INTO "users" VALUES (16,'pbkdf2_sha256$600000$cw4cDqz6Un4KwyLaQFs5aO$wr0bz9q+sSWDgLcI8XoOpzJ8F0Z2geYR4YnVhbCINak=',NULL,0,'reader_dawit_3','','',0,'2026-06-13 08:40:15.918031','reader3@gmail.com','Dawit Getachew',NULL,0,'',0,'',NULL,'','','','','client',1,0,'',NULL,NULL,NULL,'','','2026-06-13 08:40:15.918031','2026-06-13 08:40:16.271798',NULL,0,0,'');
INSERT INTO "users" VALUES (17,'pbkdf2_sha256$600000$CaOoXal0GNojN296Y2qqgh$YT425axF5DmxM/br1swzgaiByhyPSm6jx2lQykxxIT4=',NULL,0,'reader_elsabet_4','','',0,'2026-06-13 08:40:16.280853','reader4@gmail.com','Elsabet Tadesse',NULL,0,'',0,'',NULL,'','','','','client',1,0,'',NULL,NULL,NULL,'','','2026-06-13 08:40:16.280853','2026-06-13 08:40:16.636068',NULL,0,0,'');
INSERT INTO "users" VALUES (18,'pbkdf2_sha256$600000$uA84HVYBnOijGnGZk05OE6$/RePEr8SrHA5m18c61RCtygEtx2GRaJK2Y4eZyTEkxo=',NULL,0,'reader_almaz_5','','',0,'2026-06-13 08:40:16.644553','reader5@gmail.com','Almaz Desta',NULL,0,'',0,'',NULL,'','','','','client',1,0,'',NULL,NULL,NULL,'','','2026-06-13 08:40:16.644553','2026-06-13 08:40:17.008405',NULL,0,0,'');
INSERT INTO "users" VALUES (19,'pbkdf2_sha256$600000$ovSd6BmvsbGyMUNjzMimjP$3axYYa6uZ9HYS4aRvoC1ZjZA2He3YyWtOfWmp9j8s5w=',NULL,0,'reader_genet_6','','',0,'2026-06-13 08:40:17.017257','reader6@gmail.com','Genet Getachew',NULL,0,'',0,'',NULL,'','','','','client',1,0,'',NULL,NULL,NULL,'','','2026-06-13 08:40:17.017257','2026-06-13 08:40:17.374749',NULL,0,0,'');
INSERT INTO "users" VALUES (20,'pbkdf2_sha256$600000$sXyFJh2wjo5YTOQxjrjA3Q$boVhX45s5c3+pF9OKx9b1I6lUj1UPhD1WZYG6/61NNs=',NULL,0,'reader_habtamu_7','','',0,'2026-06-13 08:40:17.385522','reader7@gmail.com','Habtamu Desta',NULL,0,'',0,'',NULL,'','','','','client',1,0,'',NULL,NULL,NULL,'','','2026-06-13 08:40:17.386519','2026-06-13 08:40:17.745879',NULL,0,0,'');
INSERT INTO "users" VALUES (21,'pbkdf2_sha256$600000$5mRWbhC4trJ4Ww1QVio9dv$KxZiR5KAkJtz9kqLupsbOILJzcc//MGfWgctWFWC49c=',NULL,0,'reader_abebe_8','','',0,'2026-06-13 08:40:17.751732','reader8@gmail.com','Abebe Getachew',NULL,0,'',0,'',NULL,'','','','','client',1,0,'',NULL,NULL,NULL,'','','2026-06-13 08:40:17.751732','2026-06-13 08:40:18.113772',NULL,0,0,'');
INSERT INTO "users" VALUES (22,'pbkdf2_sha256$600000$wros2GqXQrW9Im78wBC86v$wEBctFB/oYljEDLL34ctmow3nOdruiwrjafp7JzXCE8=',NULL,0,'reader_fikru_9','','',0,'2026-06-13 08:40:18.123635','reader9@gmail.com','Fikru Tesfaye',NULL,0,'',0,'',NULL,'','','','','client',1,0,'',NULL,NULL,NULL,'','','2026-06-13 08:40:18.123635','2026-06-13 08:40:18.480487',NULL,0,0,'');
CREATE INDEX IF NOT EXISTS "auth_group_permissions_group_id_b120cbf9" ON "auth_group_permissions" (
	"group_id"
);
CREATE UNIQUE INDEX IF NOT EXISTS "auth_group_permissions_group_id_permission_id_0cd325b0_uniq" ON "auth_group_permissions" (
	"group_id",
	"permission_id"
);
CREATE INDEX IF NOT EXISTS "auth_group_permissions_permission_id_84c5c92e" ON "auth_group_permissions" (
	"permission_id"
);
CREATE INDEX IF NOT EXISTS "auth_permission_content_type_id_2f476e4b" ON "auth_permission" (
	"content_type_id"
);
CREATE UNIQUE INDEX IF NOT EXISTS "auth_permission_content_type_id_codename_01ab375a_uniq" ON "auth_permission" (
	"content_type_id",
	"codename"
);
CREATE INDEX IF NOT EXISTS "author_profiles_verified_by_id_109175fe" ON "author_profiles" (
	"verified_by_id"
);
CREATE INDEX IF NOT EXISTS "books_author_id_c90d3b48" ON "books" (
	"author_id"
);
CREATE INDEX IF NOT EXISTS "books_genre_id_0d946827" ON "books" (
	"genre_id"
);
CREATE INDEX IF NOT EXISTS "django_admin_log_content_type_id_c4bce8eb" ON "django_admin_log" (
	"content_type_id"
);
CREATE INDEX IF NOT EXISTS "django_admin_log_user_id_c564eba6" ON "django_admin_log" (
	"user_id"
);
CREATE UNIQUE INDEX IF NOT EXISTS "django_content_type_app_label_model_76bd3d3b_uniq" ON "django_content_type" (
	"app_label",
	"model"
);
CREATE INDEX IF NOT EXISTS "django_session_expire_date_a5c62663" ON "django_session" (
	"expire_date"
);
CREATE INDEX IF NOT EXISTS "notifications_user_id_468e288d" ON "notifications" (
	"user_id"
);
CREATE INDEX IF NOT EXISTS "payment_requests_approved_by_id_b4882083" ON "payment_requests" (
	"approved_by_id"
);
CREATE INDEX IF NOT EXISTS "payment_requests_author_id_905010b0" ON "payment_requests" (
	"author_id"
);
CREATE INDEX IF NOT EXISTS "payment_requests_processed_by_id_800e4898" ON "payment_requests" (
	"processed_by_id"
);
CREATE INDEX IF NOT EXISTS "purchases_book_id_984b9199" ON "purchases" (
	"book_id"
);
CREATE INDEX IF NOT EXISTS "purchases_client__a09ac4_idx" ON "purchases" (
	"client_id",
	"status"
);
CREATE INDEX IF NOT EXISTS "purchases_client_id_433e2041" ON "purchases" (
	"client_id"
);
CREATE INDEX IF NOT EXISTS "purchases_complet_ee03b2_idx" ON "purchases" (
	"completed_at"
);
CREATE INDEX IF NOT EXISTS "purchases_transac_917217_idx" ON "purchases" (
	"transaction_id"
);
CREATE INDEX IF NOT EXISTS "quality_reviews_book_id_48a7289d" ON "quality_reviews" (
	"book_id"
);
CREATE UNIQUE INDEX IF NOT EXISTS "quality_reviews_book_id_review_type_be6adcb9_uniq" ON "quality_reviews" (
	"book_id",
	"review_type"
);
CREATE INDEX IF NOT EXISTS "quality_reviews_reviewer_id_26fbad01" ON "quality_reviews" (
	"reviewer_id"
);
CREATE INDEX IF NOT EXISTS "royalties_author__c40d66_idx" ON "royalties" (
	"author_id",
	"status"
);
CREATE INDEX IF NOT EXISTS "royalties_author_id_bd84faff" ON "royalties" (
	"author_id"
);
CREATE INDEX IF NOT EXISTS "royalties_book_id_546a8221" ON "royalties" (
	"book_id"
);
CREATE INDEX IF NOT EXISTS "royalties_book_id_a39c14_idx" ON "royalties" (
	"book_id",
	"status"
);
CREATE INDEX IF NOT EXISTS "royalties_payment_4423a9_idx" ON "royalties" (
	"payment_date"
);
CREATE INDEX IF NOT EXISTS "royalties_period__e23a9a_idx" ON "royalties" (
	"period_start",
	"period_end"
);
CREATE INDEX IF NOT EXISTS "royalties_purchase_id_681e9d0a" ON "royalties" (
	"purchase_id"
);
CREATE INDEX IF NOT EXISTS "users_groups_customuser_id_4bd991a9" ON "users_groups" (
	"customuser_id"
);
CREATE UNIQUE INDEX IF NOT EXISTS "users_groups_customuser_id_group_id_927de924_uniq" ON "users_groups" (
	"customuser_id",
	"group_id"
);
CREATE INDEX IF NOT EXISTS "users_groups_group_id_2f3517aa" ON "users_groups" (
	"group_id"
);
CREATE INDEX IF NOT EXISTS "users_user_permissions_customuser_id_efdb305c" ON "users_user_permissions" (
	"customuser_id"
);
CREATE UNIQUE INDEX IF NOT EXISTS "users_user_permissions_customuser_id_permission_id_2b4e4e39_uniq" ON "users_user_permissions" (
	"customuser_id",
	"permission_id"
);
CREATE INDEX IF NOT EXISTS "users_user_permissions_permission_id_6d08dcd2" ON "users_user_permissions" (
	"permission_id"
);
CREATE INDEX IF NOT EXISTS "wishlists_book_id_552db58e" ON "wishlists" (
	"book_id"
);
CREATE INDEX IF NOT EXISTS "wishlists_client_id_188a397c" ON "wishlists" (
	"client_id"
);
CREATE UNIQUE INDEX IF NOT EXISTS "wishlists_client_id_book_id_cb79641e_uniq" ON "wishlists" (
	"client_id",
	"book_id"
);
COMMIT;
