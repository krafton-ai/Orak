from mcp_game_servers.slay_the_spire.game.spire.screen import ScreenType, RewardType


class Action:
    """A base class for an action to take in Slay the Spire"""

    def __init__(self, command="state", requires_game_ready=True):
        self.command = command
        self.requires_game_ready = requires_game_ready

    def can_be_executed(self, coordinator):
        """Indicates whether the given action can currently be executed, given the coordinator's state

        :param coordinator: The coordinator which will be used to execute the action
        :return: True if the action can currently be executed
        ":rtype: boolean
        """
        if self.requires_game_ready:
            return coordinator.game_is_ready
        else:
            return True

    def execute(self, coordinator):
        """Given the coordinator's current state, execute the given action

        :param coordinator: The coordinator which will be used to execute the action
        :return: None
        """
        coordinator.send_message(self.command)
    
    def __str__(self):
        attrs = {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
        attrs_str = ', '.join(f"{k}={v!r}" for k, v in attrs.items())
        return f"{self.__class__.__name__}({attrs_str})"

    def __repr__(self):
        return self.__str__()


class PlayCardAction(Action):
    """An action to play a specified card from your hand"""

    def __init__(self, card=None, card_index=-1, target_monster=None, target_index=None):
        super().__init__("play")
        self.card = card
        self.card_index = card_index
        self.target_index = target_index
        self.target_monster = target_monster

    def execute(self, coordinator):
        if self.card is not None:
            self.card_index = coordinator.last_game_state.hand.index(self.card) + 1
        if self.card_index == -1:
            raise Exception("Specified card for CardAction is not in hand")
        hand_card_index = self.card_index
        if self.target_monster is not None:
            self.target_index = self.target_monster.monster_index
        if self.target_index is None:
            coordinator.send_message("{} {}".format(self.command, hand_card_index))
        else:
            coordinator.send_message("{} {} {}".format(self.command, hand_card_index, self.target_index))


class PotionAction(Action):
    """An action to use or discard a selected potion"""

    def __init__(self, use, potion=None, potion_index=-1, target_monster=None, target_index=None):
        super().__init__("potion")
        self.use = use
        self.potion = potion
        self.potion_index = potion_index
        self.target_monster = target_monster
        self.target_index = target_index

    def execute(self, coordinator):
        if self.potion is not None:
            self.potion_index = coordinator.last_game_state.potions.index(self.potion)
        if self.potion_index == -1:
            raise Exception("Specified potion for PotionAction is not available")
        arguments = [self.command]
        if self.use:
            arguments.append("use")
        else:
            arguments.append("discard")
        arguments.append(str(self.potion_index))
        if self.target_monster is not None:
            self.target_index = self.target_monster.monster_index
        if self.target_index is not None:
            arguments.append(str(self.target_index))
        coordinator.send_message(" ".join(arguments))


class EndTurnAction(Action):
    """An action to end your turn"""

    def __init__(self):
        super().__init__("end")


class ProceedAction(Action):
    """An action to use the CommunicationMod 'Proceed' command"""

    def __init__(self):
        super().__init__("proceed")


class CancelAction(Action):
    """An action to use the CommunicationMod 'Cancel' command"""

    def __init__(self):
        super().__init__("cancel")


class ChooseAction(Action):
    """An action to use the CommunicationMod 'Choose' command"""

    def __init__(self, choice_index=0, name=None):
        super().__init__("choose")
        self.choice_index = choice_index
        self.name = name

    def execute(self, coordinator):
        if self.name is not None:
            coordinator.send_message("{} {}".format(self.command, self.name))
        else:
            coordinator.send_message("{} {}".format(self.command, self.choice_index))


class ChooseShopkeeperAction(ChooseAction):
    """An action to open the shop on a shop screen"""

    def __init__(self):
        super().__init__(name="shop")


class OpenChestAction(ChooseAction):
    """An action to open a chest on a chest screen"""

    def __init__(self):
        super().__init__(name="open")


class BuyCardAction(ChooseAction):
    """An action to buy a card in a shop"""

    def __init__(self, card):
        super().__init__(name=card.name)


class BuyPotionAction(ChooseAction):
    """An action to buy a potion in a shop. Currently, buys the first available potion of the same name."""

    def __init__(self, potion):
        super().__init__(name=potion.name)

    def execute(self, coordinator):
        if coordinator.game.are_potions_full():
            raise Exception("Cannot buy potion because potion slots are full.")
        super().execute(coordinator)


class BuyRelicAction(ChooseAction):
    """An action to buy a relic in a shop"""

    def __init__(self, relic):
        super().__init__(name=relic.name)


class BuyPurgeAction(Action):
    """An action to buy a card removal at a shop"""

    def __init__(self, card_to_purge=None):
        super().__init__()
        self.card_to_purge = card_to_purge

    def execute(self, coordinator):
        if coordinator.last_game_state.screen_type != ScreenType.SHOP_SCREEN:
            raise Exception("BuyPurgeAction is only available on a Shop Screen")
        coordinator.add_action_to_queue(ChooseAction(name="purge"))
        if self.card_to_purge is not None:
            coordinator.add_action_to_queue(CardSelectAction([self.card_to_purge]))


class EventOptionAction(ChooseAction):
    """An action to choose an event option"""

    def __init__(self, option):
        super().__init__(choice_index=option.choice_index)


class RestAction(ChooseAction):
    """An action to choose a rest option at a rest site"""

    def __init__(self, rest_option):
        super().__init__(name=rest_option.name)


class CardRewardAction(ChooseAction):
    """An action to choose a card reward, or use Singing Bowl"""

    def __init__(self, card=None, bowl=False):
        if bowl:
            name = "bowl"
        elif card is not None:
            name = card.name
        else:
            raise Exception("Must provide a card for CardRewardAction if not choosing the Singing Bowl")
        super().__init__(name=name)


class CombatRewardAction(ChooseAction):
    """An action to choose a combat reward"""

    def __init__(self, combat_reward):
        self.combat_reward = combat_reward
        super().__init__()

    def execute(self, coordinator):
        if coordinator.last_game_state.screen_type != ScreenType.COMBAT_REWARD:
            raise Exception("CombatRewardAction is only available on a Combat Reward Screen.")
        reward_list = coordinator.last_game_state.screen.rewards
        if self.combat_reward not in reward_list:
            raise Exception("Reward is not available: {}".format(self.combat_reward.reward_type))
        if self.combat_reward.reward_type == RewardType.POTION and coordinator.last_game_state.are_potions_full():
            raise Exception("Cannot choose potion reward with full potion slots.")
        self.choice_index = reward_list.index(self.combat_reward)
        super().execute(coordinator)


class BossRewardAction(ChooseAction):
    """An action to choose a boss relic"""

    def __init__(self, relic):
        super().__init__(name=relic.name)


class OptionalCardSelectConfirmAction(Action):
    """An action to click confirm on a hand or grid select screen, only if available"""

    def __init__(self):
        super().__init__()

    def execute(self, coordinator):
        screen_type = coordinator.last_game_state.screen_type
        if screen_type == ScreenType.HAND_SELECT:
            coordinator.add_action_to_queue(ProceedAction())
        elif screen_type == ScreenType.GRID and coordinator.last_game_state.screen.confirm_up:
            coordinator.add_action_to_queue(ProceedAction())
        else:
            coordinator.add_action_to_queue(StateAction())


class CardSelectAction(Action):
    """An action to choose the selected cards on a hand or grid select screen"""

    def __init__(self, cards):
        self.cards = cards
        super().__init__()

    def execute(self, coordinator):
        screen_type = coordinator.last_game_state.screen_type
        screen = coordinator.last_game_state.screen
        if screen_type not in [ScreenType.HAND_SELECT, ScreenType.GRID]:
            raise Exception("CardSelectAction is only available on a Hand Select or Grid Select Screen.")
        num_selected_cards = len(screen.selected_cards)
        num_remaining_cards = screen.num_cards - num_selected_cards
        available_cards = screen.cards
        if screen_type == ScreenType.GRID and not screen.any_number and len(self.cards) != num_remaining_cards:
            raise Exception("Wrong number of cards selected for CardSelectAction (provided {}, need {})".format(len(self.cards), num_remaining_cards))
        elif len(self.cards) > num_remaining_cards:
            raise Exception("Too many cards selected for CardSelectAction (provided {}, max {})".format(len(self.cards), num_remaining_cards))
        chosen_indices = []
        for card in self.cards:
            if card not in available_cards:
                raise Exception("Card {} is not available in the Hand Select Screen".format(card.name))
            else:
                chosen_indices.append(available_cards.index(card))
        chosen_indices.sort(reverse=True)
        for index in chosen_indices:
            coordinator.add_action_to_queue(ChooseAction(choice_index=index))
        coordinator.add_action_to_queue(OptionalCardSelectConfirmAction())


class ChooseMapNodeAction(ChooseAction):
    """An action to choose a map node, other than the boss"""

    def __init__(self, node):
        self.node = node
        super().__init__()

    def execute(self, coordinator):
        if coordinator.last_game_state.screen_type != ScreenType.MAP:
            raise Exception("MapChoiceAction is only available on a Map Screen")
        next_nodes = coordinator.last_game_state.screen.next_nodes
        if self.node not in next_nodes:
            raise Exception("Node {} is not available to choose.".format(self.node))
        self.choice_index = next_nodes.index(self.node)
        super().execute(coordinator)


class ChooseMapBossAction(ChooseAction):
    """An action to choose the boss map node"""

    def __init__(self):
        super().__init__()

    def execute(self, coordinator):
        if coordinator.last_game_state.screen_type != ScreenType.MAP:
            raise Exception("ChooseMapBossAction is only available on a Map Screen")
        if not coordinator.last_game_state.screen.boss_available:
            raise Exception("The boss is not available to choose.")
        self.name = "boss"
        super().execute(coordinator)


class StartGameAction(Action):
    """An action to start a new game, if not already in a game"""

    def __init__(self, player_class, ascension_level=0, seed=None):
        super().__init__("start")
        self.player_class = player_class
        self.ascension_level = ascension_level
        self.seed = seed

    def execute(self, coordinator):
        arguments = [self.command, self.player_class.name, str(self.ascension_level)]
        if self.seed is not None:
            arguments.append(str(self.seed))
        coordinator.send_message(" ".join(arguments))


class StateAction(Action):
    """An action to use the CommunicationMod 'State' command"""

    def __init__(self, requires_game_ready=False):
        super().__init__(command="state", requires_game_ready=False)

