"""Aşama 3 / Adım 1: 35 öğrenme kaydı, c05 çıkarımı ve kişi grupları."""
from pathlib import Path
import os
import csv
import re

ROOT = Path(__file__).resolve().parents[1]
(ROOT/'veri').mkdir(exist_ok=True)
(ROOT/'ciktilar').mkdir(exist_ok=True)
SOURCE = Path(os.environ.get('APNEA_DATA_DIR', 'data'))
records35 = [f'a{i:02d}' for i in range(1, 21)] + [f'b{i:02d}' for i in range(1, 6)] + [f'c{i:02d}' for i in range(1, 11)]
needed = [(r, ext) for r in records35 for ext in ('.hea', '.dat', '.apn')]
missing = [f'{r}{ext}' for r, ext in needed if not (SOURCE/f'{r}{ext}').exists()]
if missing:
    raise FileNotFoundError(f'Eksik dosyalar: {missing}')

text = (SOURCE/'additional-information.txt').read_text(encoding='utf-8')
demo = {}
for line in text.splitlines():
    parts = line.split()
    if len(parts) >= 12 and re.fullmatch(r'[abc]\d{2}', parts[0]):
        record = parts[0]
        demo[record] = (int(parts[8]), parts[9], int(parts[10]), int(parts[11]))
if set(records35) - set(demo):
    raise RuntimeError(f'Demografisi bulunamayan kayıtlar: {sorted(set(records35)-set(demo))}')

records34 = [r for r in records35 if r != 'c05']
key_to_person = {}
rows = []
for r in records34:
    key = demo[r]
    if key not in key_to_person:
        key_to_person[key] = len(key_to_person)
    rows.append({'record': r, 'age': key[0], 'sex': key[1], 'height_cm': key[2],
                 'weight_kg': key[3], 'person_group': key_to_person[key]})

out = ROOT/'veri/03_kayit_kisi_gruplari.csv'
with out.open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

print(f'Öğrenme kaydı: {len(records35)}')
print(f'c05 çıkarılınca kayıt: {len(records34)}')
print(f'Benzersiz kişi grubu: {len(key_to_person)}')
print(f'Eksik dosya: {len(missing)}')
print(out)
if len(records34) != 34 or len(key_to_person) != 24:
    raise AssertionError('Beklenen 34 kayıt / 24 kişi sağlaması geçmedi')
