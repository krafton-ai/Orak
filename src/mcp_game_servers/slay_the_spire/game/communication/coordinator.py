import sys
import queue
import threading
import json
import collections
import logging

from mcp_game_servers.slay_the_spire.game.spire.game import Game
from mcp_game_servers.slay_the_spire.game.spire.screen import ScreenType
from mcp_game_servers.slay_the_spire.game.communication.action import Action, StartGameAction, PotionAction

logger = logging.getLogger(__name__)

def read_stdin(input_queue):
    """Read lines from stdin and write them to a queue

    :param input_queue: A queue, to which lines from stdin will be written
    :type input_queue: queue.Queue
    :return: None
    """
    while True:
        stdin_input = ""
        while True:
            input_char = sys.stdin.read(1)
            if input_char == '\n':
                break
            else:
                stdin_input += input_char
        input_queue.put(stdin_input)


def write_stdout(output_queue):
    """Read lines from a queue and write them to stdout

    :param output_queue: A queue, from which this function will receive lines of text
    :type output_queue: queue.Queue
    :return: None
    """
    while True:
        output = output_queue.get()
        print(output, end='\n', flush=True)


class Coordinator:
    """An object to coordinate communication with Slay the Spire"""

    def __init__(self):
        self.input_queue = queue.Queue()
        self.output_queue = queue.Queue()
        self.input_thread = threading.Thread(target=read_stdin, args=(self.input_queue,))
        self.output_thread = threading.Thread(target=write_stdout, args=(self.output_queue,))
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

