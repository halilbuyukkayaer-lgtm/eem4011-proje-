"""Şekil 3: bir sınama kaydında dakika etiketi, ln oran ve eğitim eşiği."""
from pathlib import Path
import csv
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'sonuclar'
OUT.mkdir(exist_ok=True)
record = 'a02'
rows = [r for r in csv.DictReader(
    (ROOT / 'veri/04_asama3_dakika_ozellikleri.csv').open(encoding='utf-8'))
        if r['pipeline'] == 'suz' and r['record'] == record]
if not rows:
    raise RuntimeError(f'{record} dakikaları bulunamadı')
folds = {int(r['person_group']): int(r['fold']) for r in csv.DictReader(
    (ROOT / 'veri/06_kisi_katlari.csv').open(encoding='utf-8'))}
person = int(rows[0]['person_group'])
fold = folds[person]
rules = json.loads((ROOT / 'veri/05_dort_kural_sonuclari.json').read_text(encoding='utf-8'))
rule = next(r for r in rules if r['pipeline'] == 'suz' and r['feature'] == 'ln_sdnn_rmssd')
threshold = rule['thresholds'][fold - 1]

# Görselleştirme bölümü etiket geçişini göstermek için seçilir; eşik değişmez.
labels = [r['label'] for r in rows]
transitions = [i for i in range(1, len(labels)) if labels[i] != labels[i - 1]]
if not transitions:
    raise RuntimeError('Etiket geçişi bulunamadı')
center = transitions[0]
start, end = max(0, center - 12), min(len(rows), center + 18)
shown = rows[start:end]
minutes = np.array([int(r['minute']) for r in shown])
values = np.array([float(r['ln_sdnn_rmssd']) for r in shown])
apnea = np.array([r['label'] == 'A' for r in shown])

fig, ax = plt.subplots(figsize=(13, 5.5))
for minute, is_apnea in zip(minutes, apnea):
    ax.axvspan(minute - .5, minute + .5,
               color='#f7d9d4' if is_apnea else '#dceaf5', alpha=.65, lw=0)
ax.plot(minutes, values, color='#303841', lw=1.5, alpha=.8)
ax.scatter(minutes[~apnea], values[~apnea], color='#3276a8', s=45, zorder=3)
ax.scatter(minutes[apnea], values[apnea], color='#bc5146', s=45, zorder=3)
ax.axhline(threshold, color='#a03077', ls='--', lw=2,
           label=f'Eğitim kişilerinden seçilen eşik: {threshold:.3f}')
ax.set_xlim(minutes[0] - .7, minutes[-1] + .7)
ax.set_xlabel('Kayıttaki dakika numarası')
ax.set_ylabel('ln(SDNN/RMSSD)')
ax.set_title(f'{record}: sınama kişisi {person}, kat {fold} • dakika etiketi ve sabit eşik')
ax.grid(axis='y', alpha=.25)
handles = [Patch(facecolor='#dceaf5', label='N: normal dakika'),
           Patch(facecolor='#f7d9d4', label='A: apne dakikası'),
           plt.Line2D([0], [0], color='#a03077', ls='--', lw=2,
                      label=f'Eğitim eşiği: {threshold:.3f}')]
ax.legend(handles=handles, loc='best')
fig.tight_layout()
path = OUT / '09_a02_test_kisisi_esik.png'
fig.savefig(path, dpi=190, bbox_inches='tight')
plt.close(fig)
print(f'{record}: kişi grubu={person}, sınama katı={fold}, eşik={threshold:.6f}')
print(path)
