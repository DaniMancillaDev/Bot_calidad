from pathlib import Path


class OnnxOrientationDetector:
    """
    Adaptador: delega a orientation_engine.py (shared/infrastructure/orientation/).

    Mapeo:
    detectar()        → orientation_engine.detect_orientation()
    detectar_batch()  → orientation_engine.detect_orientations_batch()

    Import diferido para evitar cargar ONNX/NumPy al importar el módulo.
    """

    def detectar(self, img_path) -> int:
        from shared.infrastructure.orientation.orientation_engine import detect_orientation
        return detect_orientation(img_path)

    def detectar_batch(self, foto_paths: list) -> dict:
        from shared.infrastructure.orientation.orientation_engine import detect_orientations_batch
        return detect_orientations_batch(foto_paths)
