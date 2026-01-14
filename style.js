const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const context = canvas.getContext('2d');
const processed = document.getElementById('processed');
const recordButton = document.getElementById('record');
let currentRotation = 0;
let stream;
let mediaRecorder;
const recordedChunks = [];

// Hàm xoay video
function rotate() {
    currentRotation += 90;
    video.style.transform = `rotate(${currentRotation}deg)`;
    processed.style.transform = `rotate(${currentRotation}deg)`;
}

// Gắn nút xoay
document.getElementById('rotate-button').addEventListener('click', rotate);

// Lấy camera và khởi tạo mediaRecorder + socket
navigator.mediaDevices.getUserMedia({ video: true })
    .then(function (userStream) {
        stream = userStream;
        video.srcObject = stream;

        // MediaRecorder để ghi video
        mediaRecorder = new MediaRecorder(stream, { mimeType: 'video/webm' });

        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                recordedChunks.push(event.data);
            }
        };

        mediaRecorder.onstop = () => {
            const blob = new Blob(recordedChunks, { type: 'video/webm' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            document.body.appendChild(a);
            a.style.display = 'none';
            a.href = url;
            a.download = 'recorded-video.webm';
            a.click();
            window.URL.revokeObjectURL(url);
        };

        // Gửi frame lên server qua socket
        setInterval(captureAndSendFrame, 100);
    })
    .catch(function (error) {
        console.error('Error accessing the camera:', error);
    });

// Start/Stop record
recordButton.addEventListener('click', () => {
    if (recordButton.textContent === 'Record video') {
        startRecording();
    } else {
        stopRecording();
    }
});

function startRecording() {
    recordedChunks.length = 0;
    mediaRecorder.start();
    recordButton.textContent = 'Stop recording';
}

function stopRecording() {
    mediaRecorder.stop();
    recordButton.textContent = 'Record video';
}

// Gửi frame qua socket
function captureAndSendFrame() {
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const frame = canvas.toDataURL('image/jpeg');
    socket.emit('video_frame', frame);
}

// Socket nhận frame xử lý từ backend
const socket = io.connect('http://' + location.hostname + ':' + location.port);
socket.on('processed_frame', data => {
    processed.src = 'data:image/jpeg;base64,' + data;
});
