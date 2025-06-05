from datetime import datetime
import os
from typing import List, Optional

from PIL import Image
import Quartz

from mcp_game_servers.gameio.gui_utils import TargetWindow


def capture(window: TargetWindow, win_resolution: Optional[List[int]] = None, log_path=None) -> Image.Image:
    window_id = window.window["kCGWindowNumber"]

    # Capture window
    info = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionIncludingWindow, window_id)[0]
    bounds = info["kCGWindowBounds"]
    x = int(bounds["X"])
    y = int(bounds["Y"])
    w = int(bounds["Width"])
    h = int(bounds["Height"])

    image_ref = Quartz.CGWindowListCreateImage(
        Quartz.CGRectMake(x, y, w, h),
        Quartz.kCGWindowListOptionIncludingWindow,
        window_id,
        Quartz.kCGWindowImageDefault
    )

    width = Quartz.CGImageGetWidth(image_ref)
    height = Quartz.CGImageGetHeight(image_ref)
    bytes_per_row = Quartz.CGImageGetBytesPerRow(image_ref)
    data_provider = Quartz.CGImageGetDataProvider(image_ref)
    data = Quartz.CGDataProviderCopyData(data_provider)
    image = Image.frombuffer("RGBA", (width, height), data, "raw", "BGRA", bytes_per_row, 1)
    image = image.convert("RGBA")

    # Adjust Retina scale
    image = image.resize((w, h), Image.Resampling.LANCZOS)

    if win_resolution is not None:
        image = image.crop((0, h - win_resolution[1], w, h))

    # Logging
    if log_path:
        curtime = datetime.now().strftime("%H%M%S%f")
        image.save(os.path.join(log_path, f"{curtime}.png"))

    return image
