import cv2


class QRScanner:

    @staticmethod
    def decode(image_path):
        try:
            image = cv2.imread(image_path)

            detector = cv2.QRCodeDetector()

            data, points, _ = detector.detectAndDecode(image)

            if points is None or not data:
                return None

            return data

        except Exception as e:
            print(f"[QRScanner] {e}")
            return None