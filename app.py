from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from database import get_connection, init_db, add_xp, check_achievements,insert_achievements
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime, timedelta
app = Flask(__name__)
app.secret_key = "super_secret_key"  # session için gerekli

# Uygulama başlarken DB oluştur
init_db()
insert_achievements()
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

        # Aynı kitap var mı kontrol et
        cursor.execute("SELECT id FROM books WHERE title=? AND author=? AND user_id=?", 
                       (title, author, session["user_id"]))
        book_row = cursor.fetchone()

        if book_row:
            book_id = book_row[0]
        else:
            # Kitabı ekle
            cursor.execute(
                "INSERT INTO books (user_id, title, author, page, read_date) VALUES (?, ?, ?, ?, ?)", 
                (session["user_id"], title, author, page, read_date if read_date else None)
            )
            book_id = cursor.lastrowid

            # XP ekle
            add_xp(session["user_id"], 10, conn=conn)

        # Not ekleme varsa
        if notes:
            cursor.execute(
                "INSERT INTO notes (book_id, user_id, note) VALUES (?, ?, ?)",
                (book_id, session["user_id"], notes)
            )

        # Tüm başarımları tek sefer kontrol et
        check_achievements(session["user_id"], conn=conn)

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

    user_id = session["user_id"]
    user_box = get_user_box_data(user_id)
    q = request.args.get("q", "").strip()
    chat_with_id = request.args.get("chat_with", type=int)

    conn = get_connection()
    cursor = conn.cursor()

    # Kullanıcı arama
    if q:
        cursor.execute("SELECT id, username FROM users WHERE username LIKE ?", ('%' + q + '%',))
    else:
        cursor.execute("SELECT id, username FROM users")
    users = cursor.fetchall()
    users_list = [{"id": u[0], "username": u[1]} for u in users]

    # Eğer chat_with_id yoksa, son mesajla konuştuğun kullanıcıyı al
    if not chat_with_id:
        cursor.execute("""
            SELECT sender_id, receiver_id
            FROM private_messages
            WHERE sender_id=? OR receiver_id=?
            ORDER BY created_at DESC LIMIT 1
        """, (user_id, user_id))
        last_msg = cursor.fetchone()
        if last_msg:
            chat_with_id = last_msg[0] if last_msg[0] != user_id else last_msg[1]

    # Genel mesajları DB'den çek
    cursor.execute("""
        SELECT gc.content, u.username, gc.created_at
        FROM general_chat gc
        JOIN users u ON gc.user_id = u.id
        ORDER BY gc.created_at ASC
    """)
    general_messages = [
        (row[0], row[1], row[2][:16])  # YYYY-MM-DD HH:MM format
        for row in cursor.fetchall()
    ]

    # Kişisel mesajlar sadece seçilen kişi ile
    private_messages = []
    if chat_with_id:
        cursor.execute("""
            SELECT pm.content, u.username, pm.created_at, pm.sender_id, pm.receiver_id
            FROM private_messages pm
            JOIN users u ON pm.sender_id = u.id
            WHERE (pm.sender_id=? AND pm.receiver_id=?) OR (pm.sender_id=? AND pm.receiver_id=?)
            ORDER BY pm.created_at ASC
        """, (user_id, chat_with_id, chat_with_id, user_id))
        private_messages = [
            (row[0], row[1], row[2][:16], row[3], row[4])
            for row in cursor.fetchall()
        ]

    conn.close()

    return render_template(
        "social.html",
        user_box=user_box,
        users=users_list,
        general_messages=general_messages,
        private_messages=private_messages,
        current_user_id=user_id,
        chat_with_id=chat_with_id
    )

