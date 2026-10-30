"""Duyarlılık analizi: RMSSD yalnız gerçekten ardışık geçerli RR çiftlerinden.

Önceki 04/05/06/08 sonuçları korunur. Yeni eşikler yine yalnız eğitim kişileriyle seçilir.
"""
from pathlib import Path
import csv
import json
import os
import numpy as np
import wfdb
from scipy.signal import butter, filtfilt, find_peaks
from sklearn.metrics import balanced_accuracy_score, f1_score

ROOT = Path(__file__).resolve().parents[1]
VERI = ROOT / 'veri'
DATA = Path(os.environ.get('APNEA_DATA_DIR', 'data'))
rows = [r for r in csv.DictReader((VERI / '04_asama3_dakika_ozellikleri.csv').open(encoding='utf-8'))
        if r['pipeline'] == 'suz']
records = list(dict.fromkeys(r['record'] for r in rows))
folds = {int(r['person_group']): int(r['fold']) for r in csv.DictReader(
    (VERI / '06_kisi_katlari.csv').open(encoding='utf-8'))}
original_rules = json.loads((VERI / '05_dort_kural_sonuclari.json').read_text(encoding='utf-8'))
old = next(r for r in original_rules
           if r['pipeline'] == 'suz' and r['feature'] == 'ln_sdnn_rmssd')
b, a = butter(2, [5, 20], btype='bandpass', fs=100)

def tepe_bul(s):
    y = s - np.median(s)
    if abs(np.percentile(y, .5)) > np.percentile(y, 99.5):
        y = -y
    return find_peaks(y, distance=30, height=.5 * np.percentile(y, 99))[0]

new_rmssd = {}
for j, record in enumerate(records, 1):
    x = wfdb.rdrecord(str(DATA / record)).p_signal[:, 0]
    pk = tepe_bul(filtfilt(b, a, x))
    rr = np.diff(pk) / 100
    minute = pk[1:] // 6000
    record_rows = [r for r in rows if r['record'] == record]
    for row in record_rows:
        i = int(row['minute'])
        r = rr[minute == i]
        ok = (r >= .3) & (r <= 2.0)
        # diff(r)[j] yalnız r[j] ve r[j+1] birlikte geçerliyse kullanılır.
        adjacent = ok[:-1] & ok[1:]
        value = (float(np.sqrt(np.mean(np.diff(r)[adjacent] ** 2)) * 1000)
                 if int(adjacent.sum()) >= 29 else np.nan)
        new_rmssd[(record, i)] = value
    print(f'[{j:02d}/{len(records)}] {record}', flush=True)

y = np.array([r['label'] == 'A' for r in rows], dtype=bool)
g = np.array([int(r['person_group']) for r in rows])
fold_id = np.array([folds[person] for person in g])
sdnn = np.array([float(r['sdnn_ms']) for r in rows])
rmssd = np.array([new_rmssd[(r['record'], int(r['minute']))] for r in rows])
x = np.full(len(rows), np.nan)
ok = np.isfinite(sdnn) & np.isfinite(rmssd) & (sdnn > 0) & (rmssd > 0)
x[ok] = np.log(sdnn[ok] / rmssd[ok])
old_x = np.array([float(r['ln_sdnn_rmssd']) for r in rows])
old_pred = old_x > np.asarray(old['thresholds'])[fold_id - 1]
new_pred = np.zeros(len(rows), dtype=bool)
thresholds = []
for fold in range(1, 6):
    train = fold_id != fold
    test = ~train
    if set(g[train]) & set(g[test]):
        raise AssertionError('Kişi sızıntısı')
    candidates = np.nanpercentile(x[train], np.arange(1, 100))
    scores = [balanced_accuracy_score(y[train], x[train] > threshold)
              for threshold in candidates]
    threshold = float(candidates[int(np.argmax(scores))])
    thresholds.append(threshold)
    new_pred[test] = x[test] > threshold

required = ('mean_rr_ms', 'rmssd_ms', 'r_amplitude_std', 'sdnn_ms', 'ln_sdnn_rmssd')
common = np.array([all(np.isfinite(float(r[k])) for k in required) for r in rows])
if int(common.sum()) != 16375:
    raise AssertionError('Ortak dakika sayısı değişti; yeni sonuç ayrı incelenmeli')

def result(pred, mask):
    return {'minutes': int(mask.sum()),
            'BA': float(balanced_accuracy_score(y[mask], pred[mask])),
            'F1': float(f1_score(y[mask], pred[mask], zero_division=0))}

out = {
    'old_ratio_all': result(old_pred, np.ones(len(rows), dtype=bool)),
    'new_ratio_all': result(new_pred, np.ones(len(rows), dtype=bool)),
    'old_ratio_common': result(old_pred, common),
    'new_ratio_common': result(new_pred, common),
    'new_invalid_all': int(np.sum(~np.isfinite(x))),
    'new_invalid_common': int(np.sum(common & ~np.isfinite(x))),
    'new_thresholds': thresholds,
    'definition': 'Yalnız ardışık iki RR aralığı da 0,3–2,0 s içinde; dakikada en az 29 çift',
}
(VERI / '10_rmssd_ardisik_sonuc.json').write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
with (VERI / '10_rmssd_ardisik_dakikalar.csv').open('w', newline='', encoding='utf-8') as file:
    writer = csv.writer(file)
    writer.writerow(['record', 'minute', 'person_group', 'label',
                     'rmssd_ardisik_ms', 'ln_sdnn_rmssd_ardisik'])
    for row, rv, ratio in zip(rows, rmssd, x):
        writer.writerow([row['record'], row['minute'], row['person_group'],
                         row['label'], rv, ratio])
for name in ('old_ratio_all', 'new_ratio_all', 'old_ratio_common', 'new_ratio_common'):
    r = out[name]
    print(f"{name}: dakika={r['minutes']}; BA={r['BA']:.4f}; F1={r['F1']:.4f}")
print(f"Yeni geçersiz dakika: tümünde={out['new_invalid_all']}; "
      f"ortak kümede={out['new_invalid_common']}")
