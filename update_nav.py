import glob
import re

for file in glob.glob("*.html"):
    if file == "ilanlar.html": continue
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Nav header replace
    content = re.sub(
        r'(<li><a href="index\.html".*?>Ana Sayfa</a></li>)',
        r'\1\n      <li><a href="ilanlar.html">İlanlar</a></li>',
        content
    )

    with open(file, 'w', encoding='utf-8') as f:
        f.write(content)
print("Updated all HTML files!")
