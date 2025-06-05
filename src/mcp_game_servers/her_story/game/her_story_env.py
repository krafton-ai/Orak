from collections.abc import Generator
from copy import deepcopy
from dataclasses import dataclass, field
import io
import json
import logging
import os
import time
from typing import Any, BinaryIO, List, Optional

from PIL import Image

from mcp_game_servers.base_env import BaseEnv
from mcp_game_servers.gameio.gui_utils import (
    _isMac,
    _isWin,
    mouse_move_to,
    TargetWindow,
)
from mcp_game_servers.gameio.io_env import IOEnvironment
from mcp_game_servers.utils.types.game_io import Action, Obs


if _isWin():
    from mcp_game_servers.gameio.window_capture import WindowCapture
elif _isMac():
    from mcp_game_servers.gameio.window_capture_mac import capture


class HerStoryStateParser:
    line_terminators = (b"\r\n", b"\n", b"\r")

    def __init__(
        self, state_path: str, sleep_time: float = 0.1, read_size: int = 1024
    ) -> None:
        self.state_path = state_path
        self.sleep_time = sleep_time
        self.read_size = read_size
        self.state_iter = self.read_state()

    def get_state(self, timeout: Optional[float] = None) -> dict:
        if timeout is not None:
            self.timeout_deadline = time.time() + timeout
        else:
            self.timeout_deadline = None

        state_str = next(self.state_iter)
        if state_str is None:
            return None
        return json.loads(state_str)

    def read_state(self) -> Generator[Optional[str], None, None]:
        with open(self.state_path, "rb") as f:
            # Find the start pos of the last line
            f.seek(0, 2)
            self.seek_line_backward(f)

            buffer = b""
            while True:
                chunk = f.read()
                if not chunk:
                    if (
                        self.timeout_deadline
                        and time.time() > self.timeout_deadline
                    ):
                        yield None
                        self.timeout_deadline = None
                    else:
                        time.sleep(self.sleep_time)
                    continue
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    yield line.rstrip().decode("utf-8", errors="ignore")

    def seek_line_backward(self, file: BinaryIO):
        """
        Reference: https://github.com/six8/pytailer/blob/master/tailer/__init__.py
        """
        pos = end_pos = file.tell()

        read_size = self.read_size
        if pos > read_size:
            pos -= read_size
        else:
            pos = 0
            read_size = end_pos

        file.seek(pos)

        read_str = file.read(read_size)
        bytes_read = len(read_str)

        if bytes_read and read_str[-1:] in self.line_terminators:
            # The last charachter is a line terminator, don't count this one
            bytes_read -= 1

            if read_str[-2:] == b"\r\n" and b"\r\n" in self.line_terminators:
                # found crlf
                bytes_read -= 1

        while bytes_read > 0:
            # Scan backward, counting the newlines in this bufferfull
            i = bytes_read - 1
            while i >= 0:
                if read_str[i : i + 1] in self.line_terminators:
                    file.seek(pos + i + 1)
                    return file.tell()
                i -= 1

            if pos == 0 or pos - self.read_size < 0:
                # Not enought lines in the buffer, send the whole file
                file.seek(0)
                return None

            pos -= self.read_size
            file.seek(pos)

            read_str = file.read(self.read_size)
            bytes_read = len(read_str)

        return None


@dataclass
class HerStoryObs(Obs):
    state: dict
    scripts: list[str] = field(default_factory=list)
    reward: float = 0
    done: bool = False
    image: Image.Image = None

    def to_text(self) -> str:
        output = ""
        if self.state["status"] == "start_game":
            keyword_init = self.state["keyword_init"]
            output = (
                f'You are at the beginning of the game. The interface shows a search bar with the word "{keyword_init}" typed in, but no action has been taken yet. No search has been executed, so no video results are currently available to you.\n\n'
                f"No video results yet. You must execute a Search.\n"
                f"You must issue a command to start the game.\n"
            )
        elif self.state["status"] == "query_result":
            keyword = self.state["keyword"]
            summary = self.state["summary"]
            output = f'You searched for the keyword "{keyword}". {summary}.\n'
            if len(self.state["video"]) > 0:
                output += f"Search results:\n"
            else:
                output += f"No video results. You must execute a Search.\n"
            for idx, clip in enumerate(self.state["video"]):
                session = clip["session"]
                status = "Not viewed" if clip["new"] else "Viewed"
                outfit = clip["outfit"]
                script = self.scripts[idx]
                output += f'{idx}. [{session}] - Thumbnail: {outfit} - Status: {status} - Script: "{script}"\n'
        return output


