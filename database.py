import sqlite3
from datetime import datetime, timedelta

DB_NAME = "database.db"

def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():

    conn = get_connection()
    cursor = conn.cursor()
    # Kullanıcılar tablosu
    cursor.execute("""
                   
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Kitaplar tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            read_date TEXT,
            page INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Notes tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(book_id) REFERENCES books(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Follows tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS follows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            follower_id INTEGER NOT NULL,
            following_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(follower_id, following_id),
            FOREIGN KEY(follower_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(following_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deleted_books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            book_id INTEGER,
            deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Comments tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            comment TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(book_id) REFERENCES books(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Kullanıcı Başarımları tablosu
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS achievements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT NOT NULL,
        image TEXT DEFAULT 'default.png',  -- Her başarıma görsel eklemek için
        trigger_type TEXT NOT NULL,        -- kitap_ekleme, not_ekleme, yorum, takip, xp, sayfa, level
        trigger_value INTEGER DEFAULT 0
    )
""")
    cursor.execute("""
CREATE TABLE IF NOT EXISTS user_achievements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    achievement_id INTEGER NOT NULL,
    unlocked_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, achievement_id),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(achievement_id) REFERENCES achievements(id) ON DELETE CASCADE
)
""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS private_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER NOT NULL,
        receiver_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(sender_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(receiver_id) REFERENCES users(id) ON DELETE CASCADE
    )
""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS general_chat (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
""")

    conn.commit()
    conn.close()
    print("✅ Veritabanı ve tablolar oluşturuldu veya zaten mevcut.")

# Başarımları veritabanına ekleme
def insert_achievements():
    achievements_list = [
        ("İlk Kitap!", "İlk kitabını ekledin.", "1.png", "kitap_ekleme", 1),
        ("5 Kitap Okudun!", "5 kitap ekledin.", "2.png", "kitap_ekleme", 5),
        ("10 Kitap Okudun!", "10 kitap ekledin.", "3.png", "kitap_ekleme", 10),
        ("25 Kitap Okudun!", "25 kitap ekledin.", "4.png", "kitap_ekleme", 25),
        ("50 Kitap Okudun!", "50 kitap ekledin.", "5.png", "kitap_ekleme", 50),
        ("İlk Tamamlanan Kitap", "Bir kitabı okundu olarak işaretledin.", "6.png", "kitap_ekleme", 1),
        ("Haftanın Kitapçısı", "Bir haftada 3 kitap ekledin.", "7.png", "haftalik_kitap", 3),
        ("Ayın Kitapçısı", "Bir ayda 10 kitap ekledin.", "8.png", "aylik_kitap", 10),
        ("Sayfa Maratoncusu", "Toplam 1000 sayfa okudun.", "9.png", "sayfa", 1000),
        ("Sayfa Maratoncusu II", "Toplam 5000 sayfa okudun.", "10.png", "sayfa", 5000),
        ("Sayfa Maratoncusu III", "Toplam 10.000 sayfa okudun.", "11.png", "sayfa", 10000),
        ("Çok Okuyan Yazar", "Aynı yazardan 5 kitap ekledin.", "12.png", "yazar", 5),
        ("Kitap Koleksiyoncusu", "20 farklı yazardan kitap ekledin.", "13.png", "farkli_yazar", 20),
        ("İlk Not", "Bir kitap için not ekledin.", "14.png", "not_ekleme", 1),
        ("Not Tutkunu", "10 farklı kitaba not ekledin.", "15.png", "not_ekleme", 10),
        ("Detaycı", "50 not ekledin.", "16.png", "not_ekleme", 50),
        ("Popüler Yorumcu", "50 yorum yaptın.", "17.png", "yorum", 50),
        ("İlk Takip", "Başkasını takip ettin.", "18.png", "takip", 1),
        ("Takipçi Kazan!", "Bir kullanıcı seni takip etmeye başladı.", "19.png", "takip_edilme", 1),
        ("Takipçi Ormanı", "10 takipçin oldu.", "20.png", "takip_edilme", 10),
        ("Sosyal Kuş", "10 kullanıcıyı takip ettin.", "21.png", "takip", 10),
        ("Süper Sosyal", "50 kullanıcıyı takip ettin.", "22.png", "takip", 50),
        ("Ortak Zevk", "Başka bir kullanıcı ile aynı kitabı okudun.", "23.png", "ortak_kitap", 1),
        ("Kitap Arkadaşım", "5 ortak kitabın var.", "24.png", "ortak_kitap", 5),
        ("Seviye 2’ye Hoşgeldin", "Level 2’ye ulaştın.", "25.png", "level", 2),
        ("Seviye 5’e Hoşgeldin", "Level 5’e ulaştın.", "26.png", "level", 5),
        ("Seviye 10’a Hoşgeldin", "Level 10’a ulaştın.", "27.png", "level", 10),
        ("XP Canavarı", "Toplam 100 XP kazandın.", "28.png", "xp", 100),
        ("XP Yıldızı", "Toplam 500 XP kazandın.", "29.png", "xp", 500),
        ("XP Efsanesi", "Toplam 1000 XP kazandın.", "30.png", "xp", 1000),
        ("Okuma Maratoncusu", "Bir hafta içinde 500 sayfa okudun.", "31.png", "haftalik_sayfa", 500),
        ("Ayın Maratoncusu", "Bir ayda 2000 sayfa okudun.", "32.png", "aylik_sayfa", 2000),
        ("Yorumcu Arkadaş", "Başkasının feed’ine yorum yaptın.", "33.png", "yorum", 1),
        ("Kitap Silici", "Bir kitabı sildin.", "34.png", "silme", 1),
    ]

    conn = get_connection()
    cursor = conn.cursor()

    for name, desc, image, ttype, value in achievements_list:
        try:
            cursor.execute(
                "INSERT INTO achievements (name, description, image, trigger_type, trigger_value) VALUES (?, ?, ?, ?, ?)",
                (name, desc, image, ttype, value)
            )
        except sqlite3.IntegrityError:
            continue

    conn.commit()
    conn.close()
    print("✅ Başarımlar eklendi.")


