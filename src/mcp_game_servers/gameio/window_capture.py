import os
import re
import mss
import ctypes
import platform

from PIL import Image
from datetime import datetime
from screeninfo import get_monitors

IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    import win32api
    import win32gui
    import win32ui
    import win32con
    import dxcam

class WindowCapture:
    def __init__(self, window_title_pattern: str, mode: str = "bitblt", adjust_dpi: bool = False):
        # mode: "bitblt", "mss", or "dxcam"
        # for game with directx, use "dxcam", e.g., Stardew Valley
        # note that dxcam does not work in remote desktop
        # mss requires game window to be in the foreground
        # bitblt is the most compatible method and allows background capture

        # if the taken screenshot is smaller than original screen, try to set adjust_dpi to True
        if adjust_dpi:
            ctypes.windll.user32.SetProcessDPIAware()

        self.window_title_pattern = window_title_pattern
        self.hwnd = self._find_window_by_regex(window_title_pattern)
        if not self.hwnd:
            raise Exception(f"No window matching pattern '{window_title_pattern}' was found.")
        
        self.mode = mode

    def _find_window_by_regex(self, pattern: str):
        hwnd_match = None

        def enum_callback(hwnd, _):
            nonlocal hwnd_match
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if re.search(pattern, title):
                    hwnd_match = hwnd

        win32gui.EnumWindows(enum_callback, None)
        return hwnd_match

    def capture_mss(self) -> Image.Image:
        bbox = win32gui.GetWindowRect(self.hwnd)
        with mss.mss() as sct:
            screenshot = sct.grab({
                "left": bbox[0],
                "top": bbox[1],
                "width": bbox[2] - bbox[0],
                "height": bbox[3] - bbox[1],
            })
            img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)

        return img

    def capture_dxcam(self) -> Image.Image:
        # get window index
        hmonitor = win32api.MonitorFromWindow(self.hwnd, win32con.MONITOR_DEFAULTTONEAREST)
        monitor_name = win32api.GetMonitorInfo(hmonitor)["Device"]

        monitor_index = -1
        dxcam_factory = getattr(dxcam, "__factory")
        for i in range(len(dxcam_factory.outputs[0])):
            if dxcam_factory.outputs[0][i].desc.DeviceName == monitor_name:
                monitor_index = i
                break

        assert monitor_index != -1, f"Monitor with name {monitor_name} not found."

        # get window rect
        left, top, right, bottom = win32gui.GetClientRect(self.hwnd)

        camera = dxcam.create(output_idx=monitor_index, region=(left, top, right, bottom))

        screenshot = camera.grab()
        image = Image.fromarray(screenshot)

        return image

    def capture_bitblt(self) -> Image.Image:
        left, top, right, bottom = win32gui.GetClientRect(self.hwnd)
        width = right - left
        height = bottom - top

        hwnd_dc = win32gui.GetDC(self.hwnd)
        src_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        mem_dc = src_dc.CreateCompatibleDC()

        bmp = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(src_dc, width, height)
        mem_dc.SelectObject(bmp)

        mem_dc.BitBlt((0, 0), (width, height), src_dc, (0, 0), win32con.SRCCOPY)

        bmp_info = bmp.GetInfo()
        bmp_data = bmp.GetBitmapBits(True)

        img = Image.frombuffer(
            "RGB",
            (bmp_info["bmWidth"], bmp_info["bmHeight"]),
            bmp_data,
            "raw", "BGRX", 0, 1
        )

        win32gui.DeleteObject(bmp.GetHandle())
        mem_dc.DeleteDC()
        src_dc.DeleteDC()
        win32gui.ReleaseDC(self.hwnd, hwnd_dc)

        return img

    def capture(self, log_path=None) -> Image.Image:
        if self.mode == "mss":
            image = self.capture_mss()
        elif self.mode == "dxcam":
            image = self.capture_dxcam()
        else:
            image = self.capture_bitblt()
        
        if log_path:
            curtime = datetime.now().strftime("%H%M%S%f")
            image.save(os.path.join(log_path, f"{curtime}.png"))
        
        return image
