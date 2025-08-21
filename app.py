from flask import Flask, render_template, request, redirect, url_for, flash, session
from database import get_connection, init_db, add_xp
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "super_secret_key"  # session için gerekli

# Uygulama başlarken DB oluştur
init_db()

# Kullanıcı kutusu verisi
def get_user_box_data(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username, xp, level FROM users WHERE id=?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return {"username": "Bilinmiyor", "xp": 0, "level": 1, "progress": 0, "user_id": user_id}

    username, xp, level = row
    progress = (xp % 100) / 100 * 100
    return {"username": username, "xp": xp, "level": level, "progress": progress, "user_id": user_id}

# ------------------ ROUTES ------------------

@app.route("/")
def index():
    return render_template("login.html")

@app.route("/signup", methods=["POST"])
def signup():
    username = request.form.get("username")
    email = request.form.get("email")
    password = request.form.get("password")

    if not username or not email or not password:
        flash("⚠️ Tüm alanları doldurun!", "error")
        return redirect(url_for("index"))

    hashed_password = generate_password_hash(password)
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", 
                       (username, email, hashed_password))
        conn.commit()
        flash("✅ Kayıt başarılı! Şimdi giriş yapabilirsiniz.", "success")
    except sqlite3.IntegrityError:
        flash("⚠️ Bu kullanıcı adı zaten alınmış!", "error")
    finally:
        conn.close()

    return redirect(url_for("index"))

@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username")
    password = request.form.get("password")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, password FROM users WHERE username=?", (username,))
    user = cursor.fetchone()
    conn.close()

    if user:
        user_id, user_name, stored_hash = user
        if check_password_hash(stored_hash, password):
            session["user_id"] = user_id
            session["username"] = user_name
            flash("🎉 Başarıyla giriş yapıldı!", "success")
            return redirect(url_for("dashboard"))

    flash("❌ Kullanıcı adı veya şifre hatalı!", "error")
    return redirect(url_for("index"))

# ------------------ DASHBOARD ------------------

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        flash("⚠️ Lütfen giriş yapın!", "error")
        return redirect(url_for("index"))

    user_id = session["user_id"]
    user_box = get_user_box_data(user_id)

    conn = get_connection()
    cursor = conn.cursor()

    # Toplam kitap sayısı
    cursor.execute("SELECT COUNT(*) FROM books WHERE user_id=?", (user_id,))
    total_books = cursor.fetchone()[0]

    # Son okunan kitap
    cursor.execute(
        "SELECT title FROM books WHERE user_id=? AND read_date IS NOT NULL ORDER BY read_date DESC LIMIT 1",
        (user_id,)
    )
    last_book_row = cursor.fetchone()
    last_read_book = last_book_row[0] if last_book_row else "Henüz okunmuş kitap yok"

    # Haftalık hedef
    one_week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    cursor.execute(
        "SELECT COUNT(*) FROM books WHERE user_id=? AND read_date>=?",
        (user_id, one_week_ago)
    )
    weekly_completed = cursor.fetchone()[0]
    weekly_goal = f"{weekly_completed} / 3 Kitap"

    # Takipçiler ve takip edilenler
    cursor.execute("SELECT COUNT(*) FROM follows WHERE following_id=?", (user_id,))
    followers_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM follows WHERE follower_id=?", (user_id,))
    following_count = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "dashboard.html",
        user_box=user_box,
        username=user_box['username'],  # Kullanıcı adını template’e gönderiyoruz
        total_books=total_books,
        last_read_book=last_read_book,
        weekly_goal=weekly_goal,
        followers_count=followers_count,
        following_count=following_count
    )

# ------------------ LOGOUT ------------------

@app.route("/logout")
def logout():
    session.clear()
    flash("👋 Çıkış yapıldı.", "info")
    return redirect(url_for("index"))

# ------------------ ADD BOOK ------------------

