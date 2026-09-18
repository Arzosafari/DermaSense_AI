# PanDerm 8-Class Mapping Source Documentation

## Verification Source

**Official Training Labels from PanDerm Training Code:**

```python
LABELS = [
    "NV",
    "MEL", 
    "BKL",
    "BCC",
    "AK",
    "VASC",
    "DF",
    "SCC",
]

LABEL_NAMES = {
    "MEL": "Melanoma",
    "NV": "Melanocytic Nevus",
    "BCC": "Basal Cell Carcinoma",
    "AK": "Actinic Keratosis",
    "BKL": "Benign Keratosis",
    "DF": "Dermatofibroma",
    "VASC": "Vascular Lesion",
    "SCC": "Squamous Cell Carcinoma",
}
```

## Verified Class Mapping

Based on official training labels, the exact checkpoint mapping is:

| Index | Short Code | Class Name | Malignant |
|-------|-----------|------------|-----------|
| 0 | NV | Melanocytic Nevus | Benign |
| 1 | MEL | Melanoma | Malignant |
| 2 | BKL | Benign Keratosis | Benign |
| 3 | BCC | Basal Cell Carcinoma | Malignant |
| 4 | AK | Actinic Keratosis | Malignant |
| 5 | VASC | Vascular Lesion | Benign |
| 6 | DF | Dermatofibroma | Benign |
| 7 | SCC | Squamous Cell Carcinoma | Malignant |

## Verification Status

✅ **VERIFIED** - Official training labels confirmed
✅ **Checkpoint args.csv_path**: `panderm_combined_isic_pad.csv`
✅ **Exact class order from training code**
✅ **Malignant classification confirmed**: MEL, BCC, AK, SCC