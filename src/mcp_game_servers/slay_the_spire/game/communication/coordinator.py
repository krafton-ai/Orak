import queue
import threading
import json
import collections
import logging
import os
import time

from mcp_game_servers.slay_the_spire.game.spire.game import Game
from mcp_game_servers.slay_the_spire.game.spire.screen import ScreenType
from mcp_game_servers.slay_the_spire.game.communication.action import Action, StartGameAction, PotionAction

logger = logging.getLogger(__name__)

def read_from_input_file(input_queue, filepath):
    """Atomically reads a file by renaming it, processing it, and then deleting it.

    :param input_queue: A queue, to which lines from the file will be written
    :type input_queue: queue.Queue
    :param filepath: Path to the input file
    :type filepath: str
    :return: None
    """
    processing_filepath = filepath + ".processing"
    while True:
        try:
            # Check for the file without locking it
            if os.path.exists(filepath):
                # Atomically rename the file to take "ownership" of it.
                # This prevents the read-and-truncate race condition.
                os.rename(filepath, processing_filepath)

                # Now we safely own the .processing file.
                with open(processing_filepath, 'r') as f:
                    content = f.read().strip()
                
                # We are done with the file, so we can remove it.
                os.remove(processing_filepath)

                if content:
                    input_queue.put(content)
                
                # Give a small break to avoid busy-waiting
                time.sleep(0.05)
            else:
                # File doesn't exist, wait a bit before checking again.
                time.sleep(0.1)
        except FileNotFoundError:
            # This can happen in a race condition if another process/thread
            # renames the file between our os.path.exists and os.rename.
            # This is safe to ignore; we'll just loop and try again.
            continue
        except PermissionError:
            # This is expected on Windows if the game process is writing to the
            # file when we try to rename it. We wait a moment and retry.
            time.sleep(0.05)
            continue
        except Exception as e:
            logger.error(f"Error processing input file {filepath}: {e}")
            # If an error occurred, the .processing file might be left over.
            # Try to clean it up.
            if os.path.exists(processing_filepath):
                try:
                    os.remove(processing_filepath)
                except Exception as cleanup_e:
                    logger.error(f"Failed to cleanup processing file {processing_filepath}: {cleanup_e}")
            time.sleep(1)

def write_to_output_file(output_queue, filepath):
    """Read lines from a queue and write them to filepath, overwriting the file.

    :param output_queue: A queue, from which this function will receive lines of text
    :type output_queue: queue.Queue
    :param filepath: Path to the output file
    :type filepath: str
    :return: None
    """
    while True:
        try:
            output = output_queue.get() # Blocks until an item is available
            with open(filepath, 'w') as f:
                f.write(output + '\n') # Write with a newline
        except Exception as e:
            logger.error(f"Error writing to {filepath}: {e}")
            time.sleep(1)