@app.route("/add_book", methods=["GET", "POST"])
def add_book():
    if "user_id" not in session:
        flash("⚠️ Lütfen giriş yapın!", "error")
        return redirect(url_for("index"))

    user_box = get_user_box_data(session["user_id"])

    if request.method == "POST":
        title = request.form.get("title").strip()
        author = request.form.get("author").strip()
        read_date = request.form.get("read_date")
        notes = request.form.get("notes")
        page = request.form.get("page")
        page = int(page) if page and page.isdigit() else None

        if not title or not author:
            flash("⚠️ Kitap adı ve yazar alanları zorunludur.", "error")
            return redirect(url_for("add_book"))

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM books WHERE title=? AND author=? AND user_id=?", 
                       (title, author, session["user_id"]))
        book_row = cursor.fetchone()

        if book_row:
            book_id = book_row[0]
        else:
            cursor.execute("INSERT INTO books (user_id, title, author, page, read_date) VALUES (?, ?, ?, ?, ?)", 
                           (session["user_id"], title, author, page, read_date if read_date else None))
            book_id = cursor.lastrowid
            add_xp(session["user_id"], 10, conn=conn)

        if notes:
            cursor.execute("INSERT INTO notes (book_id, user_id, note) VALUES (?, ?, ?)",
                           (book_id, session["user_id"], notes))

        conn.commit()
        conn.close()

        flash(f"✅ '{title}' kitabı başarıyla eklendi! (+10 XP)", "success")
        return redirect(url_for("dashboard"))

    return render_template("addbook.html", user_box=user_box)

# ------------------ MY BOOKS ------------------

@app.route("/my_books")
def my_books():
    if "user_id" not in session:
        flash("⚠️ Lütfen giriş yapın!", "error")
        return redirect(url_for("index"))

    user_box = get_user_box_data(session["user_id"])
    user_id = session["user_id"]
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, title, author, read_date, page FROM books WHERE user_id=?", (user_id,))
    books_rows = cursor.fetchall()

    books_list = []
    for book in books_rows:
        book_id, title, author, read_date, page = book
        cursor.execute("SELECT note FROM notes WHERE book_id=? AND user_id=?", (book_id, user_id))
        notes = [n[0] for n in cursor.fetchall()]
        notes_text = ' '.join(notes) if notes else ''
        books_list.append({
            "id": book_id,
            "title": title,
            "author": author,
            "read_date": read_date,
            "page": page,
            "notes": notes_text
        })

    total_pages = sum([book["page"] for book in books_list if book["page"]])
    authors = [book["author"] for book in books_list]
    most_read_author = max(set(authors), key=authors.count) if authors else "Yok"
    total_books = len(books_list)

    conn.close()

    return render_template("mybooks.html",
                           user_box=user_box,
                           books=books_list,
                           total_pages=total_pages,
                           most_read_author=most_read_author,
                           total_books=total_books)

