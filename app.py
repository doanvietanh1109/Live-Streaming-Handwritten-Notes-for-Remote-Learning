from flask import Flask, render_template
from flask_socketio import SocketIO
from flask_cors import CORS

import cv2
import numpy as np
import base64
import time
import onnxruntime
from engineio.payload import Payload

# Import libs nội bộ
from libs.hand_remover.hand_remover import HandRemover
from libs.paper_processor.paper_processor import PaperProcessor
import libs.filter as filter

# ==============================

size = 144

class PaperSegment:
    def __init__(self):
        # Load model onnx
        self.model = onnxruntime.InferenceSession(
            "pretrained/model.onnx",
            providers=["CUDAExecutionProvider", "CPUExecutionProvider"]
        )
        self.input_name = self.model.get_inputs()[0].name
        print("[INFO] Model loaded:", self.input_name)

    def preprocess(self, image):
        # Convert BGR -> RGB
        image = image[:, :, ::-1]
        image = cv2.resize(image, (size, size)).reshape(1, size, size, 3)
        return image.astype("float32") / 255

    def predict(self, image):
        image = self.preprocess(image)
        result = self.model.run(None, {self.input_name: image})
        pred = result[0].reshape(size, size)

        # Fix gán sai
        pred[pred >= 0.0] = 1
        return pred


# ==============================

# Giới hạn payload để tránh lỗi buffer
Payload.max_decode_packets = 50

app = Flask(__name__)
CORS(app)

# SocketIO cho phép CORS tất cả
socketio = SocketIO(app, cors_allowed_origins="*")

# Khởi tạo processor
model = PaperSegment()
paper_processor = PaperProcessor()
hand_remover = HandRemover()


@app.route("/")
def index():
    return render_template("index.html")


@socketio.on("video_frame")
def handle_frame(data):
    print("[INFO] Frame received")
    start = time.time()

    try:
        # Giải mã base64
        encoded_data = data.split(",")[1]
        nparr = np.frombuffer(base64.b64decode(encoded_data), np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            print("[WARN] frame is None after decode")
            return

        # Lật ảnh
        image = cv2.flip(frame, 0)
        image = cv2.flip(image, 1)
        draw = image.copy()

        # Chạy segmentation model
        pred = model.predict(image)

        # Xử lý giấy
        is_cropped, processed_image, draw = paper_processor.get_paper_image(
            image, pred, draw=draw
        )

        if processed_image is None:
            print("[WARN] processed_image is None")
            return

        # Bỏ tay, bỏ bóng
        processed_image = hand_remover.process(processed_image, is_cropped=is_cropped)
        processed_image = filter.remove_shadow(processed_image)

        # Encode ảnh
        ret, jpeg = cv2.imencode(".jpg", processed_image)
        if not ret:
            print("[ERROR] cv2.imencode failed")
            return

        processed_encoded = base64.b64encode(jpeg.tobytes()).decode("utf-8")

        # Emit về client
        socketio.emit("processed_frame", processed_encoded)

        end = time.time()
        print(f"[INFO] Process time: {end - start:.3f} sec")

    except Exception as e:
        print("[ERROR] Exception in handle_frame:", str(e))


if __name__ == "__main__":
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)
