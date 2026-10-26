"""Hocanın baseline adımı: süzülmüş tepeler, dakika SDNN ve eğitimde seçilen tek eşik."""
from pathlib import Path
import os
import json
import numpy as np
from scipy.signal import butter, filtfilt, find_peaks
import wfdb

ROOT = Path(__file__).resolve().parents[1]
(ROOT/'veri').mkdir(exist_ok=True)
(ROOT/'ciktilar').mkdir(exist_ok=True)
DATA = Path(os.environ.get('APNEA_DATA_DIR', 'data'))
EGITIM = ['a01', 'a03', 'b02', 'c01']
TEST = ['a02', 'a04', 'b01', 'c02']
KAYITLAR = EGITIM + TEST

X, L = {}, {}
for k in KAYITLAR:
    X[k] = wfdb.rdrecord(str(DATA / k)).p_signal[:, 0]
    L[k] = np.asarray(wfdb.rdann(str(DATA / k), 'apn').symbol)

b, a = butter(2, [5, 20], btype='bandpass', fs=100)

def tepe_bul(s):
    y = s - np.median(s)
    if abs(np.percentile(y, 0.5)) > np.percentile(y, 99.5):
        y = -y
    return find_peaks(y, distance=30, height=0.5*np.percentile(y, 99))[0]

def dakika_sdnn(pk, n):
    rr = np.diff(pk) / 100
    dk = pk[1:] // 6000
    sonuc = np.full(n, np.nan)
    for i in range(n):
        r = rr[dk == i]
        ok = (r >= 0.3) & (r <= 2.0)
        if ok.sum() >= 30:
            sonuc[i] = np.std(r[ok]) * 1000
    return sonuc

def say(y, tahmin):
    pozitif = y == 'A'
    tp = int(np.sum(tahmin & pozitif))
    fn = int(np.sum(~tahmin & pozitif))
    tn = int(np.sum(~tahmin & ~pozitif))
    fp = int(np.sum(tahmin & ~pozitif))
    return tp, fn, tn, fp

def ba(tp, fn, tn, fp):
    return (tp/(tp+fn) + tn/(tn+fp)) / 2

P, SDNN = {}, {}
for k in KAYITLAR:
    suz = filtfilt(b, a, X[k])
    P[k] = tepe_bul(suz)
    SDNN[k] = dakika_sdnn(P[k], len(L[k]))

v = np.concatenate([SDNN[k] for k in EGITIM])  # NaN değerler korunur.
adaylar = np.nanpercentile(v, np.arange(1, 100))
y_egitim = np.concatenate([L[k] for k in EGITIM])
x_egitim = np.concatenate([SDNN[k] for k in EGITIM])

en_iyi_T = None
en_iyi_BA = -np.inf
for T in adaylar:  # Küçükten büyüğe; eşit BA'da ilk, yani küçük T kalır.
    tahmin = x_egitim > T  # NaN > T False: geçersiz dakika 'apne yok'.
    skor = ba(*say(y_egitim, tahmin))
    if skor > en_iyi_BA:
        en_iyi_BA = skor
        en_iyi_T = float(T)

T = en_iyi_T
y_test = np.concatenate([L[k] for k in TEST])
x_test = np.concatenate([SDNN[k] for k in TEST])
tahmin_test = x_test > T
tp, fn, tn, fp = say(y_test, tahmin_test)
test_ba = ba(tp, fn, tn, fp)
f1 = 2*tp/(2*tp+fp+fn)
duyarlilik = tp/(tp+fn)
yanlis_alarm = fp/(fp+tn)
gecersiz = int(np.isnan(x_test).sum())

hepsi_apne = np.ones(len(y_test), dtype=bool)
all_tp, all_fn, all_tn, all_fp = say(y_test, hepsi_apne)
saglama_ba = ba(all_tp, all_fn, all_tn, all_fp)

print(f'T = {T:.6f} ms')
print(f'Test BA = {test_ba:.6f}')
print(f'F1 = {f1:.6f}')
print(f'Duyarlılık = {duyarlilik:.6f}')
print(f'Yanlış alarm = {yanlis_alarm:.6f}')
print(f'Test geçersiz dakika = {gecersiz}')
print(f'Sağlama, bütün dakikalara apne BA = {saglama_ba:.6f}')
print(f'Karışıklık sayıları: TP={tp}, FN={fn}, TN={tn}, FP={fp}')

sonuc = {
    'egitim_kayitlari': EGITIM, 'test_kayitlari': TEST,
    'T_ms': T, 'egitim_BA': float(en_iyi_BA), 'test_BA': float(test_ba),
    'F1': float(f1), 'duyarlilik': float(duyarlilik),
    'yanlis_alarm': float(yanlis_alarm), 'test_gecersiz_dakika': gecersiz,
    'saglama_hepsi_apne_BA': float(saglama_ba),
    'TP': tp, 'FN': fn, 'TN': tn, 'FP': fp
}
(ROOT/'veri/02_sdnn_baseline_sonuc.json').write_text(json.dumps(sonuc, ensure_ascii=False, indent=2), encoding='utf-8')
np.savez_compressed(ROOT/'veri/02_sdnn_dakikalari.npz', **{k: SDNN[k] for k in KAYITLAR})
