"""
REWORLD — Flask (isteğe bağlı)
Statik HTML + assets sunumu ve /api/* uçları
"""

import os
from dotenv import load_dotenv
import sqlite3
import json
import urllib.request
import urllib.error
import re
import uuid
import google.generativeai as genai
import webbrowser
import threading

from flask import Flask, abort, jsonify, request, send_from_directory, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(ROOT, "yenidehayat.db")
TEMPLETES_PATH = os.path.join(ROOT, "templetes")
# .env dosyasındaki verileri sisteme yükle
load_dotenv()

# Artık anahtarı güvenli bir şekilde değişkene atayabiliriz
raw_key = os.getenv("GEMINI_API_KEY")
GEMINI_API_KEY = raw_key.strip() if raw_key else None

if not GEMINI_API_KEY:
    print("HATA: GEMINI_API_KEY .env dosyasında bulunamadı, özellikler çalışmayacak!")
else:
    genai.configure(api_key=GEMINI_API_KEY)

ALLOWED_HTML = {
    "index.html",
    "ilanlar.html",
    "kitaplar.html",
    "kiyafetler.html",
    "gida.html",
    "bagis.html",
    "detay.html",
}

app = Flask(__name__, static_folder="assets", template_folder="templetes")
CORS(app)
app.secret_key = "reworld_secret_key_2024"  # Güvenli bir anahtar kullan