# ------------------ LIBRARY ------------------
@app.route("/library")
def library():
    if "user_id" not in session:
        flash("⚠️ Lütfen giriş yapın!", "error")
        return redirect(url_for("index"))

    user_box = get_user_box_data(session["user_id"])
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT b.title, b.author, b.page, u.username
        FROM books b
        JOIN users u ON b.user_id = u.id
        ORDER BY b.title ASC
    """)
    rows = cursor.fetchall()
    conn.close()

    books_dict = {}
    for title, author, page, username in rows:
        key = (title.strip().lower(), author.strip().lower())
        if key not in books_dict:
            books_dict[key] = {"title": title, "author": author, "page": page, "users": [username]}
        else:
            if username not in books_dict[key]["users"]:
                books_dict[key]["users"].append(username)

    books = list(books_dict.values())
    return render_template("library.html", user_box=user_box, books=books)


# ------------------ SOCIAL ------------------
@app.route("/social")
def social():
    if "user_id" not in session:
        flash("⚠️ Lütfen giriş yapın!", "error")
        return redirect(url_for("index"))

    user_box = get_user_box_data(session["user_id"])
    q = request.args.get("q", "").strip()
    conn = get_connection()
    cursor = conn.cursor()

    if q:
        cursor.execute("SELECT id, username FROM users WHERE username LIKE ?", ('%' + q + '%',))
    else:
        cursor.execute("SELECT id, username FROM users")

    users = cursor.fetchall()
    conn.close()
    users_list = [{"id": u[0], "username": u[1]} for u in users]

    return render_template("social.html", user_box=user_box, users=users_list)


# ------------------ USER PROFILE ------------------
@app.route("/user/<int:user_id>")
def user_profile(user_id):
    if "user_id" not in session:
        flash("⚠️ Lütfen giriş yapın!", "error")
        return redirect(url_for("index"))

    current_user_id = session["user_id"]
    user_box = get_user_box_data(user_id)  # 👈 profil sahibinin bilgisi

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, username FROM users WHERE id=?", (user_id,))
    user_row = cursor.fetchone()
    if not user_row:
        flash("Kullanıcı bulunamadı!", "error")
        return redirect(url_for("social"))
    user = {"id": user_row[0], "username": user_row[1]}

    cursor.execute("SELECT b.id, b.title, b.author, b.read_date, b.page FROM books b WHERE b.user_id=? ORDER BY b.title ASC", (user_id,))
    books_rows = cursor.fetchall()
    books = []
    for r in books_rows:
        book_id, title, author, read_date, page = r
        cursor.execute("SELECT note FROM notes WHERE book_id=? AND user_id=? ORDER BY id DESC", (book_id, user_id))
        user_notes = [n[0] for n in cursor.fetchall()]
        books.append({"id": book_id, "title": title, "author": author, "read_date": read_date, "page": page, "notes": user_notes})

    cursor.execute("SELECT COUNT(*), SUM(page) FROM books WHERE user_id=?", (user_id,))
    total_books, total_pages = cursor.fetchone()
    cursor.execute("SELECT author, COUNT(*) as cnt FROM books WHERE user_id=? GROUP BY author ORDER BY cnt DESC LIMIT 1", (user_id,))
    most_author_row = cursor.fetchone()
    most_author = most_author_row[0] if most_author_row else "Yok"

    stats = {"total_books": total_books or 0, "total_pages": total_pages or 0, "most_author": most_author}

    cursor.execute("SELECT title, author FROM books WHERE user_id=? AND title IN (SELECT title FROM books WHERE user_id=?)", (user_id, current_user_id))
    common_books = cursor.fetchall()

    cursor.execute("SELECT 1 FROM follows WHERE follower_id=? AND following_id=?", (current_user_id, user_id))
    is_following = cursor.fetchone() is not None

    conn.close()

    return render_template("user_profile.html", user_box=user_box, user=user, books=books, stats=stats, common_books=common_books, is_following=is_following, current_user_id=current_user_id)

@app.route("/toggle_follow/<int:user_id>", methods=["POST"])
def toggle_follow(user_id):
    current_user_id = session["user_id"]

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM follows WHERE follower_id=? AND following_id=?", (current_user_id, user_id))
    is_following = cursor.fetchone() is not None

    if is_following:
        cursor.execute("DELETE FROM follows WHERE follower_id=? AND following_id=?", (current_user_id, user_id))
    else:
        cursor.execute("INSERT INTO follows (follower_id, following_id) VALUES (?, ?)", (current_user_id, user_id))
    
    conn.commit()
    conn.close()
    return redirect(url_for("user_profile", user_id=user_id))


@app.route("/followers/<string:type>")
def followers_list(type):
    if "user_id" not in session:
        flash("⚠️ Lütfen giriş yapın!", "error")
        return redirect(url_for("index"))

    user_id = session["user_id"]
    user_box = get_user_box_data(user_id)  # 👈 Kullanıcı verisi alınıyor

    conn = get_connection()
    cursor = conn.cursor()

    users_list = []
    if type == "followers":
        cursor.execute("""
            SELECT u.id, u.username FROM follows f
            JOIN users u ON f.follower_id = u.id
            WHERE f.following_id=?
        """, (user_id,))
        users_list = cursor.fetchall()
        page_title = "Takipçilerin"
    elif type == "following":
        cursor.execute("""
            SELECT u.id, u.username FROM follows f
            JOIN users u ON f.following_id = u.id
            WHERE f.follower_id=?
        """, (user_id,))
        users_list = cursor.fetchall()
        page_title = "Takip Ettiklerin"
    else:
        flash("Geçersiz parametre!", "error")
        return redirect(url_for("dashboard"))

    conn.close()

    return render_template(
        "followers.html",
        users=users_list,
        page_title=page_title,
        user_box=user_box  # 👈 user_box gönderildi
    )

    
@app.route("/bookdetails/<string:title>/<string:author>")
def bookdetails(title, author):
    if "user_id" not in session:
        flash("⚠️ Lütfen giriş yapın!", "error")
        return redirect(url_for("index"))

    user_id = session["user_id"]
    user_box = get_user_box_data(user_id)  # 👈 Kullanıcı verisini alıyoruz

    conn = get_connection()
    cursor = conn.cursor()

    # Kitap detaylarını ve notları çek
    cursor.execute("""
        SELECT b.id, b.title, b.author, b.page, n.note, u.username
        FROM books b
        LEFT JOIN notes n ON b.id = n.book_id
        LEFT JOIN users u ON n.user_id = u.id
        WHERE b.title=? AND b.author=?
        ORDER BY n.id DESC
    """, (title, author))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        flash("Kitap bulunamadı!", "error")
        return redirect(url_for("library"))

    # Kitap bilgisi
    book = {
        "title": rows[0][1],
        "author": rows[0][2],
        "page": rows[0][3]
    }

    # Notları hazırlama
    notes = [{"note": r[4], "username": r[5]} for r in rows if r[4] is not None]

    return render_template("bookdetails.html", book=book, notes=notes, user_box=user_box)  # 👈 user_box eklendi
@app.route("/leaderboard")
def leaderboard():
    conn = get_connection()
    cursor = conn.cursor()

    # user_box için veri
    user_id = session.get("user_id")  # giriş yapan kullanıcı
    user_box = None
    if user_id:
        cursor.execute("SELECT username, xp, level FROM users WHERE id=?", (user_id,))
        row = cursor.fetchone()
        if row:
            username, xp, level = row
            progress = (xp % 100)
            user_box = {
                "username": username,
                "xp": xp,
                "level": level,
                "progress": progress
            }

    # 1. En çok kitap okuyan kullanıcılar
    cursor.execute("""
        SELECT u.username, COUNT(b.id) as total_books
        FROM users u
        LEFT JOIN books b ON u.id = b.user_id
        GROUP BY u.id
        ORDER BY total_books DESC
        LIMIT 10
    """)
    top_books = cursor.fetchall()

    # 2. En çok sayfa okuyan kullanıcılar
    cursor.execute("""
        SELECT u.username, SUM(b.page) as total_pages
        FROM users u
        LEFT JOIN books b ON u.id = b.user_id
        GROUP BY u.id
        ORDER BY total_pages DESC
        LIMIT 10
    """)
    top_pages = cursor.fetchall()

    # 3. Bu ay en çok kitap okuyan kullanıcılar
    this_month = datetime.now().strftime("%Y-%m")
    cursor.execute("""
        SELECT u.username, COUNT(b.id) as books_this_month
        FROM users u
        LEFT JOIN books b ON u.id = b.user_id
        WHERE b.read_date LIKE ?
        GROUP BY u.id
        ORDER BY books_this_month DESC
        LIMIT 10
    """, (f"{this_month}%",))
    top_month = cursor.fetchall()

    conn.close()

    return render_template("leaderboard.html",
                           top_books=top_books,
                           top_pages=top_pages,
                           top_month=top_month,
                           user_box=user_box)


@app.route("/add_comment/<int:book_id>", methods=["POST"])
def add_comment(book_id):
    if "user_id" not in session:
        flash("Yorum eklemek için giriş yapmalısınız.", "warning")
        return redirect(url_for("login"))

    comment_text = request.form.get("comment")
    user_id = session["user_id"]

    if not comment_text or comment_text.strip() == "":
        flash("Yorum boş olamaz.", "danger")
        return redirect(request.referrer)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
    "INSERT INTO comments (book_id, user_id, comment, created_at) VALUES (?, ?, ?, ?)",
    (book_id, user_id, comment_text, datetime.now())
)

# Yorum ekledikten sonra XP ekle
    add_xp(user_id, 2, conn=conn)
    conn.commit()
    conn.close()

    flash("Yorumunuz eklendi!", "success")
    return redirect(request.referrer)


# ------------------ FEED ------------------
@app.route("/feed", methods=["GET", "POST"])
def feed():
    if "user_id" not in session:
        flash("⚠️ Lütfen giriş yapın!", "error")
        return redirect(url_for("index"))

    user_id = session["user_id"]
    user_box = get_user_box_data(user_id)  # Kullanıcının xp, level, username vs.

    conn = get_connection()
    cursor = conn.cursor()

    # Feed için kitapları al
    cursor.execute("""
        SELECT b.id, b.title, b.author, b.page, b.read_date, b.user_id, u.username
        FROM books b
        JOIN users u ON b.user_id = u.id
        WHERE b.user_id IN (SELECT following_id FROM follows WHERE follower_id = ?) OR b.user_id = ?
        ORDER BY b.created_at DESC
    """, (user_id, user_id))
    feed_items = cursor.fetchall()

    feed_data = []
    for book in feed_items:
        book_id, title, author, page, read_date, book_user_id, username = book

        # Yorumları al
        cursor.execute("""
            SELECT c.comment, u.username FROM comments c
            JOIN users u ON c.user_id = u.id
            WHERE c.book_id = ?
            ORDER BY c.created_at ASC
        """, (book_id,))
        comments = cursor.fetchall()

        feed_data.append({
            "book_id": book_id,
            "title": title,
            "author": author,
            "page": page,
            "read_date": read_date,
            "username": username,
            "comments": comments
        })

    conn.close()

    return render_template(
        "feed.html",
        user_box=user_box,   # Burada user_box’ı template’e gönderiyoruz
        xp=user_box.get("xp", 0),     # XP bilgisi
        level=user_box.get("level", 1), # Level bilgisi
        feed_data=feed_data
    )



if __name__ == "__main__":
    app.run(debug=True)