class Coordinator:
    """An object to coordinate communication with Slay the Spire"""

    def __init__(self, mod_input_path, mod_output_path):
        self.input_queue = queue.Queue()
        self.output_queue = queue.Queue()
        
        # Ensure communication directories exist
        try:
            if not os.path.exists(os.path.dirname(mod_input_path)):
                os.makedirs(os.path.dirname(mod_input_path))
            if not os.path.exists(os.path.dirname(mod_output_path)):
                os.makedirs(os.path.dirname(mod_output_path))
        except IOError as e:
            logger.error(f"Failed to create directories for communication files: {e}")

        # Initialize/clean communication files
        processing_input_path = mod_output_path + ".processing"
        try:
            # Clear main input file by ensuring it's empty
            with open(mod_output_path, 'w'):
                pass
            # Clear output file
            with open(mod_input_path, 'w'):
                pass
            # Remove any stale processing file from a previous crash
            if os.path.exists(processing_input_path):
                os.remove(processing_input_path)
        except IOError as e:
            logger.error(f"Failed to initialize communication files: {e}")
            # Depending on requirements, might want to raise this error

        self.input_thread = threading.Thread(target=read_from_input_file, args=(self.input_queue, mod_output_path))
        self.output_thread = threading.Thread(target=write_to_output_file, args=(self.output_queue, mod_input_path))
        self.input_thread.daemon = True
        self.input_thread.start()
        self.output_thread.daemon = True
        self.output_thread.start()
        self.action_queue = collections.deque()
        self.state_change_callback = None
        self.out_of_game_callback = None
        self.error_callback = None
        self.game_is_ready = False
        self.stop_after_run = False
        self.in_game = False
        self.last_game_state = None
        self.last_error = None

    def signal_ready(self):
        """Indicate to Communication Mod that setup is complete

        Must be used once, before any other commands can be sent.
        :return: None
        """
        self.send_message("ready")

    def send_message(self, message):
        """Send a command to Communication Mod and start waiting for a response

        :param message: the message to send
        :type message: str
        :return: None
        """
        self.output_queue.put(message)
        self.game_is_ready = False

    def add_action_to_queue(self, action):
        """Queue an action to perform when ready

        :param action: the action to queue
        :type action: Action
        :return: None
        """
        self.action_queue.append(action)

    def clear_actions(self):
        """Remove all actions from the action queue

        :return: None
        """
        self.action_queue.clear()

    def execute_next_action(self):
        """Immediately execute the next action in the action queue

        :return: None
        """
        action = self.action_queue.popleft()
        action.execute(self)

    def execute_next_action_if_ready(self):
        """Immediately execute the next action in the action queue, if ready to do so

        :return: None
        """
        if len(self.action_queue) > 0 and self.action_queue[0].can_be_executed(self):
            logger.info(f"self.action_queue: {self.action_queue}")
            self.execute_next_action()

    def register_state_change_callback(self, new_callback):
        """Register a function to be called when a message is received from Communication Mod

        :param new_callback: the function to call
        :type new_callback: function(game_state: Game) -> Action
        :return: None
        """
        self.state_change_callback = new_callback

    def register_command_error_callback(self, new_callback):
        """Register a function to be called when an error is received from Communication Mod

        :param new_callback: the function to call
        :type new_callback: function(error: str) -> Action
        :return: None
        """
        self.error_callback = new_callback

    def register_out_of_game_callback(self, new_callback):
        """Register a function to be called when Communication Mod indicates we are in the main menu

        :param new_callback: the function to call
        :type new_callback: function() -> Action
        :return: None
        """
        self.out_of_game_callback = new_callback

    def get_next_raw_message(self, block=False, timeout=None):
        """Get the next message from Communication Mod as a string

        :param block: set to True to wait for the next message
        :type block: bool
        :return: the message from Communication Mod
        :rtype: str
        """
        logger.info(f"block: {block}")
        logger.info(f"self.input_queue.empty(): {self.input_queue.empty()}")
        if block or not self.input_queue.empty():
            return self.input_queue.get(timeout=timeout)

    def receive_game_state_update(self, block=False, timeout=None, perform_callbacks=True):
        """Using the next message from Communication Mod, update the stored game state

        :param block: set to True to wait for the next message
        :type block: bool
        :param perform_callbacks: set to True to perform callbacks based on the new game state
        :type perform_callbacks: bool
        :return: whether a message was received
        """
        logger.info("START get_next_raw_message")
        try:
            message = self.get_next_raw_message(block, timeout=timeout)
        except queue.Empty:
            return False
        logger.info("END get_next_raw_message")
        if message is not None:
            communication_state = json.loads(message)
            logger.info(f"communication_state: {communication_state}")

            self.last_error = communication_state.get("error", None)
            
            self.game_is_ready = communication_state.get("ready_for_command")

            if self.last_error is None:
                self.in_game = communication_state.get("in_game")
                if self.in_game:
                    self.last_game_state = Game.from_json(communication_state.get("game_state"), communication_state.get("available_commands"))

            if perform_callbacks:
                if self.error_callback is not None and self.last_error is not None:
                    self.action_queue.clear()
                    new_action = self.error_callback(self.last_error)
                    self.add_action_to_queue(new_action)
                elif self.in_game:
                    if len(self.action_queue) == 0:
                        new_action = self.state_change_callback(self.last_game_state)
                        if new_action is not None:
                            self.add_action_to_queue(new_action)
                elif self.stop_after_run:
                    self.clear_actions()
                else:
                    new_action = self.out_of_game_callback()
                    self.add_action_to_queue(new_action)
            return True
        return False

    # def run(self):
    #     """Start executing actions forever

    #     :return: None
    #     """
    #     while True:
    #         self.execute_next_action_if_ready()
    #         self.receive_game_state_update(perform_callbacks=True)

    def play_one_game(self, player_class, ascension_level=0, seed=None):
        """

        :param player_class: the class to play
        :type player_class: PlayerClass
        :param ascension_level: the ascension level to use
        :type ascension_level: int
        :param seed: the alphanumeric seed to use
        :type seed: str
        :return: True if the game was a victory, else False
        :rtype: bool
        """
        self.clear_actions()
        logger.info("play_one_game starts")
        while not self.game_is_ready:
            self.receive_game_state_update(block=True, perform_callbacks=False)
        if not self.in_game:
            StartGameAction(player_class, ascension_level, seed).execute(self)
            self.receive_game_state_update(block=True)
        while self.in_game:
            self.execute_next_action_if_ready()
            self.receive_game_state_update()
        logger.info("play_one_game end")        
        if self.last_game_state.screen_type == ScreenType.GAME_OVER:
            return self.last_game_state.screen.victory
        else:
            return False

