"""
Motor de detección de orientación de imágenes via ONNX.

Módulo puro: sin dependencias de Django, bot ni Excel.
Puede ser importado desde shared/ o web/ indistintamente.

Funciones públicas:
    detect_orientation(img_path) → int  (0 / 90 / 180 / 270)
    detect_orientations_batch(foto_paths) → dict[int, int]
"""
import warnings
import numpy as np
import onnxruntime as ort
from pathlib import Path
from PIL import Image, ImageFile, ImageOps

warnings.filterwarnings("ignore")
ImageFile.LOAD_TRUNCATED_IMAGES = True


# ============================================================
# MODELO ONNX  (singleton — se carga una sola vez por proceso)
# ============================================================
_onnx_session = None


def _get_onnx_session():
    """Carga el modelo ONNX de HuggingFace la primera vez y lo cachea."""
    global _onnx_session
    if _onnx_session is None:
        try:
            from huggingface_hub import hf_hub_download
            model_path = hf_hub_download(
                repo_id='Chuckame/deep-image-orientation-angle-detection',
                filename='deep-image-orientation-angle-detection.onnx'
            )
            _onnx_session = ort.InferenceSession(model_path)
        except Exception as e:
            print(f"[WARN] No se pudo cargar modelo ONNX: {e}")
            _onnx_session = None
    return _onnx_session


def _predict_angle_onnx(img: Image.Image) -> float:
    session = _get_onnx_session()
    if session is None:
        return 0.0
    img_r = img.convert('RGB').resize((224, 224), Image.LANCZOS)
    arr   = np.array(img_r, dtype=np.float32)
    arr   = arr.transpose(2, 0, 1)
    arr   = np.expand_dims(arr, axis=0) / 255.0
    result = session.run(None, {'image': arr})
    return float(result[0][0][0])


# ============================================================
# API PÚBLICA
# ============================================================

def detect_orientation(img_path) -> int:
    """
    Detecta el ángulo de corrección necesario para una imagen.

    Returns:
        int: uno de 0, 90, 180, 270 (grados de rotación a aplicar)
    """
    try:
        img = Image.open(img_path)
        img = ImageOps.exif_transpose(img)
        raw = _predict_angle_onnx(img) % 360
        if   raw < 45 or raw > 315:  return 0
        elif 45  <= raw < 135:       return 270
        elif 135 <= raw < 225:       return 180
        else:                        return 90
    except Exception as e:
        print(f"[WARN] Orientación fallida en {img_path}: {e}")
        return 0


def detect_orientations_batch(foto_paths: list) -> dict:
    """
    Detecta orientación de múltiples fotos.

    Args:
        foto_paths: lista de paths (str o Path)
    Returns:
        dict: {numero_int: angulo_int}
    """
    resultado = {}
    for path in foto_paths:
        path = Path(path)
        try:
            num = int(path.stem)
            resultado[num] = detect_orientation(path)
        except Exception:
            pass
    return resultado