@app.route("/get_general_messages")
def get_general_messages():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT gc.content, u.username, gc.created_at
        FROM general_chat gc
        JOIN users u ON gc.user_id = u.id
        ORDER BY gc.created_at ASC
    """)
    messages = [
        {"msg": row[0], "username": row[1], "time": row[2][:16]}  # YYYY-MM-DD HH:MM
        for row in cursor.fetchall()
    ]
    conn.close()
    return jsonify(messages)


@app.route("/send_general_message", methods=["POST"])
def send_general_message():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    user_id = session["user_id"]
    message = request.form.get("message", "").strip()

    if not message:
        return jsonify({"error": "Empty message"}), 400

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO general_chat (user_id, content, created_at) VALUES (?, ?, ?)",
                   (user_id, message, datetime.now()))
    conn.commit()
    conn.close()

    # Mesaj gönderildikten sonra saat bilgisini döndür
    time_str = datetime.now().strftime("%H:%M")
    return jsonify({"time": time_str})


# ------------------ SEND PRIVATE MESSAGE ------------------
@app.route("/send_private_message", methods=["POST"])
def send_private_message():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    user_id = session["user_id"]
    receiver_id = int(request.form.get("receiver_id"))
    message = request.form.get("message", "").strip()

    if not message:
        return jsonify({"error": "Empty message"}), 400

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO private_messages (sender_id, receiver_id, content, created_at) VALUES (?, ?, ?, ?)",
        (user_id, receiver_id, message, datetime.now())
    )
    conn.commit()
    conn.close()

    time_str = datetime.now().strftime("%H:%M")
    return jsonify({"time": time_str})

@app.route("/get_private_messages/<int:user_id>")
def get_private_messages(user_id):
    if "user_id" not in session:
        return jsonify([])

    current_id = session["user_id"]
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT pm.content, u.username, pm.created_at, pm.sender_id
        FROM private_messages pm
        JOIN users u ON pm.sender_id = u.id
        WHERE (pm.sender_id=? AND pm.receiver_id=?) OR (pm.sender_id=? AND pm.receiver_id=?)
        ORDER BY pm.created_at
    """, (current_id, user_id, user_id, current_id))
    msgs = cursor.fetchall()
    conn.close()

    return jsonify([{
        "msg": m[0],
        "username": m[1],
        "time": m[2].split(" ")[1][:5],  # sadece HH:MM
        "sender_id": m[3]
    } for m in msgs])

@app.route("/user/<int:user_id>", methods=["GET", "POST"])
def user_profile(user_id):
    if "user_id" not in session:
        flash("⚠️ Lütfen giriş yapın!", "error")
        return redirect(url_for("index"))

    current_user_id = session["user_id"]
    user_box = get_user_box_data(user_id)  # Profil sahibinin bilgisi

    conn = get_connection()
    cursor = conn.cursor()

    # POST: Yorum ekleme
    if request.method == "POST" and "comment" in request.form:
        comment_text = request.form["comment"].strip()
        if comment_text:
            cursor.execute(
                "INSERT INTO comments (book_id, user_id, comment) VALUES (?, ?, ?)",
                (0, current_user_id, comment_text)
            )
            conn.commit()
            conn.close()
            return jsonify({"success": True, "time": datetime.now().strftime("%H:%M")})
        conn.close()
        return jsonify({"success": False}), 400

    # Profil bilgisi
    cursor.execute("SELECT id, username FROM users WHERE id=?", (user_id,))
    user_row = cursor.fetchone()
    if not user_row:
        flash("Kullanıcı bulunamadı!", "error")
        conn.close()
        return redirect(url_for("social"))
    user = {"id": user_row[0], "username": user_row[1]}

    # Takip durumu
    cursor.execute("SELECT 1 FROM follows WHERE follower_id=? AND following_id=?", (current_user_id, user_id))
    is_following = bool(cursor.fetchone())

    # Takipçi ve takip edilen sayısı
    cursor.execute("SELECT COUNT(*) FROM follows WHERE following_id=?", (user_id,))
    followers_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM follows WHERE follower_id=?", (user_id,))
    following_count = cursor.fetchone()[0]

    # Kullanıcının kitapları
    cursor.execute("""
        SELECT b.id, b.title, b.author, b.read_date, b.page
        FROM books b
        WHERE b.user_id=?
        ORDER BY b.title ASC
    """, (user_id,))
    books_rows = cursor.fetchall()
    books = []
    for r in books_rows:
        book_id, title, author, read_date, page = r
        cursor.execute("SELECT note FROM notes WHERE book_id=? AND user_id=? ORDER BY id DESC", (book_id, user_id))
        user_notes = [n[0] for n in cursor.fetchall()]
        books.append({
            "id": book_id,
            "title": title,
            "author": author,
            "read_date": read_date,
            "page": page,
            "notes": user_notes
        })

    # Ortak kitaplar
    cursor.execute("""
        SELECT b1.id, b1.title, b1.author, b1.read_date, b1.page
        FROM books b1
        JOIN books b2 ON b1.title = b2.title AND b2.user_id = ?
        WHERE b1.user_id = ?
    """, (current_user_id, user_id))
    common_books_rows = cursor.fetchall()
    common_books = []
    for r in common_books_rows:
        book_id, title, author, read_date, page = r
        common_books.append({
            "id": book_id,
            "title": title,
            "author": author,
            "read_date": read_date,
            "page": page
        })

    # Kullanıcının başarımları
    cursor.execute("""
        SELECT a.name, a.description, a.image
        FROM achievements a
        JOIN user_achievements ua ON ua.achievement_id = a.id
        WHERE ua.user_id=?
        ORDER BY ua.unlocked_at DESC
    """, (user_id,))
    user_achievements = cursor.fetchall()

    # Private mesajlar
    cursor.execute("""
        SELECT pm.content, u.username, pm.created_at, pm.sender_id, pm.receiver_id
        FROM private_messages pm
        JOIN users u ON u.id = pm.sender_id
        WHERE (pm.sender_id=? AND pm.receiver_id=?) OR (pm.sender_id=? AND pm.receiver_id=?)
        ORDER BY pm.created_at ASC
    """, (current_user_id, user_id, user_id, current_user_id))
    private_messages = cursor.fetchall()

    # Yorumlar
    cursor.execute("""
        SELECT c.comment, u.username, c.created_at
        FROM comments c
        JOIN users u ON u.id = c.user_id
        WHERE c.book_id=0
        ORDER BY c.created_at ASC
    """)
    comments = cursor.fetchall()

    conn.close()

    return render_template(
        "user_profile.html",
        user=user,
        user_box=user_box,
        books=books,
        common_books=common_books,
        user_achievements=user_achievements,
        private_messages=private_messages,
        comments=comments,
        current_user_id=current_user_id,
        chat_with_id=user_id,
        is_following=is_following,
        followers_count=followers_count,
        following_count=following_count
    )



