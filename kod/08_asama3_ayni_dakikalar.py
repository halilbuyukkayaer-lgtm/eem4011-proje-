"""Aşama 3 sağlaması: dört eski eşiği lojistik regresyonun dakikalarında ölç.

Eşikler 05'te eğitim kişileriyle seçilmiştir; burada hiçbir eşik yeniden seçilmez.
"""
from pathlib import Path
import csv
import json
import numpy as np
from sklearn.metrics import balanced_accuracy_score, f1_score

ROOT = Path(__file__).resolve().parents[1]
VERI = ROOT / 'veri'
rows = list(csv.DictReader((VERI / '04_asama3_dakika_ozellikleri.csv').open(encoding='utf-8')))
folds = {int(r['person_group']): int(r['fold']) for r in csv.DictReader(
    (VERI / '06_kisi_katlari.csv').open(encoding='utf-8'))}
rules = json.loads((VERI / '05_dort_kural_sonuclari.json').read_text(encoding='utf-8'))
models = json.loads((VERI / '06_lojistik_sonuclari.json').read_text(encoding='utf-8'))

key = lambda r: (r['record'], int(r['minute']))
suz = {key(r): r for r in rows if r['pipeline'] == 'suz'}
required = ('mean_rr_ms', 'rmssd_ms', 'r_amplitude_std', 'sdnn_ms', 'ln_sdnn_rmssd')
common = {k for k, r in suz.items() if all(np.isfinite(float(r[name])) for name in required)}
if len(common) != models[0]['valid_minutes']:
    raise AssertionError('06 ile ortak dakika sayısı uyuşmuyor')
if len(folds) != 24 or len(suz) - len(common) != models[0]['excluded_minutes']:
    raise AssertionError('Kişi veya dışlama sayısı uyuşmuyor')

def person_bootstrap(y, p, g, count=1000, seed=0):
    rng = np.random.default_rng(seed)
    people = np.unique(g)
    indices = {person: np.flatnonzero(g == person) for person in people}
    ba, f1 = [], []
    for _ in range(count):
        chosen = rng.choice(people, len(people), replace=True)
        sample = np.concatenate([indices[person] for person in chosen])
        if len(np.unique(y[sample])) < 2:
            continue  # Dengeli doğruluk iki sınıf olmadan tanımlı değildir.
        ba.append(balanced_accuracy_score(y[sample], p[sample]))
        f1.append(f1_score(y[sample], p[sample], zero_division=0))
    if not ba:
        raise RuntimeError('Bootstrap örneklerinde iki sınıf bulunamadı')
    return ([float(v) for v in np.percentile(ba, [2.5, 97.5])],
            [float(v) for v in np.percentile(f1, [2.5, 97.5])])

results = []
for rule in rules:
    data = [r for r in rows if r['pipeline'] == rule['pipeline'] and key(r) in common]
    if len(data) != len(common) or {key(r) for r in data} != common:
        raise AssertionError('Kuralın dakika kimlikleri modelle uyuşmuyor')
    y = np.array([r['label'] == 'A' for r in data], dtype=bool)
    g = np.array([int(r['person_group']) for r in data])
    x = np.array([float(r[rule['feature']]) for r in data])
    f = np.array([folds[person] for person in g])
    if sorted(set(f)) != [1, 2, 3, 4, 5]:
        raise AssertionError('Katlar eksik')
    thresholds = np.asarray(rule['thresholds'])
    p = x > thresholds[f - 1]  # NaN mevcut kuralda olduğu gibi "apne yok" sayılır.
    ba_ci, f1_ci = person_bootstrap(y, p, g)
    result = {
        'pipeline': rule['pipeline'], 'feature': rule['feature'],
        'feature_name': rule['feature_name'], 'minutes': len(data),
        'unavailable_feature_minutes': int(np.sum(~np.isfinite(x))),
        'BA': float(balanced_accuracy_score(y, p)),
        'F1': float(f1_score(y, p, zero_division=0)),
        'BA_CI95': ba_ci, 'F1_CI95': f1_ci,
        'TP': int(np.sum(y & p)), 'FN': int(np.sum(y & ~p)),
        'TN': int(np.sum(~y & ~p)), 'FP': int(np.sum(~y & p)),
    }
    results.append(result)

out = VERI / '08_ayni_dakika_kural_sonuclari.json'
out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'Ortak dakika: {len(common)}; dışarıda: {len(suz) - len(common)}')
for r in results:
    name = 'süzülmüş' if r['pipeline'] == 'suz' else 'ham'
    print(f"{name} | {r['feature_name']}: BA={r['BA']:.4f} "
          f"%95 GA={r['BA_CI95']}; F1={r['F1']:.4f}; "
          f"bu dakikalarda özellik yok={r['unavailable_feature_minutes']}")
print(f"Temel 3 + SDNN lojistik regresyon: BA={models[1]['BA']:.4f}; "
      f"F1={models[1]['F1']:.4f}; ortak dakika={models[1]['valid_minutes']}")
print(out)