def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, username, email FROM users WHERE id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    if user:
        return {"id": user[0], "username": user[1], "email": user[2]}
    return None


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS ilanlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            kategori TEXT NOT NULL,
            baslik TEXT NOT NULL,
            aciklama TEXT,
            sehir TEXT NOT NULL,
            iletisim TEXT NOT NULL,
            tarih TEXT DEFAULT CURRENT_TIMESTAMP,
            onaylandi INTEGER DEFAULT 0,
            gorsel_yolu TEXT,
            silme_kodu TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """
    )
    # Yeni sütunları mevcut veritabanına ekle (zaten varsa hatayı yoksay)
    try:
        c.execute("ALTER TABLE ilanlar ADD COLUMN gorsel_yolu TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE ilanlar ADD COLUMN silme_kodu TEXT")
    except sqlite3.OperationalError:
        pass

    # Users tablosu
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.commit()
    conn.close()

@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    if not username or not email or not password:
        return jsonify({"hata": "Tüm alanları doldurun"}), 400

    if len(password) < 6:
        return jsonify({"hata": "Şifre en az 6 karakter olmalı"}), 400

    password_hash = generate_password_hash(password)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                  (username, email, password_hash))
        user_id = c.lastrowid
        conn.commit()
        session['user_id'] = user_id
        return jsonify({"mesaj": "Kayıt başarılı", "user": {"id": user_id, "username": username, "email": email}}), 201
    except sqlite3.IntegrityError:
        return jsonify({"hata": "Kullanıcı adı veya e-posta zaten kullanılıyor"}), 400
    finally:
        conn.close()


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"hata": "E-posta ve şifre gerekli"}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT id, username, email, password_hash FROM users WHERE email=?", (email,))
    user = c.fetchone()
    conn.close()

    if user and check_password_hash(user[3], password):
        session['user_id'] = user[0]
        return jsonify({"mesaj": "Giriş başarılı", "user": {"id": user[0], "username": user[1], "email": user[2]}}), 200
    else:
        return jsonify({"hata": "Geçersiz e-posta veya şifre"}), 401


@app.route("/api/logout", methods=["POST"])
def logout():
    session.pop('user_id', None)
    return jsonify({"mesaj": "Çıkış yapıldı"}), 200


@app.route("/api/user", methods=["GET"])
def get_user():
    user = get_current_user()
    if user:
        return jsonify({"user": user}), 200
    else:
        return jsonify({"hata": "Giriş yapmamışsınız"}), 401


@app.route("/api/ilanlar", methods=["GET"])
def get_ilanlar():
    kategori = request.args.get("kategori", None)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    if kategori:
        c.execute(
            "SELECT id, kategori, baslik, aciklama, sehir, tarih, gorsel_yolu FROM ilanlar WHERE onaylandi=1 AND kategori=? ORDER BY tarih DESC",
            (kategori,),
        )
    else:
        c.execute("SELECT id, kategori, baslik, aciklama, sehir, tarih, gorsel_yolu FROM ilanlar WHERE onaylandi=1 ORDER BY tarih DESC")

    rows = c.fetchall()
    conn.close()

    ilanlar = []
    for row in rows:
        ilanlar.append(
            {
                "id": row[0],
                "kategori": row[1],
                "baslik": row[2],
                "aciklama": row[3],
                "sehir": row[4],
                "tarih": row[5],
                "gorsel": row[6] if row[6] else "",
            }
        )

    return jsonify({"ilanlar": ilanlar, "toplam": len(ilanlar)})


@app.route("/api/ilan-olustur", methods=["POST"])
def create_ilan():
    user = get_current_user()
    if not user:
        return jsonify({"hata": "İlan oluşturmak için giriş yapmalısınız"}), 401

    if request.is_json:
        data = request.get_json() or {}
    else:
        data = request.form.to_dict()

    required = ["kategori", "baslik", "sehir", "iletisim"]
    for field in required:
        if not data.get(field):
            return jsonify({"hata": f"{field} alanı zorunludur"}), 400

    moderasyon = ai_moderasyon(
        data.get("baslik", ""), data.get("aciklama", ""))

    if not moderasyon["uygun"]:
        return jsonify(
            {
                "hata": "İlan ticari içerik barındırıyor veya platform kurallarına uymuyor.",
                "sebep": moderasyon["sebep"],
            }
        ), 400

    gorsel_yolu = ""
    if "gorsel" in request.files:
        file = request.files["gorsel"]
        if file.filename:
            uploads_dir = os.path.join(ROOT, "assets", "uploads")
            os.makedirs(uploads_dir, exist_ok=True)
            ext = os.path.splitext(file.filename)[1] or ".png"
            new_filename = str(uuid.uuid4()) + ext
            file_path = os.path.join(uploads_dir, new_filename)
            file.save(file_path)
            gorsel_yolu = f"assets/uploads/{new_filename}"

    silme_kodu = str(uuid.uuid4()).replace("-", "")[:12]

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO ilanlar (user_id, kategori, baslik, aciklama, sehir, iletisim, onaylandi, gorsel_yolu, silme_kodu)
        VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
        """,
        (
            user["id"],
            data["kategori"],
            data["baslik"],
            data.get("aciklama", ""),
            data["sehir"],
            data["iletisim"],
            gorsel_yolu,
            silme_kodu
        ),
    )
    conn.commit()
    ilan_id = c.lastrowid
    conn.close()

    return jsonify({"mesaj": "İlanınız başarıyla yayınlandı!", "id": ilan_id, "gorsel": gorsel_yolu, "silme_kodu": silme_kodu}), 201


@app.route("/api/ilan/<int:ilan_id>", methods=["DELETE"])
def sil_ilan(ilan_id):
    user = get_current_user()
    if not user:
        return jsonify({"hata": "İlan silmek için giriş yapmalısınız"}), 401

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT user_id, silme_kodu, gorsel_yolu FROM ilanlar WHERE id=?", (ilan_id,))
    row = c.fetchone()

    if not row:
        conn.close()
        return jsonify({"hata": "İlan bulunamadı."}), 404

    db_user_id = row[0]
    db_kodu = row[1]
    gorsel = row[2]

    if db_user_id != user["id"]:
        conn.close()
        return jsonify({"hata": "Bu ilanı silme yetkiniz yok!"}), 403

    c.execute("DELETE FROM ilanlar WHERE id=?", (ilan_id,))
    conn.commit()
    conn.close()

    try:
        if gorsel and os.path.exists(os.path.join(ROOT, gorsel)):
            os.remove(os.path.join(ROOT, gorsel))
    except Exception:
        pass

    return jsonify({"mesaj": "İlan raflardan kalıcı olarak silindi."}), 200