@app.route("/toggle_follow/<int:user_id>", methods=["POST"])
def toggle_follow(user_id):
    current_user_id = session["user_id"]
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM follows WHERE follower_id=? AND following_id=?", (current_user_id, user_id))
    is_following = cursor.fetchone() is not None

    if is_following:
        cursor.execute("DELETE FROM follows WHERE follower_id=? AND following_id=?", (current_user_id, user_id))
    else:
        cursor.execute("INSERT INTO follows (follower_id, following_id) VALUES (?, ?)", (current_user_id, user_id))

    # Takip ettikleri sayısını çek
    cursor.execute("SELECT COUNT(*) FROM follows WHERE follower_id=?", (current_user_id,))
    total_following = cursor.fetchone()[0]

    # Başarımları kontrol et
    check_achievements(user_id, conn=conn)

    conn.commit()
    conn.close()
    return redirect(url_for("user_profile", user_id=user_id))

@app.route("/follow/<int:user_id>", methods=["POST"])
def follow_user(user_id):
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Giriş yapmalısınız."}), 403

    current_user_id = session["user_id"]
    conn = get_connection()
    cursor = conn.cursor()

    # Takip/Unfollow kontrolü
    cursor.execute("SELECT 1 FROM follows WHERE follower_id=? AND following_id=?", (current_user_id, user_id))
    exists = cursor.fetchone()
    if exists:
        cursor.execute("DELETE FROM follows WHERE follower_id=? AND following_id=?", (current_user_id, user_id))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "following": False})
    else:
        cursor.execute("INSERT INTO follows (follower_id, following_id) VALUES (?, ?)", (current_user_id, user_id))
        conn.commit()
        conn.close()
        # Achievements kontrolü
        check_achievements(current_user_id)
        return jsonify({"success": True, "following": True})

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

    # Yorum ekle
    cursor.execute(
        "INSERT INTO comments (book_id, user_id, comment, created_at) VALUES (?, ?, ?, ?)",
        (book_id, user_id, comment_text, datetime.now())
    )

    # XP ekle
    add_xp(user_id, 2, conn=conn)

    # Toplam yorum sayısını çek
    cursor.execute("SELECT COUNT(*) FROM comments WHERE user_id=?", (user_id,))
    total_comments = cursor.fetchone()[0]

    # Başarımları kontrol et (yorum ekleme)
    check_achievements(user_id, conn=conn)

    # Seviye check (XP sonrası)
    cursor.execute("SELECT level FROM users WHERE id=?", (user_id,))
    new_level = cursor.fetchone()[0]
    check_achievements(user_id, conn=conn)

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

