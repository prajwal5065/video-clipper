"""Face-aware horizontal crop position (OpenCV Haar cascade, no model download)."""
import statistics


def face_center(video, start, end, samples=12):
    """Return the median horizontal face position as a 0..1 fraction of frame width,
    or None if no face is found reliably (caller falls back to centre crop)."""
    import cv2  # lazy import

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        return None
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    xs = []
    for i in range(samples):
        t = start + (end - start) * (i + 0.5) / samples
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            continue
        h, w = frame.shape[:2]
        scale = 480 / h if h > 480 else 1.0
        small = cv2.resize(frame, (int(w * scale), int(h * scale))) if scale != 1.0 else frame
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
        if len(faces):
            x, _y, fw, _fh = max(faces, key=lambda f: f[2] * f[3])
            xs.append((x + fw / 2) / small.shape[1])
    cap.release()
    if len(xs) < max(2, samples // 4):
        return None
    return statistics.median(xs)