@app.route("/api/ilan/<int:ilan_id>", methods=["GET"])
def getir_ilan(ilan_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT id, kategori, baslik, aciklama, sehir, iletisim, tarih, gorsel_yolu, user_id FROM ilanlar WHERE id=?", (ilan_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        return jsonify({"hata": "İlan bulunamadı"}), 404

    ilan = {
        "id": row[0],
        "kategori": row[1],
        "baslik": row[2],
        "aciklama": row[3],
        "sehir": row[4],
        "iletisim": row[5],
        "tarih": row[6],
        "gorsel_yolu": row[7],
        "user_id": row[8]
    }
    return jsonify({"ilan": ilan}), 200


@app.route("/api/talep", methods=["POST"])
def talep_et():
    data = request.get_json() or {}
    ilan_id = data.get("ilan_id")

    if not ilan_id:
        return jsonify({"hata": "ilan_id zorunludur"}), 400

    return jsonify({"mesaj": "Talebiniz bağışçıya iletildi! En kısa sürede dönüş yapılacak."})


def ai_moderasyon(baslik: str, aciklama: str) -> dict:
    ticari_kelimeler = [
        r"\bsatılık\b",
        r"\bsatıslık\b",
        r"\bsatış\b",
        r"\bsatis\b",
        r"\bfiyat\b",
        r"\bfiyatı\b",
        r"\btl\b",
        r"\blira\b",
        r"₺",
        r"\bpazarlık\b",
        r"\bücret\b"
    ]
    metin = (baslik + " " + aciklama).lower()

    for pattern in ticari_kelimeler:
        if re.search(pattern, metin):
            # Ekranda kötü re görünmemesi için temizle
            gosterilecek_sebeb = pattern.replace(r"\b", "").replace("\\", "")
            return {
                "uygun": False,
                "sebep": f'İlan ticari içerik barındırıyor: "{gosterilecek_sebeb}" kelimesi tespit edildi.',
            }

    return {"uygun": True, "sebep": None}


@app.route("/")
def index():
    return send_from_directory(TEMPLETES_PATH, "index.html")


@app.route("/api/sihirli-ilan", methods=["POST"])
def sihirli_ilan():
    data = request.get_json() or {}
    kategori = data.get("kategori", "Bilinmiyor")
    baslik = data.get("baslik", "")
    aciklama = data.get("aciklama", "")

    if not baslik.strip() and not aciklama.strip():
        return jsonify({"hata": "Sihir yapabilmemiz için eşya hakkında birkaç kelime girmelisiniz!"}), 400

    ham_metin = f"Kategori: {kategori}\nGirilenler: {baslik} - {aciklama}"

    prompt = f"""
    Sen, sürdürülebilir yaşam ve döngüsel ekonomi üzerine kurulu prestijli bir bağış platformu olan 'REWORLD' için çalışan uzman bir metin yazarısın. (Copywriter)
    Amacın, kullanıcıların sisteme girdiği basit, eksik veya sıradan eşya bilgilerini alıp; onları son derece profesyonel, okuyanda saygı ve o eşyaya sahip olma arzusu uyandıran,
    aynı zamanda eşyaya ikinci bir şans verilmesini çevre bilinciyle harmanlayan yüksek kaliteli listeleme metinlerine dönüştürmek.
    Ayrıca kullanıcının metinden yola çıkarak eşyanın kategorisini "kitap", "kiyafet", "gida" veya "diger" seçeneklerinden hangisine ait olduğunu doğru tespit et.
    
    Kullanıcının girdiği ham veri:
    {ham_metin}
    
    Lütfen şu standartlarda bir içerik üret:
    1. Çok çarpıcı, profesyonel ve tıklama arzusu yaratan ancak abartıdan uzak bir BAŞLIK (en fazla 7 kelime).
    2. Eşyanın değerini ön plana çıkaran, sürdürülebilirliğe vurgu yapan, kaliteli, ikna edici ve edebi bir dille yazılmış 3-4 cümlelik prestij algısı yüksek bir AÇIKLAMA.
    3. Metnin içeriğine en uygun KATEGORI ("kitap", "kiyafet", "gida" veya "diger").

    Yalnızca geçerli bir JSON formatı döndür (Asla ```json, ``` vb. markdown formatı kullanma). JSON formatı kesinlikle şu şekilde olmak zorundadır:
    {{"baslik": "...", "aciklama": "...", "kategori": "..."}}
    """

    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.7,
                response_mime_type="application/json"
            )
        )
        
        raw_text = response.text.strip()

        # Markdown temizliği (Eğer response_mime_type tam oturmazsa diye tedbir)
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]

        ai_data = json.loads(raw_text.strip())
        return jsonify(ai_data)

    except Exception as e:
        error_msg = str(e)
        print("Sihirli ilan hatası:", error_msg)
        if "400" in error_msg or "API" in error_msg:
            return jsonify({"hata": "Google Gemini API Anahtarınız devredışı kalmış, yetkisiz veya yanlış! Lütfen .env dosyası içindeki GEMINI_API_KEY değerini aistudio.google.com adresinden alacağınız yeni bir anahtar ile değiştirin."}), 500
        return jsonify({"hata": "AI Asistan ağa bağlanamadı! Lütfen kendi metninizi kullanın."}), 500

