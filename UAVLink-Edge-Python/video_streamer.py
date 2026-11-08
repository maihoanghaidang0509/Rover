import cv2 as cv
import logging
import shlex
import subprocess
import threading
import time
from picamera2 import Picamera2

logger = logging.getLogger("VideoStreamer")

class VideoStreamer:
    """Stream video từ Pi Camera trực tiếp tới QGroundControl qua luồng UDP H.264

    Sử dụng Picamera2 và OpenCV để sẵn sàng vẽ khung hình (HUD/LiDAR).
    """

    def __init__(self, config):
        self.cfg = getattr(config, 'video', {}) if hasattr(config, 'video') else {}
        if not isinstance(self.cfg, dict):
            self.cfg = {}

        self.proc = None
        self.running = False

        # Cấu hình từ config.yaml
        self.target_ip = self.cfg.get('laptop_ip', '100.111.253.11')
        self.port = self.cfg.get('port', 5600)
        self.width = self.cfg.get('width', 640)
        self.height = self.cfg.get('height', 480)
        self.fps = self.cfg.get('fps', 30)
        self.rotation = self.cfg.get('rotation', 0)
        self.bitrate = self.cfg.get('bitrate_kbps', 800)

    def _get_flip_element(self):
        """Xử lý góc xoay linh hoạt và tiết kiệm CPU"""
        if self.rotation == 90:
            return "! videoflip method=clockwise "
        elif self.rotation == 180:
            return "! videoflip method=rotate-180 "
        elif self.rotation == 270:
            return "! videoflip method=counterclockwise "
        return ""  # Nếu = 0 thì không dùng videoflip để giảm tải CPU

    def _build_gst_cmd(self):
        frame_size = self.width * self.height * 3
        flip_str = self._get_flip_element()
        
        # Định dạng bgr để khớp với output của OpenCV (cv.cvtColor)
        video_cmd = (
            f"gst-launch-1.0 fdsrc blocksize={frame_size} do-timestamp=true ! "
            f"videoparse format=bgr width={self.width} height={self.height} framerate={self.fps}/1 ! "
            f"videoconvert {flip_str}! "
            f"queue leaky=downstream max-size-buffers=1 max-size-bytes=0 max-size-time=0 ! "
            f"x264enc threads=1 tune=zerolatency speed-preset=ultrafast bitrate={self.bitrate} ! "
            f"video/x-h264, profile=baseline ! "
            f"h264parse ! rtph264pay config-interval=1 pt=96 ! "
            f"udpsink host={self.target_ip} port={self.port} sync=false buffer-size=2097152"
        )
        return shlex.split(video_cmd)

    def start(self):
        self.running = True
        threading.Thread(target=self._stream_loop, daemon=True).start()

    def _stream_loop(self):
        cmd_list = self._build_gst_cmd()

        while self.running:
            picam2 = None
            try:
                logger.info(f"Khởi tạo Pi Camera → UDP {self.target_ip}:{self.port}")
                picam2 = Picamera2()
                video_config = picam2.create_video_configuration(
                    main={"size": (self.width, self.height), "format": "RGB888"},
                    controls={"FrameRate": self.fps}
                )
                picam2.configure(video_config)
                picam2.start()
                time.sleep(0.5)

                self.proc = subprocess.Popen(cmd_list, stdin=subprocess.PIPE)

                while self.running:
                    frame_rgb = picam2.capture_array()
                    if frame_rgb is None:
                        break

                    # Chuyển sang BGR để OpenCV xử lý và khớp với videoparse format=bgr
                    frame = cv.cvtColor(frame_rgb, cv.COLOR_RGB2BGR)

                    # --- VẼ THÔNG TIN LIDAR / HUD LÊN 'frame' TẠI ĐÂY ---

                    self.proc.stdin.write(frame.tobytes())
                    self.proc.stdin.flush()

            except Exception as e:
                logger.error(f"Lỗi luồng Video: {e}")
                time.sleep(2.0)
            finally:
                if self.proc:
                    try:
                        if self.proc.stdin: self.proc.stdin.close()
                        self.proc.wait(timeout=1)
                    except Exception: pass
                if picam2:
                    try: picam2.stop()
                    except Exception: pass

    def stop(self):
        self.running = False
        if self.proc:
            try: self.proc.terminate()
            except Exception: pass