# ------------------ add_xp ------------------
def add_xp(user_id, amount, conn=None):
    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True

    cursor = conn.cursor()
    cursor.execute("SELECT xp, level FROM users WHERE id=?", (user_id,))
    row = cursor.fetchone()
    if not row:
        if close_conn:
            conn.close()
        return

    xp, level = row
    xp += amount
    new_level = (xp // 100) + 1
    cursor.execute("UPDATE users SET xp=?, level=? WHERE id=?", (xp, new_level, user_id))

    if close_conn:
        conn.commit()
        conn.close()
    else:
        conn.commit()

# ------------------ check_achievements + XP ------------------
def check_achievements(user_id, conn=None):
    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True
    cursor = conn.cursor()

    # Kullanıcı verileri
    cursor.execute("SELECT COUNT(*) FROM books WHERE user_id=?", (user_id,))
    total_books = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT book_id) FROM notes WHERE user_id=?", (user_id,))
    total_notes = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM comments WHERE user_id=?", (user_id,))
    total_comments = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM follows WHERE follower_id=?", (user_id,))
    total_following = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM follows WHERE following_id=?", (user_id,))
    total_followers = cursor.fetchone()[0]
    cursor.execute("SELECT xp, level FROM users WHERE id=?", (user_id,))
    xp, level = cursor.fetchone()
    cursor.execute("SELECT SUM(page) FROM books WHERE user_id=?", (user_id,))
    total_pages = cursor.fetchone()[0] or 0

    # Achievements tablosu
    cursor.execute("SELECT id, name, description, image, trigger_type, trigger_value FROM achievements")
    all_achievements = cursor.fetchall()

    # XP ödülleri
    achievement_xp = {
        "İlk Kitap!": 50,
        "5 Kitap Okudun!": 100,
        "10 Kitap Okudun!": 200,
        "25 Kitap Okudun!": 300,
        "50 Kitap Okudun!": 500,
        "İlk Tamamlanan Kitap": 50,
        "Haftanın Kitapçısı": 150,
        "Ayın Kitapçısı": 250,
        "Sayfa Maratoncusu": 100,
        "Sayfa Maratoncusu II": 250,
        "Sayfa Maratoncusu III": 500,
        "Çok Okuyan Yazar": 100,
        "Kitap Koleksiyoncusu": 150,
        "İlk Not": 50,
        "Not Tutkunu": 100,
        "Detaycı": 200,
        "Popüler Yorumcu": 100,
        "İlk Takip": 50,
        "Takipçi Kazan!": 50,
        "Takipçi Ormanı": 150,
        "Sosyal Kuş": 100,
        "Süper Sosyal": 250,
        "Ortak Zevk": 50,
        "Kitap Arkadaşım": 100,
        "Seviye 2’ye Hoşgeldin": 50,
        "Seviye 5’e Hoşgeldin": 100,
        "Seviye 10’a Hoşgeldin": 200,
        "XP Canavarı": 50,
        "XP Yıldızı": 100,
        "XP Efsanesi": 200,
        "Okuma Maratoncusu": 100,
        "Ayın Maratoncusu": 250,
        "Yorumcu Arkadaş": 50,
        "Kitap Silici": 50
    }

    for ach_id, ach_name, ach_desc, ach_image, trigger_type, trigger_value in all_achievements:
        cursor.execute("SELECT 1 FROM user_achievements WHERE user_id=? AND achievement_id=?", (user_id, ach_id))
        if cursor.fetchone():
            continue

        unlocked = False

        # 📌 Trigger kontrolleri
        if trigger_type == "kitap_ekleme" and total_books >= trigger_value:
            unlocked = True
        elif trigger_type == "not_ekleme" and total_notes >= trigger_value:
            unlocked = True
        elif trigger_type == "yorum" and total_comments >= trigger_value:
            unlocked = True
        elif trigger_type == "takip" and total_following >= trigger_value:
            unlocked = True
        elif trigger_type == "takip_edilme" and total_followers >= trigger_value:
            unlocked = True
        elif trigger_type == "xp" and xp >= trigger_value:
            unlocked = True
        elif trigger_type == "level" and level >= trigger_value:
            unlocked = True
        elif trigger_type == "sayfa" and total_pages >= trigger_value:
            unlocked = True
        elif trigger_type == "haftalik_sayfa":
            cursor.execute("""
                SELECT SUM(page) FROM books 
                WHERE user_id=? AND date(created_at) >= date('now','-7 day')
            """, (user_id,))
            weekly_pages = cursor.fetchone()[0] or 0
            if weekly_pages >= trigger_value:
                unlocked = True
        elif trigger_type == "aylik_sayfa":
            cursor.execute("""
                SELECT SUM(page) FROM books 
                WHERE user_id=? AND date(created_at) >= date('now','-1 month')
            """, (user_id,))
            monthly_pages = cursor.fetchone()[0] or 0
            if monthly_pages >= trigger_value:
                unlocked = True
        elif trigger_type == "ortak_kitap":
            cursor.execute("""
                SELECT COUNT(*) 
                FROM books b1 
                JOIN books b2 ON b1.title = b2.title AND b1.user_id != b2.user_id
                WHERE b1.user_id=?
            """, (user_id,))
            ortak = cursor.fetchone()[0] or 0
            if ortak >= trigger_value:
                unlocked = True
        elif trigger_type == "silme":
            cursor.execute("SELECT COUNT(*) FROM deleted_books WHERE user_id=?", (user_id,))
            silinen = cursor.fetchone()[0] or 0
            if silinen >= trigger_value:
                unlocked = True

        if unlocked:
            cursor.execute(
                "INSERT INTO user_achievements (user_id, achievement_id) VALUES (?, ?)",
                (user_id, ach_id)
            )
            xp_to_add = achievement_xp.get(ach_name, 50)
            add_xp(user_id, xp_to_add, conn)
            print(f"[DEBUG] Açıldı: {ach_name}, +{xp_to_add} XP")

    if close_conn:
        conn.commit()
        conn.close()
    else:
        conn.commit()


if __name__ == "__main__":
    init_db()
    insert_achievements()
    
    # Test kullanıcı ekle
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (username, password, email) VALUES (?, ?, ?)",
            ("testuser", "1234", "test@example.com")
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()

    # Artık achievements kontrol edebilirsin
    check_achievements(1)