@dataclass
class HerStoryAction(Action):
    type: str  # query, play
    keyword: str = ""
    video_index: int = -1

    @classmethod
    def from_string(
        cls,
        action_str: str,
        keyword_max_length: int = -1,
    ) -> "HerStoryAction":
        if action_str.startswith("Search "):
            keyword = action_str.splitlines()[0][len("Search ") :]
            if keyword_max_length > 0:
                keyword = keyword[:keyword_max_length]
            return cls(type="query", keyword=keyword)
        elif action_str.startswith("Play Video "):
            try:
                return cls(
                    type="play",
                    video_index=int(action_str[len("Play Video ") :]),
                )
            except:
                pass
        return cls(type="")


class HerStoryEnv(BaseEnv):
    @dataclass
    class Config:
        state_path: str
        log_path: str
        speedrun: bool
        stop_after_ending: bool
        reset_after_stop: bool
        max_steps: int
        sleep_time: float
        sleep_time_fadein: float
        io_env: dict
        task: str
        input_modality: str
        window_capture_mode: str
        image_max_bytes: int
        keyword_max_length: int
        censor_contents: bool

    cfg: Config

    def configure(self) -> None:
        self.state_path = os.path.expanduser(self.cfg.state_path)
        self.log_path = os.path.expanduser(self.cfg.log_path)
        self.speedrun = self.cfg.speedrun
        self.stop_after_ending = self.cfg.stop_after_ending
        self.reset_after_stop = self.cfg.reset_after_stop
        self.max_steps = self.cfg.max_steps
        self.sleep_time = self.cfg.sleep_time
        self.sleep_time_fadein = self.cfg.sleep_time_fadein
        self.io_env = IOEnvironment(self.cfg.io_env)
        self.state_parser = HerStoryStateParser(
            self.state_path, sleep_time=self.sleep_time
        )

        self.num_videos = 272

        self.logger = logging.getLogger("HerStory")

        self.input_modality = self.cfg.input_modality
        self.window_capture_mode = self.cfg.window_capture_mode
        self.image_max_bytes = self.cfg.image_max_bytes
        self.keyword_max_length = self.cfg.keyword_max_length
        self.censor_contents = self.cfg.censor_contents
        self.censor_words = ["sex", "fuck", "virginity", "sleep with", "slept with", "pregnant"]
        self.use_image = self.input_modality in ["image", "text_image"]
        if self.use_image and _isWin():
            self.window_capture = WindowCapture(
                self.io_env.config.win_name_pattern,
                mode=self.window_capture_mode,
            )

    def initial_obs(self) -> HerStoryObs:
        window = self.get_activate_window()
        state_init = self.state_parser.get_state()
        if state_init["status"] == "title":
            self.obs_main = HerStoryObs(state=state_init)
            resolution = state_init["resolution"]
            self.move_mouse(window, resolution[0] // 2, resolution[1] // 2)
            self.io_env.mouse_click_button("left")
            state_init = self.state_parser.get_state()

        self.check_state(state_init, "start_game")

        image = None
        if self.use_image:
            time.sleep(
                self.sleep_time_fadein
            )  # Wait until the fade-in effect is finished
            image = self.capture_image(win_resolution=state_init["resolution"])

        self.obs_main = HerStoryObs(state=state_init, image=image)
        self.history_search = []
        self.num_queries = 0
        self.num_reads = 0
        self.num_flags = 0
        self.num_steps = 0
        self.num_steps_ending = -1
        self.num_queries_ending = -1
        return self.obs_main

    def obs2text(self, obs: HerStoryObs) -> str:
        return obs.to_text()

    def text2action(self, text: str) -> HerStoryAction:
        return HerStoryAction.from_string(text, self.keyword_max_length)

    def move_mouse(self, window: TargetWindow, x: int, y: int) -> None:
        cl_left, cl_top, _, _ = window.get_client_region(
            self.obs_main.state["resolution"]
        )
        mouse_move_to(
            cl_left + x,
            cl_top + y,
            screen_resolution=self.io_env.screen_resolution,
            env_region=[0, 0],
        )

    def check_state(self, state: dict, status_exp: str):
        self.logger.info(state)
        if state["status"] != status_exp:
            msg_error = f"Status should be '{status_exp}'"
            self.logger.error(msg_error)
            raise RuntimeError("Unexpected state observed")

    def get_activate_window(self):
        windows = self.io_env.get_windows_by_config()
        if not windows:
            msg_error = f"Could not find '{self.io_env.config.env_name}' window"
            self.logger.error(msg_error)
            raise RuntimeError("Game is not executed")
        if _isWin():
            window = windows[0]
        elif _isMac():
            window = next(
                (w for w in windows if w.window.get("kCGWindowName")), None
            )
        window.activate()
        return window

    def get_image_bytes(self, image: Image.Image) -> int:
        buf = io.BytesIO()
        image.save(buf, format="png")
        image_bytes = buf.tell()
        return image_bytes

    def capture_image(
        self, win_resolution: Optional[List[int]] = None
    ) -> Image.Image:
        if _isWin():
            image = self.window_capture.capture(log_path=self.log_path)
        elif _isMac():
            window = self.get_activate_window()
            image = capture(
                window,
                win_resolution=win_resolution,
                log_path=self.log_path,
            )
        # Resize image
        image_bytes = self.get_image_bytes(image)
        scale = image_bytes / self.image_max_bytes
        w, h = image.size
        new_size = (int(w / scale), int(h / scale)) if scale > 1 else (w, h)
        resized_image = image.resize(new_size, Image.Resampling.LANCZOS)
        return resized_image

    def step(
        self, action: HerStoryAction
    ) -> tuple[HerStoryObs, float, bool, bool, dict[str, Any]]:
        window = self.get_activate_window()
        reward = 0
        terminated = False
        truncated = False
        info = {}
        self.num_steps += 1

        if action.type == "query":
            # Step 1: Type keyword
            pos_textfield = self.obs_main.state["pos_textfield"]
            self.move_mouse(window, pos_textfield[0], pos_textfield[1])
            self.io_env.mouse_click_button("left")
            time.sleep(self.sleep_time)
            self.io_env.keys_type(f"{action.keyword}\n")

            # Step 2: Get query results
            state_query = self.state_parser.get_state()
            self.check_state(state_query, "query")

            state_result = self.state_parser.get_state()
            self.check_state(state_result, "query_result")

            image = None
            if self.use_image:
                image = self.capture_image(
                    win_resolution=state_result["resolution"]
                )

            self.obs_main = HerStoryObs(
                state=state_result,
                scripts=["" for _ in range(state_result["num_visible"])],
                image=image,
            )
            self.history_search.append(
                (action.keyword, state_result["num_total"])
            )

            # Step 3: Check game completion
            if state_result["chat_enabled"] == 1:
                if self.num_steps_ending == -1:
                    self.num_steps_ending = self.num_steps
                    self.num_queries_ending = self.num_queries
                """
                if self.stop_after_ending:
                    terminated = True
                    self.obs_main.done = True
                """

            # Step 4: Update score
            self.num_queries += 1
            self.num_reads = state_result["num_reads"]
            self.num_flags = state_result["num_flags"]

        elif (
            action.type == "play"
            and action.video_index >= 0
            and "video" in self.obs_main.state
            and action.video_index < len(self.obs_main.state["video"])
            and self.obs_main.state["status"] == "query_result"
        ):
            video = self.obs_main.state["video"][action.video_index]
            if video["new"] == 1:
                reward += 1

            # Step 1: Open video detail panel
            pos_video = video["pos"]
            self.move_mouse(window, pos_video[0], pos_video[1])
            self.io_env.mouse_click_button("left")

            state_detail = self.state_parser.get_state()
            self.check_state(state_detail, "open_detail")
            time.sleep(self.sleep_time)

            # Step 2: Play video
            pos_play = state_detail["pos_play"]
            self.move_mouse(window, pos_play[0], pos_play[1])
            self.io_env.mouse_click_button("left")

            state_play = self.state_parser.get_state()
            self.check_state(state_play, "play_video")

            # Step 3: Close video
            if self.speedrun:
                time.sleep(self.sleep_time)
                closed = False
                while not closed:
                    self.io_env.key_press("esc")
                    state_close_video = self.state_parser.get_state(
                        self.sleep_time
                    )
                    if state_close_video is not None:
                        closed = True
            else:
                state_close_video = self.state_parser.get_state()
            self.check_state(state_close_video, "close_video")
            time.sleep(self.sleep_time)

            # Step 4: Close video detail panel
            pos_close = state_detail["pos_close"]
            self.move_mouse(window, pos_close[0], pos_close[1])
            self.io_env.mouse_click_button("left")

            state_close_detail = self.state_parser.get_state()
            self.check_state(state_close_detail, "close_detail")
            time.sleep(self.sleep_time)

            # Step 5: Update observation
            self.obs_main = deepcopy(self.obs_main)
            script = state_play["script"]
            if self.censor_contents:
                for cw in self.censor_words:
                    if cw in script:
                        script = ""
                        break
            self.obs_main.scripts[action.video_index] = script
            self.obs_main.state["video"][action.video_index][
                "outfit"
            ] = state_play[
                "outfit"
            ]  # Update outfit
            self.obs_main.state["video"][action.video_index][
                "new"
            ] = 0  # Change: not viewed -> viewed
            self.obs_main.reward = reward

            if self.use_image:  # Update image
                self.obs_main.image = self.capture_image(
                    win_resolution=state_detail["resolution"]
                )

            # Step 6: Update score
            self.num_reads = state_play["num_reads"]
            self.num_flags = state_play["num_flags"]

        # Set terminated, truncated
        if self.num_reads == self.num_videos:
            terminated = True
            self.obs_main.done = True
        elif self.num_steps >= self.max_steps:
            """
            if self.stop_after_ending:
                terminated = True
                self.obs_main.done = True
            """
            truncated = not terminated

        # Reset the environment
        if (terminated or truncated) and self.reset_after_stop:
            # Step 1: Open setting panel
            pos_setting = self.obs_main.state["pos_setting"]
            self.move_mouse(window, pos_setting[0], pos_setting[1])
            self.io_env.mouse_click_button("left")

            state_setting = self.state_parser.get_state()
            self.check_state(state_setting, "open_setting")
            time.sleep(self.sleep_time)

            # Step 2: Click 'Delete session data' button
            pos_delete = state_setting["pos_delete"]
            self.move_mouse(window, pos_delete[0], pos_delete[1])
            self.io_env.mouse_click_button("left")
            time.sleep(self.sleep_time)

            # Step 3: Click 'DELETE' button of the popup
            pos_delete2 = state_setting["pos_delete2"]
            self.move_mouse(window, pos_delete2[0], pos_delete2[1])
            self.io_env.mouse_click_button("left")

        return self.obs_main, reward, terminated, truncated, info

    def evaluate(self, obs: HerStoryObs) -> tuple[int, bool]:
        score = self.num_reads
        """
        score = {
            "num_reads": self.num_reads,
            "num_flags": self.num_flags,
            "num_queries": self.num_queries,
            "num_steps_ending": self.num_steps_ending,
            "num_queries_ending": self.num_queries_ending,
        }
        """
        return score, obs.done

    def get_game_info(self) -> dict:
        history_search = "; ".join(f"{s} ({n})" for s, n in self.history_search)
        return {
            "history_search": history_search,
        }