@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit_book(id):
    if "user_id" not in session:
        flash("⚠️ Lütfen giriş yapın!", "error")
        return redirect(url_for("index"))

    user_id = session["user_id"]
    conn = get_connection()
    cursor = conn.cursor()

    # Kitap kontrolü
    cursor.execute(
        "SELECT id, title, author, read_date, page FROM books WHERE id=? AND user_id=?",
        (id, user_id)
    )
    book = cursor.fetchone()
    if not book:
        conn.close()
        flash("❌ Bu kitabı düzenleme izniniz yok veya kitap bulunamadı.", "error")
        return redirect(url_for("my_books"))

    # Mevcut notu çek
    cursor.execute("SELECT note FROM notes WHERE book_id=? AND user_id=?", (id, user_id))
    note_row = cursor.fetchone()
    note_text = note_row[0] if note_row else ""

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        author = (request.form.get("author") or "").strip()
        read_date = request.form.get("read_date") or None
        page_raw = request.form.get("page")
        note = request.form.get("note") or ""

        page = int(page_raw) if page_raw and str(page_raw).isdigit() else None

        if not title or not author:
            flash("⚠️ Başlık ve Yazar alanları zorunludur.", "error")
            conn.close()
            return redirect(url_for("edit_book", id=id))

        # Kitabı güncelle
        cursor.execute(
            "UPDATE books SET title=?, author=?, read_date=?, page=? WHERE id=? AND user_id=?",
            (title, author, read_date, page, id, user_id)
        )

        # Notu ekle veya güncelle
        if note_row:
            cursor.execute("UPDATE notes SET note=? WHERE book_id=? AND user_id=?", (note, id, user_id))
        else:
            cursor.execute("INSERT INTO notes (book_id, user_id, note) VALUES (?, ?, ?)", (id, user_id, note))

        conn.commit()
        conn.close()

        flash("✅ Kitap ve not başarıyla güncellendi!", "success")
        return redirect(url_for("my_books"))

    user_box = get_user_box_data(user_id)
    conn.close()
    return render_template("edit_book.html", book=book, note_text=note_text, user_box=user_box)



@app.route("/delete_book/<int:book_id>", methods=["POST"])
def delete_book(book_id):
    if "user_id" not in session:
        flash("⚠️ Lütfen giriş yapın!", "error")
        return redirect(url_for("index"))

    conn = get_connection()
    cursor = conn.cursor()

    # Silmeden önce silinen kitabı kaydet
    cursor.execute("""
        INSERT INTO deleted_books (user_id, book_id)
        VALUES (?, ?)
    """, (session["user_id"], book_id))

    # Kitabı sil
    cursor.execute("DELETE FROM books WHERE id=? AND user_id=?", (book_id, session["user_id"]))

    conn.commit()
    conn.close()

    flash("🗑️ Kitap başarıyla silindi!", "success")
    return redirect(url_for("my_books"))



@app.route("/achievements")
def achievements():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    # Yeni başarımları kontrol et
    check_achievements(user_id)

    conn = get_connection()
    cursor = conn.cursor()

    # Kullanıcı bilgilerini al (user_box için)
    cursor.execute("SELECT username, xp, level FROM users WHERE id=?", (user_id,))
    user_row = cursor.fetchone()
    user_box = {
        "username": user_row[0],
        "xp": user_row[1],
        "level": user_row[2],
        "progress": user_row[1] % 100  # progress bar için
    }

    # Kullanıcının tüm başarımlarını al
# Kullanıcının tüm başarımlarını al (güncel ve güvenli versiyon)
    cursor.execute("""
    SELECT a.id, a.name, a.description,
           CASE WHEN ua.user_id IS NOT NULL THEN 1 ELSE 0 END as unlocked
    FROM achievements a
    LEFT JOIN user_achievements ua
    ON a.id = ua.achievement_id AND ua.user_id = ?
""", (user_id,))
    achievements_data = cursor.fetchall()

    # Listeye dönüştür
    achievements_list = []
    for ach in achievements_data:
        achievements_list.append({
            "id": ach[0],
            "name": ach[1],
            "description": ach[2],
            "unlocked": bool(ach[3]),
            "image": f"{ach[0]}.png"  # Her başarıma karşılık gelen görsel dosyası (static/achievements/ içinde)
        })

    conn.close()

    return render_template("achievements.html", user_box=user_box, achievements=achievements_list)

if __name__ == "__main__":
    app.run(debug=True)
