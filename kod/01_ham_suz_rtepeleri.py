"""Hocanın 1. adımı: ham ve 5–20 Hz süzülmüş R tepe tespiti karşılaştırması."""
from pathlib import Path
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt, find_peaks
import wfdb

ROOT = Path(__file__).resolve().parents[1]
(ROOT/'veri').mkdir(exist_ok=True)
(ROOT/'ciktilar').mkdir(exist_ok=True)
DATA = Path(os.environ.get('APNEA_DATA_DIR', 'data'))
KAYITLAR = ['a01', 'a02', 'a03', 'c01', 'c02']

X, L = {}, {}
for k in KAYITLAR:
    X[k] = wfdb.rdrecord(str(DATA / k)).p_signal[:, 0]
    L[k] = np.asarray(wfdb.rdann(str(DATA / k), 'apn').symbol)

b, a = butter(2, [5, 20], btype='bandpass', fs=100)

def tepe_bul(s):
    y = s - np.median(s)
    if abs(np.percentile(y, 0.5)) > np.percentile(y, 99.5):
        y = -y
    pk = find_peaks(y, distance=30, height=0.5 * np.percentile(y, 99))[0]
    return pk

S, P = {}, {}
for k in X:
    S[k] = filtfilt(b, a, X[k])
    P[(k, 'ham')] = tepe_bul(X[k])
    P[(k, 'suz')] = tepe_bul(S[k])
    print(f"{k}: ham={len(P[(k, 'ham')])}, süzülmüş={len(P[(k, 'suz')])}")

n = len(L['a02'])
ham_dk = np.bincount(P[('a02', 'ham')] // 6000, minlength=n)[:n]
suz_dk = np.bincount(P[('a02', 'suz')] // 6000, minlength=n)[:n]
dakika = int(np.argmax(np.abs(ham_dk - suz_dk)))
print(f"a02 en büyük fark: dakika {dakika}; ham={ham_dk[dakika]}, süzülmüş={suz_dk[dakika]}")

bas = dakika * 6000
son = bas + 1000
zaman = np.arange(1000) / 100
ham10 = P[('a02', 'ham')]
ham10 = ham10[(ham10 >= bas) & (ham10 < son)]
suz10 = P[('a02', 'suz')]
suz10 = suz10[(suz10 >= bas) & (suz10 < son)]

fig, ax = plt.subplots(2, 1, figsize=(15, 8), sharex=True)
ax[0].plot(zaman, X['a02'][bas:son], color='#555555', lw=1)
ax[0].scatter((ham10-bas)/100, X['a02'][ham10], color='red', marker='x', s=55, zorder=3)
ax[0].set_title(f'a02 • dakika {dakika}, ilk 10 saniye • ham sinyal | {len(ham10)} tepe')
ax[0].set_ylabel('EKG (mV)'); ax[0].grid(alpha=.25)
ax[1].plot(zaman, S['a02'][bas:son], color='#236a9f', lw=1)
ax[1].scatter((suz10-bas)/100, S['a02'][suz10], color='red', marker='x', s=55, zorder=3)
ax[1].set_title(f'5–20 Hz süzülmüş sinyal | {len(suz10)} tepe')
ax[1].set_xlabel('Dakikanın seçilen bölümündeki süre (s)'); ax[1].set_ylabel('Süzülmüş EKG (mV)'); ax[1].grid(alpha=.25)
fig.tight_layout()
fig.savefig(ROOT / 'ciktilar/sekil1_a02_ham_suzulmus.png', dpi=200, bbox_inches='tight')

np.savez_compressed(ROOT / 'veri/01_tepe_sonuclari.npz',
                    **{f'{k}_{yol}': P[(k, yol)] for k in X for yol in ('ham', 'suz')})
(ROOT / 'notlar/01_sayilar.txt').write_text(
    '\n'.join([f"{k}: ham={len(P[(k, 'ham')])}, süzülmüş={len(P[(k, 'suz')])}" for k in X]) +
    f"\na02 en büyük fark: dakika {dakika}; ham={ham_dk[dakika]}, süzülmüş={suz_dk[dakika]}" +
    f"\nİlk 10 s: ham={len(ham10)}, süzülmüş={len(suz10)}\n", encoding='utf-8')
print(f"Bu 10 saniyede ham={len(ham10)}, süzülmüş={len(suz10)}")
print(ROOT / 'ciktilar/sekil1_a02_ham_suzulmus.png')
