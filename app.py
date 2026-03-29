"""
REWORLD — Flask (isteğe bağlı)
Statik HTML + assets sunumu ve /api/* uçları
"""

import os
import sqlite3
import json
import urllib.request
import urllib.error
import re
import uuid

from flask import Flask, abort, jsonify, request, send_from_directory
from flask_cors import CORS

ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(ROOT, "yenidehayat.db")

GEMINI_API_KEY = "AIzaSyCOoFg0ubL63EjfShsySBwoY-Kg5X3dvGQ"

ALLOWED_HTML = {
    "index.html",
    "ilanlar.html",
    "kitaplar.html",
    "kiyafetler.html",
    "gida.html",
    "bagis.html",
}

app = Flask(__name__, static_folder=None)
CORS(app)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS ilanlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kategori TEXT NOT NULL,
            baslik TEXT NOT NULL,
            aciklama TEXT,
            sehir TEXT NOT NULL,
            iletisim TEXT NOT NULL,
            tarih TEXT DEFAULT CURRENT_TIMESTAMP,
            onaylandi INTEGER DEFAULT 0,
            gorsel_yolu TEXT,
            silme_kodu TEXT
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
    conn.commit()
    conn.close()


@app.route("/assets/<path:path>")
def serve_assets(path):
    return send_from_directory(os.path.join(ROOT, "assets"), path)


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
    if request.is_json:
        data = request.get_json() or {}
    else:
        data = request.form.to_dict()

    required = ["kategori", "baslik", "sehir", "iletisim"]
    for field in required:
        if not data.get(field):
            return jsonify({"hata": f"{field} alanı zorunludur"}), 400

    moderasyon = ai_moderasyon(data.get("baslik", ""), data.get("aciklama", ""))

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
        INSERT INTO ilanlar (kategori, baslik, aciklama, sehir, iletisim, onaylandi, gorsel_yolu, silme_kodu)
        VALUES (?, ?, ?, ?, ?, 1, ?, ?)
        """,
        (
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
    data = request.get_json() or {}
    kodu = data.get("silme_kodu")
    if not kodu:
        return jsonify({"hata": "Yetkisiz işlem. Şifre bulunamadı."}), 403

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT silme_kodu, gorsel_yolu FROM ilanlar WHERE id=?", (ilan_id,))
    row = c.fetchone()
    
    if not row:
        conn.close()
        return jsonify({"hata": "İlan bulunamadı."}), 404

    db_kodu = row[0]
    gorsel = row[1]
    
    if db_kodu and db_kodu != kodu:
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
    return send_from_directory(ROOT, "index.html")

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
    
    req_body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7}
    }).encode("utf-8")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    req = urllib.request.Request(url, data=req_body, headers={'Content-Type': 'application/json'})
    
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            raw_text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
            
            if raw_text.startswith("```json"): raw_text = raw_text[7:]
            if raw_text.startswith("```"): raw_text = raw_text[3:]
            if raw_text.endswith("```"): raw_text = raw_text[:-3]

            ai_data = json.loads(raw_text.strip())
            return jsonify(ai_data)
            
    except Exception as e:
        print("Sihirli ilan hatası:", e)
        return jsonify({"hata": "AI Asistan ağa bağlanamadı! Lütfen kendi metninizi kullanın."}), 500


@app.route("/<path:name>")
def serve_html(name):
    if name not in ALLOWED_HTML:
        abort(404)
    return send_from_directory(ROOT, name)

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
    
    req_body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2048,
        }
    }).encode("utf-8")

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    req = urllib.request.Request(api_url, data=req_body, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode())
            text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
            return jsonify({"cevap": text}), 200
    except Exception as e:
        print(f"Chatbot Hatası: {str(e)}")
        return jsonify({"cevap": "Üzgünüm, şu an bağlantımda sorun var. 😞 Biraz sonra tekrar dener misiniz?"}), 500


if __name__ == "__main__":
    init_db()
    print("REWORLD: http://127.0.0.1:5000 — bagis.html içinde REWORLD_USE_FLASK = true kullan.")
    app.run(debug=True, port=5000)
