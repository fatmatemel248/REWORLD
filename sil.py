import sqlite3
c = sqlite3.connect('yenidehayat.db')
c.execute("DELETE FROM ilanlar WHERE baslik LIKE '%Dostoyevski%' OR aciklama LIKE '%Dostoyevski%'")
c.execute("DELETE FROM ilanlar WHERE baslik LIKE '%dostoyevski%' OR aciklama LIKE '%dostoyevski%'")
c.commit()
print('silindi')
