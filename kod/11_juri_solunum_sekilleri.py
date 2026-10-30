"""Aşama 3 solunum özellikleri için iki jüri şekli üretir.

Bu dosya ham hasta verisi okumaz. Daha önce üretilmiş JSON sonuçlarını kullanır.
"""
from pathlib import Path
import json

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "sonuclar"
OUT.mkdir(exist_ok=True)


def load(name):
    with (ROOT / "denemeler" / name).open(encoding="utf-8") as f:
        return json.load(f)


# Şekil 4: Aynı kişi bazlı beş kat üzerinde özellik gruplarının katkısı
classification = load("25_edr_genlik_alan_tum_veri_sonuc.json")
cv = classification["group_cv_on_learn"]
keys = ["ritim_4", "alan_EDR_7", "ritim_4+alan_EDR_7"]
labels = ["4 ritim\nözelliği", "7 QRS alanı\nsolunum özelliği", "Ritim + solunum\n(11 özellik)"]
ba = [cv[k]["BA"] for k in keys]
f1 = [cv[k]["F1"] for k in keys]

fig, ax = plt.subplots(figsize=(9, 5.2))
x = np.arange(len(keys)); width = 0.34
b1 = ax.bar(x - width / 2, ba, width, label="Dengeli doğruluk", color="#1769aa")
b2 = ax.bar(x + width / 2, f1, width, label="F1", color="#ef6c00")
ax.axhline(0.50, color="black", linestyle="--", linewidth=1.2, label="Şans çizgisi")
ax.set_xticks(x, labels)
ax.set_ylim(0.45, 0.85)
ax.set_ylabel("Başarı")
ax.set_title("Kişi bazlı beş katlı sınamada solunum özelliklerinin katkısı")
ax.grid(axis="y", alpha=0.25)
ax.legend(loc="upper left")
ax.bar_label(b1, fmt="%.3f", padding=3)
ax.bar_label(b2, fmt="%.3f", padding=3)
fig.tight_layout()
fig.savefig(OUT / "11_solunum_ozellikleri_model_karsilastirmasi.png", dpi=220)
plt.close(fig)


# Şekil 5: EKG'den çıkarılan solunumun gerçek solunumla doğrulanması
validation = load("27_edr_birlestirme_dogrulama_sonuc.json")["summary"]
keys = ["qrs_area", "slope_range", "fusion_quality_weighted"]
labels = ["QRS alanı", "QRS eğimi", "Kalite ağırlıklı\nbirleşim"]
corr = [validation[k]["median_effort_corr"] for k in keys]
rate = [validation[k]["median_rate_error_bpm"] for k in keys]

fig, axes = plt.subplots(1, 2, figsize=(10, 4.8))
bars = axes[0].bar(labels, corr, color=["#1769aa", "#78909c", "#2e7d32"])
axes[0].set_ylim(0, 0.65)
axes[0].set_ylabel("Ortanca mutlak korelasyon")
axes[0].set_title("Gerçek solunum dalgasına benzerlik")
axes[0].grid(axis="y", alpha=0.25)
axes[0].bar_label(bars, fmt="%.3f", padding=3)

bars = axes[1].bar(labels, rate, color=["#1769aa", "#78909c", "#2e7d32"])
axes[1].set_ylim(0, 1.0)
axes[1].set_ylabel("Ortanca hata (nefes/dakika)")
axes[1].set_title("Solunum hızı hatası (düşük daha iyi)")
axes[1].grid(axis="y", alpha=0.25)
axes[1].bar_label(bars, fmt="%.1f", padding=3)
fig.suptitle("EKG türevli solunumun 8 kayıtta, 3.900 pencerede doğrulanması")
fig.tight_layout()
fig.savefig(OUT / "12_edr_gercek_solunum_dogrulama.png", dpi=220)
plt.close(fig)

print(OUT / "11_solunum_ozellikleri_model_karsilastirmasi.png")
print(OUT / "12_edr_gercek_solunum_dogrulama.png")
