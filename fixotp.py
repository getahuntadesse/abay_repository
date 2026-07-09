# fix_otp_tables_final.py
import mysql.connector
from mysql.connector import Error

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',  # Your MySQL password
    'database': 'abay_repository'
}

def table_exists(cursor, table_name):
    cursor.execute(f"""
        SELECT COUNT(*) 
        FROM information_schema.TABLES 
        WHERE TABLE_SCHEMA = DATABASE() 
        AND TABLE_NAME = '{table_name}'
    """)
    return cursor.fetchone()[0] > 0

def fix_otp_tables():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()
        
        print("=" * 60)
        print("Creating OTP Tables")
        print("=" * 60)
        
        # Tables to create
        tables = [
            ('otp_email_emaildevice', """
                CREATE TABLE IF NOT EXISTS `otp_email_emaildevice` (
                    `id` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    `name` VARCHAR(64) NOT NULL,
                    `confirmed` TINYINT(1) NOT NULL DEFAULT 1,
                    `created_at` DATETIME(6) NOT NULL,
                    `last_used_at` DATETIME(6) NULL,
                    `email` VARCHAR(254) NOT NULL,
                    `validity` INT NOT NULL DEFAULT 300,
                    `throttle_factor` INT NOT NULL DEFAULT 1,
                    `user_id` BIGINT NOT NULL,
                    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
                    INDEX `otp_email_emaildevice_user_id_0c8af0b4` (`user_id`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """),
            ('otp_static_staticdevice', """
                CREATE TABLE IF NOT EXISTS `otp_static_staticdevice` (
                    `id` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    `name` VARCHAR(64) NOT NULL,
                    `confirmed` TINYINT(1) NOT NULL DEFAULT 1,
                    `created_at` DATETIME(6) NOT NULL,
                    `last_used_at` DATETIME(6) NULL,
                    `user_id` BIGINT NOT NULL,
                    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
                    INDEX `otp_static_staticdevice_user_id_b07ffb82` (`user_id`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """),
            ('otp_static_staticdevice_tokens', """
                CREATE TABLE IF NOT EXISTS `otp_static_staticdevice_tokens` (
                    `id` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    `token` VARCHAR(16) NOT NULL,
                    `device_id` BIGINT NOT NULL,
                    FOREIGN KEY (`device_id`) REFERENCES `otp_static_staticdevice`(`id`) ON DELETE CASCADE,
                    INDEX `otp_static_staticdevice_tokens_device_id_3a12a563` (`device_id`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """),
        ]
        
        print("\nCreating OTP tables...")
        for table_name, create_sql in tables:
            if not table_exists(cursor, table_name):
                try:
                    print(f"  Creating: {table_name}...")
                    cursor.execute(create_sql)
                    print(f"    ✅ Created: {table_name}")
                except Error as e:
                    print(f"    ❌ Error: {e}")
            else:
                print(f"  ✅ Already exists: {table_name}")
        
        # Add migration records
        print("\nAdding migration records...")
        cursor.execute("DELETE FROM django_migrations WHERE app IN ('otp_email', 'otp_static')")
        cursor.execute("""
            INSERT INTO django_migrations (app, name, applied) VALUES
            ('otp_email', '0001_initial', NOW()),
            ('otp_static', '0001_initial', NOW())
        """)
        print("  ✅ Migration records added")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        print("\n" + "=" * 60)
        print("✅ OTP tables created successfully!")
        print("=" * 60)
        print("\nNow try creating the device again.")
        
    except Error as e:
        print(f"❌ Database error: {e}")

if __name__ == "__main__":
    fix_otp_tables()