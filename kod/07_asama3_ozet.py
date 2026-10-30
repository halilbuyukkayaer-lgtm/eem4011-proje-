"""Şekil 2: aynı dakikalarda BA ve kişi bazlı güven aralıkları."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'sonuclar'
OUT.mkdir(exist_ok=True)
rules = json.loads((ROOT / 'veri/08_ayni_dakika_kural_sonuclari.json').read_text(encoding='utf-8'))
models = json.loads((ROOT / 'veri/06_lojistik_sonuclari.json').read_text(encoding='utf-8'))
if len({r['minutes'] for r in rules} | {r['valid_minutes'] for r in models}) != 1:
    raise AssertionError('Yöntemler aynı sayıda dakikada ölçülmemiş')

items = []
for r in rules:
    p = 'süzülmüş' if r['pipeline'] == 'suz' else 'ham'
    name = f"Kural: {p} {r['feature_name']}"
    kind = 'baseline' if p == 'süzülmüş' and r['feature'] == 'sdnn_ms' else (
        'en iyi kural' if p == 'süzülmüş' and r['feature'] == 'ln_sdnn_rmssd' else '')
    items.append((name, r, kind))
for r in models:
    kind = 'en iyi model' if r['model'] == 'Temel 3 + SDNN' else ''
    items.append((f"Lojistik regresyon: {r['model']}", r, kind))

colors = {'baseline': '#d27d24', 'en iyi kural': '#1a8b76',
          'en iyi model': '#ad3c72', '': '#54758e'}
fig, ax = plt.subplots(figsize=(13, 7.3))
y = np.arange(len(items))
for i, (name, r, kind) in enumerate(items):
    value = r['BA']; lo, hi = r['BA_CI95']
    ax.errorbar(value, i, xerr=[[value - lo], [hi - value]], fmt='o',
                color=colors[kind], ecolor=colors[kind], capsize=5,
                markersize=9 if kind else 7, linewidth=2 if kind else 1.4)
    ax.text(min(hi + .008, .815), i, f'{value:.3f}', va='center', fontsize=10)
ax.axvline(.5, ls='--', color='#777', lw=1.2, label='Şans çizgisi (0,50)')
ax.set_yticks(y, [name + (f'  ← {kind}' if kind else '') for name, _, kind in items])
ax.invert_yaxis()
ax.set_xlim(.35, .85)
ax.set_xlabel('Dengeli doğruluk (BA) ve kişi bazlı %95 güven aralığı')
ax.set_title(f'Aynı {rules[0]["minutes"]:,} dakikada kişi bazlı beş katlı karşılaştırma'.replace(',', '.'))
ax.grid(axis='x', alpha=.2)
ax.legend(loc='upper right')
fig.tight_layout()
path = OUT / '07_asama3_model_karsilastirmasi.png'
fig.savefig(path, dpi=190, bbox_inches='tight')
plt.close(fig)
print(path)
