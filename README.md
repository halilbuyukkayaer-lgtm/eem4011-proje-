# eem4011-proje-
Bu projede PhysioNet Apnea-ECG kayıtlarında ham ve 5–20 Hz süzülmüş R tepeleri karşılaştırılmış; dakika bazında SDNN ve `ln(SDNN/RMSSD)` eşik kuralları ile lojistik regresyon modelleri kişi bazlı çapraz doğrulamayla değerlendirilmiştir.

## Veri seti

**Apnea-ECG Database v1.0.0:** https://physionet.org/content/apnea-ecg/1.0.0/

Veri dosyaları bu depoya yüklenmemiştir. Çalıştırmadan önce 35 öğrenme kaydının `.hea`, `.dat` ve `.apn` dosyaları ile `additional-information.txt` dosyasını PhysioNet'ten indirip yerel `data/` klasörüne koyun. `x01–x35` kayıtları kullanılmaz; `c05` analizden çıkarılır.

## Kurulum

```bash
python -m pip install -r requirements.txt
```

Veriler başka bir klasördeyse yolu ortam değişkeniyle belirtin:

```bash
export APNEA_DATA_DIR=/verinin/tam/yolu
```

## Çalıştırma sırası

```bash
python kod/01_ham_suz_rtepeleri.py
python kod/02_sdnn_baseline.py
python kod/03_asama3_veri_ve_kisi_gruplari.py
python kod/04_asama3_dakika_ozellikleri.py
python kod/05_groupkfold_dort_kural.py
python kod/06_groupkfold_lojistik.py
python kod/07_asama3_ozet.py
```

Ara sonuçlar `veri/`, grafikler `ciktilar/` klasöründe oluşturulur. `.gitignore` bu veri ve ara sonuçların GitHub'a yanlışlıkla eklenmesini engeller.

## Ana sonuç

24 kişi grubuyla yapılan beş katlı çapraz doğrulamada en iyi eşik kuralı süzülmüş `ln(SDNN/RMSSD)` olmuştur: dengeli doğruluk **0,680**, F1 **0,633**. En iyi lojistik regresyon modeli RR ortalaması, RMSSD, R genliği standart sapması ve SDNN özellikleriyle dengeli doğruluk **0,703**, F1 **0,647** elde etmiştir. Sonuçlar yöntem karşılaştırması içindir ve klinik tanı başarısı olarak yorumlanmamıştır.