@app.route("/<path:name>")
def serve_html(name):
    allowed_exts = {".css", ".js", ".json", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
    ext = os.path.splitext(name)[1].lower()
    if name in ALLOWED_HTML or ext in allowed_exts:
        return send_from_directory(TEMPLETES_PATH, name)
    abort(404)


@app.route("/api/chatbot", methods=["POST"])
def chatbot_api():
    if not globals().get("GEMINI_API_KEY"):
        return jsonify({"cevap": "Sistemim şu an uykuda, lütfen API ayarlarımı kontrol edin!"}), 200

    data = request.get_json() or {}
    kullanici_mesaji = data.get("mesaj", "")

    if not kullanici_mesaji:
        return jsonify({"cevap": "Lütfen önce bana bir şeyler yazın. 😊"}), 400

    prompt = f"""
    Sen, 'REWORLD' sürdürülebilirlik ve bağış platformunun akıllı, dostane ve net cevaplar veren yapay zeka asistanısın. 
    Kullanıcının sorusu: "{kullanici_mesaji}"
    
    KURALLAR:
    1. Kullanıcıya her zaman dostane ama çok kısa, öz ve net (maksimum 3-4 cümle) cevaplar ver.
    2. Cümlelerin gramer yapısı mükemmel olmalı. Asla lafı uzatma veya cümleyi yarıda kesme.
    3. Anlam bütünlüğünü koruyarak, düşüncelerini tamamen toparlayarak bitirilmiş kesin bir yanıt üret.
    """

    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.7,
                max_output_tokens=2048,
            )
        )
        text = response.text.strip()
        return jsonify({"cevap": text}), 200
    except Exception as e:
        error_msg = str(e)
        print(f"Chatbot Hatası: {error_msg}")
        if "400" in error_msg or "API_KEY_INVALID" in error_msg or "PermissionDenied" in error_msg:
             return jsonify({"cevap": "Sistemim şu an uykuda. Görünüşe göre API anahtarımın yetkisi yok, yanlış yazılmış veya süresi dolmuş. Lütfen .env dosyası içerisinden anahtarımı yenileyin! 😔"}), 200
        return jsonify({"cevap": "Üzgünüm, şu an bağlantımda sorun var. 😞 Biraz sonra tekrar dener misiniz?"}), 500

def open_browser():
    webbrowser.open("http://127.0.0.1:5000")

if __name__ == "__main__":
    init_db()
    print("REWORLD: http://127.0.0.1:5000 — bagis.html içinde REWORLD_USE_FLASK = true kullan.")
    # sadece reloader değilse tarayıcı aç
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        threading.Timer(1, open_browser).start()
    
    app.run(debug=True, port=5000)