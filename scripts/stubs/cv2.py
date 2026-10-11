"""Stub cv2 module to satisfy ddddocr imports without bundling OpenCV.

ddddocr only imports cv2 for slide verification, detection, and color filtering.
The default OCR classification pipeline uses PIL and onnxruntime directly.
"""


def __getattr__(name: str):
    return _StubMember(name)


class _StubMember:
    def __init__(self, name: str):
        self._name = name

    def __call__(self, *args, **kwargs):
        raise RuntimeError(
            f"cv2.{self._name}() was called, but OpenCV was replaced with a stub "
            "to minimize binary size. Full OpenCV is required for this feature."
        )

    def __int__(self):
        return 0

    def __index__(self):
        return 0
