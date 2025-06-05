import json
import pyautogui
from pathlib import Path
import time

from .Monsters import Monsters
from .Roster import Party
from .AttackSkills import AttackSkills
from .Controls import Controller, attack_target, swap_hero, heal_target

pyautogui.FAILSAFE = True
Debug, attack_completed, Initialized = False, False, False
SelectedHeroRank, RoundNumber = 1, 1
NumberOfEnemies, RetryCount = 0, 0
TurnTracker = {}
PartyOrder, UpdatedPartyOrder = [], []
LastHero, LastMoved, LastRoundMoved, NextHeroToMove = None, None, None, None

BackLineClasses = ['jester', 'vestal', 'plague_doctor', 'arbalest']
FrontLineClasses = ['crusader', 'hellion', 'leper', 'flagellant']


def get_selected_hero_rank():
    global SelectedHeroRank
    return SelectedHeroRank


# future - use items from inventory during battle
def battle(inventory, battle_speed, sfr, debug):
    global Debug, SelectedHeroRank, TurnTracker, LastHero, RoundNumber, Initialized, \
        LastMoved, NumberOfEnemies, LastRoundMoved, RetryCount, PartyOrder, UpdatedPartyOrder, NextHeroToMove
    Debug = debug
    c = Controller(debug)
    print('Starting battle algorithm!')
    c.write(c.b, 2)  # important, this makes sure the wrong menu isn't selected

    while True:
        try:
            # wait at least this long before reading save file to try and avoid save corruption
            time.sleep(.7)  # previous values used 0.4 worked well
            sfr.decrypt_save_info('persist.raid.json')
            f = open(Path(f'{sfr.save_editor_path()}/persist.raid.json'), encoding="utf-8")
            raid_info = json.load(f)['base_root']
            f.close()
        except FileNotFoundError:
            if LastHero is not None:
                SelectedHeroRank = Party.get_rank(LastHero, UpdatedPartyOrder)
            print(f'Selected hero rank: {SelectedHeroRank}')
            TurnTracker = {}
            RoundNumber = 1
            LastHero, LastMoved, NumberOfEnemies, LastRoundMoved, NextHeroToMove = None, None, None, None, None
            break
        if not raid_info['inbattle']:
            if LastHero is not None:
                SelectedHeroRank = Party.get_rank(LastHero, UpdatedPartyOrder)
            print(f'Selected hero rank: {SelectedHeroRank}')
            TurnTracker = {}
            RoundNumber = 1
            LastHero, LastMoved, NumberOfEnemies, LastRoundMoved, NextHeroToMove = None, None, None, None, None
            break

        sfr.decrypt_save_info('persist.roster.json')
        f = open(Path(f'{sfr.save_editor_path()}/persist.roster.json'), encoding="utf-8")
        roster_info = json.load(f)['base_root']
        f.close()

        # sort combatants in order of who has highest initiative and track which enemies have moved this round
        turn_order = []
        save_file_round_number = raid_info['battle']['round']
        print(f"save file round number {save_file_round_number}")
        round_number = RoundNumber if RoundNumber > save_file_round_number else save_file_round_number
        current_turn = str(raid_info['battle']['currentturn'])
        initiative = raid_info['battle']['initiative']
        current_turn_id = initiative['heroes'][current_turn]['roster_guid'] \
            if current_turn in initiative['heroes'] else 'None'
        print(f'round number {round_number}')
        print(f'current turn in save file: {current_turn}, current_turn_id: {current_turn_id} (not always accurate)')

        # save file not always reliable, iterate through allies and enemies to get as much info as possible,
        #  and avoid using current turn from save file unless starting in the middle and absolutely necessary
        heroes_moved, enemies_moved = 0, 0
        enemy_stunned_last_turn, monsters_surprised, party_surprised = False, False, False
        hero_to_move, last_moved_initiative = None, None
        for each_hero in initiative['heroes'].values():
            hero_id = str(each_hero['roster_guid'])
            hero_data = roster_info['heroes'][hero_id]['hero_file_data']['raw_data']['base_root']
            turns_performed = hero_data['actor']['performing_turn']
            buff_group = hero_data['actor']['buff_group']
            # still might not work in all cases when have StunRecoveryBuff already before combat even starts
            stun_recovery_buff = 0 if round_number == 1 \
                and not any('monster_id' in turn and turn['already_moved'] for turn in turn_order) \
                else sum(buff['id'] == 'STUNRECOVERYBUFF' for buff in buff_group.values())
            if round_number <= turns_performed + stun_recovery_buff:
                heroes_moved += 1
                if last_moved_initiative is None or each_hero['initiative'] < last_moved_initiative:
                    last_moved_initiative = each_hero['initiative']
            else:
                hero_to_move = hero_id
        # if need to use current turn from save file, attempt to adjust for any obvious discrepancy
        if round_number == 1:
            monsters_surprised = raid_info['battle']['monsters_surprised']
        if not Initialized:
            if len(initiative['heroes']) == 0:
                continue
            elif len(initiative['heroes']) == heroes_moved:
                hero_initiative = [[i, hero] for i, hero in initiative['heroes'].items()]
                first_hero = max(hero_initiative, key=lambda k: k[1]['initiative'])
                current_turn = first_hero[0]
            elif len(initiative['heroes']) - 1 == heroes_moved:
                current_turn = next(i for i, hero in initiative['heroes'].items()
                                    if hero_to_move == str(hero['roster_guid']))
            print(f'adjusted current turn {current_turn}')

        for each_monster in initiative['monsters'].values():
            monster_id = each_monster['battle_guid']
            monster_data = next(enemy['data'] for enemy in raid_info['battle']['enemies'].values()
                                if enemy['data']['battle_guid'] == monster_id)
            turns_performed = monster_data['actor']['performing_turn']
            buff_group = monster_data['actor']['buff_group']
            stun_recovery_buff = sum(buff['id'] == 'STUNRECOVERYBUFF' for buff in buff_group.values())
            if round_number <= turns_performed + stun_recovery_buff:
                enemies_moved += 1
                if last_moved_initiative is None or each_monster['initiative'] < last_moved_initiative:
                    last_moved_initiative = each_monster['initiative']

        # determine which enemies have already moved
        for each_monster in initiative['monsters'].values():
            monster_id = each_monster['battle_guid']
            monster_initiative = each_monster['initiative']
            monster_data = next(enemy['data'] for enemy in raid_info['battle']['enemies'].values()
                                if enemy['data']['battle_guid'] == monster_id)
            turns_performed = monster_data['actor']['performing_turn']
            buff_group = monster_data['actor']['buff_group']
            stun_recovery_buff = sum(buff['id'] == 'STUNRECOVERYBUFF' for buff in buff_group.values())
            stunned = False if monster_data['actor']['stunned'] == 0 else True
            if monster_id not in TurnTracker:
                if heroes_moved == 0 and enemies_moved == 0:  # start of combat, nobody has moved yet
                    already_moved = False
                elif not Initialized and current_turn in initiative['heroes'] \
                        and each_monster['initiative'] > initiative['heroes'][current_turn]['initiative']:
                    already_moved = True
                elif current_turn not in initiative['heroes']:  # assume this means that all enemies have moved
                    already_moved = True
                    if last_moved_initiative is None or each_monster['initiative'] < last_moved_initiative:
                        last_moved_initiative = each_monster['initiative']
                elif round_number <= turns_performed + stun_recovery_buff \
                        or (last_moved_initiative is not None and monster_initiative > last_moved_initiative):
                    already_moved = True
                else:
                    already_moved = False
                stun_count = round_number - turns_performed if already_moved else round_number - turns_performed - 1
                TurnTracker.update({monster_id: {'stun_count': stun_count, 'buff_count': stun_recovery_buff,
                                                 'stunned': stunned}})
            else:
                if stun_recovery_buff != TurnTracker[monster_id]['buff_count']:
                    if stun_recovery_buff > TurnTracker[monster_id]['buff_count']:
                        TurnTracker[monster_id]['stun_count'] += 1
                    TurnTracker[monster_id]['buff_count'] = stun_recovery_buff
                stun_count = TurnTracker[monster_id]['stun_count']
                already_moved = True if round_number == turns_performed + stun_count else False
                if stunned and not TurnTracker[monster_id]['stunned']:
                    enemy_stunned_last_turn = True
                    TurnTracker[monster_id]['stunned'] = True
                elif not stunned:
                    TurnTracker[monster_id]['stunned'] = False
            print(f'monster_id: {monster_id}, initiative: {monster_initiative}, turns_moved: {turns_performed}, '
                  f'stunned: {stunned}, stun_count: {stun_count}, stun_recovery_buff: {stun_recovery_buff}, '
                  f'already_moved: {already_moved}')
            turn_order.append({'monster_id': monster_id, 'initiative': monster_initiative,
                               'already_moved': already_moved})

        # determine which heroes have already moved
        for index, each_hero in initiative['heroes'].items():
            hero_id = str(each_hero['roster_guid'])
            hero_initiative = each_hero['initiative']
            hero_data = roster_info['heroes'][hero_id]['hero_file_data']['raw_data']['base_root']
            turns_performed = hero_data['actor']['performing_turn']
            buff_group = hero_data['actor']['buff_group']
            # still might not work in all cases when have StunRecoveryBuff already before combat even starts
            stun_recovery_buff = 0 if round_number == 1 \
                and not any('monster_id' in turn and turn['already_moved'] for turn in turn_order) \
                else sum(buff['id'] == 'STUNRECOVERYBUFF' for buff in buff_group.values())
            stunned = False if hero_data['actor']['stunned'] == 0 else True
            enemies_killed = hero_data['enemies_killed']
            if hero_id not in TurnTracker:
                already_moved = False
                if round_number <= turns_performed + stun_recovery_buff \
                        or (last_moved_initiative is not None and hero_initiative > last_moved_initiative):
                    already_moved = True
                stun_count = round_number - turns_performed if already_moved else round_number - turns_performed - 1
                TurnTracker.update({hero_id: {'stun_count': stun_count, 'buff_count': stun_recovery_buff,
                                              'enemies_killed': enemies_killed}})
            else:
                if stun_recovery_buff != TurnTracker[hero_id]['buff_count']:
                    if stun_recovery_buff > TurnTracker[hero_id]['buff_count']:
                        TurnTracker[hero_id]['stun_count'] += 1
                    TurnTracker[hero_id]['buff_count'] = stun_recovery_buff
                if round_number < turns_performed + TurnTracker[hero_id]['stun_count']:
                    TurnTracker[hero_id]['stun_count'] = round_number - turns_performed
                stun_count = TurnTracker[hero_id]['stun_count']
                already_moved = True if round_number == turns_performed + stun_count else False
            print(f'hero_id: {hero_id}, initiative: {hero_initiative}, turns_moved: {turns_performed}, '
                  f'stunned: {stunned}, stun_count: {stun_count}, stun_recovery_buff: {stun_recovery_buff}, '
                  f'already_moved: {already_moved}, enemies_killed: {enemies_killed}')
            turn_order.append({'hero_id': hero_id, 'initiative': hero_initiative, 'already_moved': already_moved})

        # check if it is our turn to move
        turn_order.sort(key=lambda k: k['initiative'], reverse=True)
        our_turn_to_move = False
        enemy_to_move = None
        Initialized = True
        PartyOrder = UpdatedPartyOrder if UpdatedPartyOrder is not None and PartyOrder is not None and \
            raid_info['party']['heroes'] == PartyOrder else raid_info['party']['heroes']
        UpdatedPartyOrder = PartyOrder.copy()
        party_info = Party(roster_info, PartyOrder, turn_order)
        party = party_info.heroes

        # check if monster surprised (enemies may also all have negative initiatives when surprised)
        if round_number == 1 and monsters_surprised:
            party_turns = [turn for turn in turn_order if 'hero_id' in turn]
            monster_turns = [turn for turn in turn_order if 'monster_id' in turn]
            turn_order = party_turns
            turn_order.extend(monster_turns)

        for i, turn in enumerate(turn_order):
            next_turn_index = next((j for j, next_turn in enumerate(turn_order) if j > i
                                    and not turn_order[j]['already_moved'] and 'hero_id' in turn_order[j]), None)
            if 'hero_id' in turn_order[i] and not turn_order[i]['already_moved']:
                hero_to_move = turn_order[i]['hero_id']
                our_turn_to_move = True
                # if there is a tie for the next initiative score and it's another hero
                if next_turn_index is not None \
                        and turn_order[i]['initiative'] == turn_order[next_turn_index]['initiative']:
                    # i_hero = next(hero for hero in party if hero.roster_index == turn_order[i]['hero_id'])
                    # next_hero = next(hero for hero in party
                    #                  if hero.roster_index == turn_order[next_turn_index]['hero_id'])
                    # # check which hero has the higher total speed
                    # if next_hero.speed > i_hero.speed:
                    #     continue
                    print('Speed tie between 2 heroes. Need to move both in a row in case save file '
                          'doesnt update after the first')
                    NextHeroToMove = turn_order[next_turn_index]['hero_id']

                    # if current_turn doesn't match the next hero in turn_order (i_hero), give it to the first hero
                    #   in PartyOrder, otherwise let it fall through and use the current_turn hero
                    #   (if doesn't work, maybe tie goes to specific hero classes or order in turn_order)
                    if current_turn in initiative['heroes'] \
                            and int(turn_order[i]['hero_id']) != initiative['heroes'][current_turn]['roster_guid']:
                        next_in_party_order = next(n for n in PartyOrder if n == int(turn_order[i]['hero_id'])
                                                   or n == int(turn_order[next_turn_index]['hero_id']))
                        if next_in_party_order != int(turn_order[i]['hero_id']):
                            hero_to_move = turn_order[next_turn_index]['hero_id']
                            NextHeroToMove = turn_order[i]['hero_id']
                break
            elif 'monster_id' in turn_order[i] and not turn_order[i]['already_moved']:
                # if there is a tie between an enemy and a hero for the next initiative score, then assume that the hero
                # will be next (future - determine if this is right, throw an exception and then go back in and debug)
                if next_turn_index is not None \
                        and turn_order[i]['initiative'] == turn_order[next_turn_index]['initiative']:
                    continue
                enemy_to_move = turn_order[i]['monster_id']
                break

        if not our_turn_to_move and enemy_to_move is None and len(turn_order) >= 5:
            if RetryCount >= 5:
                print('attempt to account for save file discrepancy where round number does not increment')
                RoundNumber = round_number + 1
                RetryCount = 0
            elif RetryCount < 5:
                RetryCount += 1
                time.sleep(1)
        elif not our_turn_to_move and enemy_to_move is not None:
            if RetryCount >= 10:
                print('attempt to account for game bug where its the enemies turn but enemy does not move')
                our_turn_to_move = True
                RetryCount = 0
                hero_to_move = next((turn['hero_id'] for turn in turn_order
                                    if not turn['already_moved'] and 'hero_id' in turn), None)
                if hero_to_move is None:
                    print('No hero available to move, resetting turn order')
                    for turn in turn_order:
                        if 'already_moved' in turn:
                            turn['already_moved'] = False
                    hero_to_move = next(turn['hero_id'] for turn in turn_order if 'hero_id' in turn)
            elif RetryCount < 10:
                if LastMoved != enemy_to_move:
                    LastMoved = enemy_to_move
                    RetryCount = 0
                elif LastMoved == enemy_to_move:
                    RetryCount += 1
        if our_turn_to_move:
            RetryCount = 0
            hero_data = roster_info['heroes'][hero_to_move]['hero_file_data']['raw_data']['base_root']
            hero_enemies_killed = hero_data['enemies_killed']
            enemy_killed_last_turn = False if LastMoved in initiative['monsters'] \
                or TurnTracker[hero_to_move]['enemies_killed'] == hero_enemies_killed \
                or len(initiative['monsters']) >= NumberOfEnemies else True
            if LastHero != hero_to_move or round_number != LastRoundMoved:
                # use torch if less than 50% and not shambler (future - or 75% for sun trinkets)
                # torchlight = 0 if raid_info['torchlight'] == 0 else (raid_info['torchlight'] / 131072) - 8448
                # if torchlight < 50:
                #     pyautogui.write(c.torch)  # need to use 'write' instead of 'press' for torch
                # manage_inventory_empty_torch_slots(inventory, torches, torches_used)
                for i in range(2 if NextHeroToMove is not None else 1):
                    hero = next((hero for hero in party if hero.roster_index == hero_to_move), None)
                    TurnTracker[hero_to_move]['enemies_killed'] = hero_enemies_killed
                    # make sure enough time has passed since the save file was read for animations to complete
                    time.sleep(2.0 if battle_speed == 'fast' else 3.0)  # also prevent same character from moving twice

                    # check again to make sure we're still in battle before doing next move
                    sfr.decrypt_save_info('persist.raid.json')
                    f = open(Path(f'{sfr.save_editor_path()}/persist.raid.json'), encoding="utf-8")
                    raid_info = json.load(f)['base_root']
                    f.close()
                    if not raid_info['inbattle'] or hero.stunned:
                        NextHeroToMove = None
                        break
                    
                    difficulty = raid_info['raid_instance']['difficulty']
                    enemy_formation = get_enemy_formation(raid_info, turn_order, difficulty)
                    party.sort(key=lambda k: k.rank)

                    # LastHero = hero_to_move
                    # LastMoved = hero_to_move
                    # LastRoundMoved = round_number
                    # NumberOfEnemies = len(initiative['monsters'])

                    return party, hero, raid_info, enemy_formation
                    # take_battle_action(raid_info, party, hero, turn_order)
                    # time.sleep(.5)
                    # LastHero = hero_to_move
                    # LastMoved = hero_to_move
                    # LastRoundMoved = round_number
                    # NumberOfEnemies = len(initiative['monsters'])
                    # if NextHeroToMove is not None:
                    #     time.sleep(2.5)
                    #     hero_to_move = NextHeroToMove
                    #     NextHeroToMove = None

            # attempt to account for save file discrepancy where turns performed is not updated
            elif LastHero == hero_to_move and LastRoundMoved == round_number \
                    and (enemy_stunned_last_turn or enemy_killed_last_turn):
                print(f'enemy_stunned_last_turn: {enemy_stunned_last_turn}, '
                      f'enemy_killed_last_turn: {enemy_killed_last_turn}')
                print('Save file turns performed did not update. Attempting to make correction!')
                TurnTracker[hero_to_move]['stun_count'] += 1  # already moved = turns_performed + stun_count == round_number
                RetryCount = 0
            elif LastHero == hero_to_move and round_number == 1 and not any(hero.already_moved for hero in party):
                if RetryCount >= 5:
                    print('Save file turns performed did not update. Attempting to make correction!')
                    TurnTracker[hero_to_move]['stun_count'] += 1  # already moved = turns_performed + stun_count == round_number
                    RetryCount = 0
                elif RetryCount < 5:
                    RetryCount += 1
                    time.sleep(1)
            elif LastHero == hero_to_move and LastRoundMoved == round_number:
                if RetryCount >= 15:  # only do as last resort
                    print('Save file turns performed did not update. Attempting to make correction!')
                    TurnTracker[hero_to_move]['stun_count'] += 1  # already moved = turns_performed + stun_count == round_number
                    RetryCount = 0
                elif RetryCount < 15:
                    RetryCount += 1
            else:
                RetryCount = 0


def take_battle_action(raid_info, party, hero, turn_order):
    print('Taking battle action!')
    difficulty = raid_info['raid_instance']['difficulty']
    enemy_formation = get_enemy_formation(raid_info, turn_order, difficulty)

    hero_class = hero.heroClass
    print(f'hero class: {hero_class}, rank {hero.rank}, hero_id: {hero.roster_index}')
    party.sort(key=lambda k: k.rank)  # sort by rank

    if hero_class == 'highwayman':
        highwayman_action(party, hero, raid_info, enemy_formation)
    elif hero_class == 'crusader':
        crusader_action(party, hero, raid_info, enemy_formation)
    elif hero_class == 'plague_doctor':
        plague_doctor_action(party, hero, raid_info, enemy_formation)
    elif hero_class == 'vestal':
        vestal_action(party, hero, raid_info, enemy_formation)
    elif hero_class == 'hellion':
        hellion_action(party, hero, raid_info, enemy_formation)
    elif hero_class == 'man_at_arms':
        man_at_arms_action(party, hero, raid_info, enemy_formation)
    elif hero_class == 'shieldbreaker':
        shieldbreaker_action(party, hero, raid_info, enemy_formation)
    elif hero_class == 'jester':
        jester_action(party, hero, raid_info, enemy_formation)
    elif hero_class == 'occultist':
        occultist_action(party, hero, raid_info, enemy_formation)
    elif hero_class == 'houndmaster':
        houndmaster_action(party, hero, raid_info, enemy_formation)


def occultist_attack_helper(hero, list_of_enemies, stun_chance, kill_stunned_enemy, cant_kill_enemy_ok=False):
    attack = None
    if 'bloodlet' in hero.skills and hero.rank in AttackSkills['bloodlet'][0] \
            and any(enemy.lowHp and ((not enemy.stunned or (enemy.stunned and kill_stunned_enemy))
                    and any(rank in AttackSkills['bloodlet'][1] for rank in enemy.rank))
                    for enemy in list_of_enemies):
        attack = 'bloodlet'
    elif 'hands_from_abyss' in hero.skills and hero.rank in AttackSkills['hands_from_abyss'][0] \
            and any((1 in enemy.rank or 2 in enemy.rank or 3 in enemy.rank)
                    and stun_chance - enemy.stunResist >= 50 and not enemy.stunned for enemy in list_of_enemies):
        attack = 'hands_from_abyss'
    elif 'daemons_pull' in hero.skills and hero.rank in AttackSkills['daemons_pull'][0] \
            and any(enemy.name == 'Bone Arbalist' and (3 in enemy.rank or 4 in enemy.rank)
                    for enemy in list_of_enemies):
        attack = 'daemons_pull'
    elif 'bloodlet' in hero.skills and cant_kill_enemy_ok and hero.rank in AttackSkills['bloodlet'][0] \
            and any(any(rank in AttackSkills['bloodlet'][1] for rank in enemy.rank)
                    for enemy in list_of_enemies):
        attack = 'bloodlet'
    return attack, list_of_enemies


def occultist_action(party_sorted_by_rank, hero, raid_info, enemy_formation):
    """[ Ideal skill load-out: sacrificial_stab, wyrd_reconstruction, any 2 - hands_from_the_abyss or daemons_pull
            or weakening_curse or abyssal_artillery or vulnerability_hex ]"""
    # Note: sacrificial stab = bloodlet
    global UpdatedPartyOrder
    party = party_sorted_by_rank
    list_of_attacks = ['bloodlet', 'abyssal_artillery', 'hands_from_abyss', 'daemons_pull']
    stall_count = raid_info['battle']['round_stall_count']
    stall_accelerated = raid_info['battle']['previous_stall_accelerated']
    stall = False if stall_count >= 2 or stall_accelerated else True
    attack, stun_chance = None, None
    swap_distance = -1

    enemies_not_dead_already = [enemy for enemy in enemy_formation if not enemy.alreadyGoingToDie]
    enemies_not_moved = [enemy for enemy in enemies_not_dead_already if not enemy.alreadyMoved]
    high_threat_enemies = [enemy for enemy in enemies_not_dead_already if enemy.threat >= 4]
    very_high_threat_enemies = [enemy for enemy in high_threat_enemies if enemy.threat >= 7]
    very_high_threat_not_moved = [enemy for enemy in very_high_threat_enemies if not enemy.alreadyMoved]
    high_threat_not_moved = [enemy for enemy in high_threat_enemies if not enemy.alreadyMoved]
    skeleton_archers = [enemy for enemy in enemies_not_dead_already if enemy.name == 'Bone Arbalist'
                        and (3 in enemy.rank or 4 in enemy.rank)]
    skeleton_archers_not_moved = [enemy for enemy in skeleton_archers if not enemy.alreadyMoved]
    potential_targets = enemy_formation
    enemy = enemies_not_dead_already[0] if len(enemies_not_dead_already) > 0 else None

    if 'hands_from_abyss' in hero.skills:
        stun_level = hero.skills['hands_from_abyss']
        stun_chance = AttackSkills['hands_from_abyss'][2][stun_level]

    # heal if on deaths door or going to be on deaths door
    target = next((ally for ally in party if ally.effectiveHp == 0 or ally.currentHp == 0), None)
    if target is not None and 'wyrd_reconstruction' in hero.skills \
            and hero.rank in AttackSkills['wyrd_reconstruction'][0]:
        attack = 'wyrd_reconstruction'
    # stall if only one weak enemy left and need to heal or stress heal
    if attack is None and (len(enemies_not_dead_already) == 0 or (len(enemies_not_dead_already) == 1 and stall)) \
            and ((any(ally.percentHp < 80 for ally in party) and any(ally.healer for ally in party))
                 or (any(ally.stress > 0 for ally in party) and any(ally.stressHealer for ally in party))):
        if 'hands_from_abyss' in hero.skills and len(enemies_not_dead_already) == 1 \
                and hero.rank in AttackSkills['hands_from_abyss'][0] \
                and any(rank in AttackSkills['hands_from_abyss'][1] for rank in enemy.rank) \
                and not enemy.stunned and stun_chance - enemy.stunResist >= 50 \
                and (not enemy.canBeKilledIn1Hit or enemy.threat >= 4):
            attack = 'hands_from_abyss'
        elif (enemy.stunned or enemy.threat < 4) or len(enemies_not_dead_already) == 0:
            if 'wyrd_reconstruction' and any(ally.percentHp < 100 and ally.currentHp != ally.maxHp for ally in party) \
                    and hero.rank in AttackSkills['wyrd_reconstruction'][0]:
                attack = 'wyrd_reconstruction'
            # weakening curse
            elif 'weakening_curse' in hero.skills:
                attack = 'weakening_curse'
            # vulnerability_hex
            elif 'vulnerability_hex' in hero.skills:
                attack = 'vulnerability_hex'
            # swap
            else:
                attack = 'swap'
                swap_distance = -1 \
                    if ((hero.rank == 2 or hero.rank == 3) and party[hero.rank].heroClass in FrontLineClasses) \
                    or (hero.rank == 3 and party[1].heroClass in FrontLineClasses) or hero.rank == 1 else 1

    # heal
    if attack is None and any(ally.percentHp < 20 and ally.currentHp != ally.maxHp for ally in party):
        attack = 'wyrd_reconstruction'

    # kill an enemy or stun very high threat enemy
    if attack is None:
        attack, potential_targets = occultist_attack_helper(hero, very_high_threat_not_moved, stun_chance,
                                                            kill_stunned_enemy=False)
    if attack is None:
        attack, potential_targets = occultist_attack_helper(hero, very_high_threat_enemies, stun_chance,
                                                            kill_stunned_enemy=True, cant_kill_enemy_ok=True)
    # kill an enemy or stun high threat enemy
    if attack is None:
        attack, potential_targets = occultist_attack_helper(hero, high_threat_not_moved, stun_chance,
                                                            kill_stunned_enemy=False)

    # heal
    if attack is None and any(ally.percentHp < 40 and ally.currentHp != ally.maxHp for ally in party):
        attack = 'wyrd_reconstruction'

    # stun or pull skeleton archer
    if attack is None:
        attack, potential_targets = occultist_attack_helper(hero, skeleton_archers_not_moved, stun_chance,
                                                            kill_stunned_enemy=False)
    if attack is None:
        attack, potential_targets = occultist_attack_helper(hero, skeleton_archers, stun_chance,
                                                            kill_stunned_enemy=False)
    # swap if need to fix position
    attack = 'swap' if attack is None and hero.rank == 2 and 'hands_from_abyss' not in hero.skills \
             and (party[2].heroClass == 'hellion' or party[2].heroClass == 'leper'
                  or party[2].heroClass == 'flagellant') else attack
    if attack is None and (hero.rank == 3 or hero.rank == 4) and party[hero.rank-2].heroClass in BackLineClasses:
        attack = 'swap'
        swap_distance = 1

    # attack high threat enemy
    if attack is None:
        attack, potential_targets = occultist_attack_helper(hero, high_threat_enemies, stun_chance,
                                                            kill_stunned_enemy=True, cant_kill_enemy_ok=True)
    # kill an enemy or stun enemy
    if attack is None:
        attack, potential_targets = occultist_attack_helper(hero, enemies_not_moved, stun_chance,
                                                            kill_stunned_enemy=False)
    # heal
    if attack is None and any(ally.percentHp < 85 and ally.currentHp != ally.maxHp for ally in party):
        attack = 'wyrd_reconstruction'

    if attack is None:
        attack, potential_targets = occultist_attack_helper(hero, enemies_not_dead_already, stun_chance,
                                                            kill_stunned_enemy=True, cant_kill_enemy_ok=True)

    if attack == 'swap':
        swap_hero(hero, swap_distance, UpdatedPartyOrder, debug=Debug)
    elif attack == 'hands_from_abyss':
        find_target_and_stun(hero, potential_targets, attack, stun_chance, UpdatedPartyOrder, target)
    elif attack == attack == 'wyrd_reconstruction':
        if target is None:
            party.sort(key=lambda k: k.percentHp)
            target = party[0]
        heal_target(hero, target, attack=attack, debug=Debug)
    else:
        # Find target and attack enemy
        if attack is not None:
            list_of_attacks.insert(0, attack)
        find_target_and_attack(raid_info, potential_targets, hero, party, list_of_attacks, UpdatedPartyOrder)


def jester_attack_helper(hero, party, list_of_enemies, kill_stunned_enemy, cant_kill_enemy_ok=False):
    attack = None
    if 'slice_off' in hero.skills and hero.rank in AttackSkills['slice_off'][0] \
            and any(enemy.lowHp and ((not enemy.stunned or (enemy.stunned and kill_stunned_enemy))
                                     and any(rank in AttackSkills['slice_off'][1] for rank in enemy.rank))
                    for enemy in list_of_enemies):
        attack = 'slice_off'
    elif 'dirk_stab' in hero.skills and hero.rank == 4 and party[2].heroClass in BackLineClasses \
            and any(enemy.lowHp and ((not enemy.stunned or (enemy.stunned and kill_stunned_enemy))
                                     and any(rank in AttackSkills['dirk_stab'][1] for rank in enemy.rank))
                    for enemy in list_of_enemies):
        attack = 'dirk_stab'
    elif 'harvest' in hero.skills and hero.rank in AttackSkills['harvest'][0] \
            and any(enemy.lowHp and ((not enemy.stunned or (enemy.stunned and kill_stunned_enemy))
                                     and any(rank in AttackSkills['harvest'][1] for rank in enemy.rank))
                    for enemy in list_of_enemies):
        attack = 'harvest'
    elif 'slice_off' in hero.skills and hero.rank in AttackSkills['slice_off'][0] and cant_kill_enemy_ok \
            and any(any(rank in AttackSkills['slice_off'][1] for rank in enemy.rank) for enemy in list_of_enemies):
        attack = 'slice_off'
    elif 'harvest' in hero.skills and hero.rank in AttackSkills['harvest'][0] and cant_kill_enemy_ok \
            and any(any(rank in AttackSkills['harvest'][1] for rank in enemy.rank) for enemy in list_of_enemies):
        attack = 'harvest'
    return attack, list_of_enemies


def jester_action(party_sorted_by_rank, hero, raid_info, enemy_formation):
    """[ Ideal skill load-out: dirk_stab, slice_off, inspiring_tune, battle_ballad ]"""
    global UpdatedPartyOrder
    party = party_sorted_by_rank
    list_of_attacks = ['slice_off', 'harvest']
    stall_count = raid_info['battle']['round_stall_count']
    stall_accelerated = raid_info['battle']['previous_stall_accelerated']
    stall = False if stall_count >= 2 or stall_accelerated else True
    attack = None
    swap_distance = -1

    enemies_not_dead_already = [enemy for enemy in enemy_formation if not enemy.alreadyGoingToDie]
    enemies_not_moved = [enemy for enemy in enemies_not_dead_already if not enemy.alreadyMoved]
    high_threat_enemies = [enemy for enemy in enemies_not_dead_already if enemy.threat >= 4]
    very_high_threat_enemies = [enemy for enemy in high_threat_enemies if enemy.threat >= 7]
    very_high_threat_not_moved = [enemy for enemy in very_high_threat_enemies if not enemy.alreadyMoved]
    high_threat_not_moved = [enemy for enemy in high_threat_enemies if not enemy.alreadyMoved]
    potential_targets = enemy_formation

    # ally almost at 100 or 200 stress
    if 'inspiring_tune' in hero.skills and (hero.rank == 3 or hero.rank == 4) \
            and any(86 < ally.stress < 100 or 180 < ally.stress for ally in party):
        attack = 'inspiring_tune'
    # stall if only one weak enemy left and need to heal or stress heal
    if attack is None and (len(enemies_not_dead_already) == 0 or (len(enemies_not_dead_already) == 1 and stall)) \
            and ((any(ally.percentHp < 80 for ally in party) and any(ally.healer for ally in party))
                 or (any(ally.stress > 0 for ally in party) and any(ally.stressHealer for ally in party))):
        if 'inspiring_tune' in hero.skills and (hero.rank == 3 or hero.rank == 4) \
                and any(ally.stress > 0 for ally in party):
            attack = 'inspiring_tune'
        elif 'battle_ballad' in hero.skills and (hero.rank == 4 or hero.rank == 3):
            attack = 'battle_ballad'
        else:
            attack = 'swap'
            swap_distance = 1 if hero.rank == 4 else -1

    # kill a very high threat enemy if it hasn't moved
    if attack is None:
        attack, potential_targets = jester_attack_helper(hero, party, very_high_threat_not_moved,
                                                         kill_stunned_enemy=False)

    # buff party crit and speed with battle ballad if not already in affect and > 2 enemies left
    if attack is None and 'battle_ballad' in hero.skills and (hero.rank == 4 or hero.rank == 3) \
            and any(ally.buffs is None or not any(buff['stat_type'] == 2 for buff in ally.buffs.values())
                    for ally in party) and len(enemies_not_dead_already) > 2:
        attack = 'battle_ballad'

    # kill a very high threat enemy
    if attack is None:
        attack, potential_targets = jester_attack_helper(hero, party, very_high_threat_enemies,
                                                         kill_stunned_enemy=False)
    # heal stress if already 1 stack of battle ballad
    if attack is None and 'inspiring_tune' in hero.skills and (hero.rank == 4 or hero.rank == 3) \
            and any(ally.buffs is not None
                    and any(buff['stat_type'] == 2 for buff in ally.buffs.values()) for ally in party) \
            and any(ally.stress > 6 for ally in party):
        attack = 'inspiring_tune'

    # kill a high threat enemy
    if attack is None:
        attack, potential_targets = jester_attack_helper(hero, party, high_threat_not_moved, kill_stunned_enemy=False)

    # swap if need to fix position
    attack = 'swap' if attack is None and (hero.rank == 1 or hero.rank == 2
                                           or (hero.rank == 3 and party[3].heroClass in FrontLineClasses)) else attack

    # attack high threat enemy
    if attack is None:
        attack, potential_targets = jester_attack_helper(hero, party, high_threat_enemies, kill_stunned_enemy=False)

    # stress heal if main threats are dealt with
    if attack is None and 'howl' in hero.skills and hero.rank in AttackSkills['howl'][0] \
            and len(enemies_not_dead_already) < 3 and any(ally.stress > 0 for ally in party) \
            and not any(enemy.threat > 2 or (enemy.threat > 3 and not enemy.stunned)
                        for enemy in enemies_not_dead_already):
        attack = 'howl'

    # heal stress if already at least 2 stacks of battle ballad
    if attack is None and 'inspiring_tune' in hero.skills and (hero.rank == 4 or hero.rank == 3) \
            and any(ally.buffs is not None
                    and any(buff['stat_type'] == 2 for buff in ally.buffs.values()) for ally in party) \
            and any(ally.stress > 0 for ally in party):
        attack = 'inspiring_tune'

    # kill an enemy
    if attack is None:
        attack, potential_targets = jester_attack_helper(hero, party, enemies_not_moved, kill_stunned_enemy=False)

    # buff party crit and speed with battle ballad
    if attack is None and 'battle_ballad' in hero.skills and (hero.rank == 4 or hero.rank == 3):
        attack = 'battle_ballad'

    # attack an enemy
    if attack is None:
        attack, potential_targets = jester_attack_helper(hero, party, enemies_not_dead_already,
                                                         kill_stunned_enemy=True, cant_kill_enemy_ok=True)

    if attack == 'swap':
        swap_hero(hero, swap_distance, UpdatedPartyOrder, debug=Debug)
    elif attack == 'inspiring_tune' or attack == 'battle_ballad':
        party.sort(key=lambda k: k.stress, reverse=True)
        heal_target(hero, target=party[0], attack=attack, debug=Debug)
    else:
        # Find target and attack enemy
        if attack is not None:
            list_of_attacks.insert(0, attack)
        find_target_and_attack(raid_info, potential_targets, hero, party, list_of_attacks, UpdatedPartyOrder)


def vestal_attack_helper(hero, list_of_enemies, stun_chance, kill_stunned_enemy, cant_kill_enemy=False):
    attack = None
    if 'judgement' in hero.skills and (hero.rank == 3 or hero.rank == 4) \
            and any(enemy.lowHp and (not enemy.stunned or (enemy.stunned and kill_stunned_enemy))
                    for enemy in list_of_enemies):
        attack = 'judgement'
    elif 'dazzling_light' in hero.skills \
            and any((1 in enemy.rank or 2 in enemy.rank or 3 in enemy.rank)
                    and stun_chance - enemy.stunResist >= 50 and not enemy.stunned for enemy in list_of_enemies):
        attack = 'dazzling_light'
    elif 'judgement' in hero.skills and cant_kill_enemy and (hero.rank == 3 or hero.rank == 4):
        attack = 'judgement'
    return attack, list_of_enemies


def vestal_heal_helper(hero, party, enemies_not_dead_already, single_heal_thresh, multi_heal_thresh):
    """ Assumes percent hp threshold for when to use divine grace is lower than divine comfort """
    attack, target = None, None
    # if one ally hp percentage is less than divine_grace_thresh
    party.sort(key=lambda k: k.percentHp)
    ally = next((ally for ally in party
                 if ally.percentHp < single_heal_thresh and ally.currentHp < ally.maxHp
                 and ally.damageOnNextTurn < ally.maxHp), None)
    if ally is not None:
        # determine whether to use multi-target heal (divine comfort) or single target heal (divine grace)
        if 'gods_comfort' in hero.skills and hero.rank != 1 \
                and (sum(hero.percentHp < multi_heal_thresh for hero in party) > 2
                     or sum(hero.percentHp < 30 for hero in party) > 1
                     or sum(hero.percentHp < multi_heal_thresh for hero in party) > 1 and hero.rank == 2):
            attack = 'gods_comfort'
        elif 'judgement' in hero.skills and ally is hero and len(enemies_not_dead_already) > 1 \
                and (hero.rank == 3 or hero.rank == 4):
            attack = 'judgement'
        elif 'divine_grace' in hero.skills and (hero.rank == 3 or hero.rank == 4):
            attack = 'divine_grace'
            target = ally
    return attack, target


def vestal_action(party_sorted_by_rank, hero, raid_info, enemy_formation):
    """[ Ideal skill load-out: judgement, dazzling light, divine grace, divine comfort ]"""
    global UpdatedPartyOrder
    party = party_sorted_by_rank
    potential_targets = []
    # stall_count = raid_info['battle']['round_stall_count']
    # stall_accelerated = raid_info['battle']['previous_stall_accelerated']
    # stall = False if stall_count >= 2 or stall_accelerated else True
    list_of_attacks = ['judgement', 'gods_hand', 'gods_illumination']
    attack, target, stun_chance = None, None, None

    if hero.rank == 1:
        attack = 'swap'
    elif hero.rank == 2 or hero.rank == 3 or hero.rank == 4:
        enemies_not_dead_already = [enemy for enemy in enemy_formation if not enemy.alreadyGoingToDie]
        high_threat_enemies = [enemy for enemy in enemies_not_dead_already if enemy.threat >= 4]
        very_high_threat_enemies = [enemy for enemy in high_threat_enemies if enemy.threat >= 7
                                    or (enemy.name == 'Bone Arbalist' and (3 in enemy.rank or 4 in enemy.rank))]
        very_high_threat_not_moved = [enemy for enemy in very_high_threat_enemies if not enemy.alreadyMoved]
        high_threat_not_moved = [enemy for enemy in high_threat_enemies if not enemy.alreadyMoved]

        if 'dazzling_light' in hero.skills:
            stun_level = hero.skills['dazzling_light']
            stun_chance = AttackSkills['dazzling_light'][2][stun_level]

        # ally is on death's door or going to die from poison or bleed (less than 1% effective hp)
        if attack is None:
            multi_thresh = 30 if 'gods_comfort' in hero.skills else 100
            attack, target = vestal_heal_helper(hero, party, enemies_not_dead_already, single_heal_thresh=1,
                                                multi_heal_thresh=multi_thresh)

        # can kill or stun very high threat enemies that haven't moved yet (>=7) and multiple enemies left
        if attack is None and len(enemies_not_dead_already) >= 1 and len(very_high_threat_not_moved) > 0:
            attack, potential_targets \
                = vestal_attack_helper(hero, very_high_threat_not_moved, stun_chance, kill_stunned_enemy=False)

        # one ally < 30% hp or multiple allies < 50% hp
        if attack is None:
            multi_thresh = 50 if 'gods_comfort' in hero.skills else 100
            attack, target = vestal_heal_helper(hero, party, enemies_not_dead_already, single_heal_thresh=30,
                                                multi_heal_thresh=multi_thresh)

        # can kill or stun very high threat enemies that haven't moved yet (>=7)
        if attack is None and len(very_high_threat_not_moved) > 0:
            attack, potential_targets \
                = vestal_attack_helper(hero, very_high_threat_not_moved, stun_chance, kill_stunned_enemy=False)

        # one ally < 50% hp or multiple allies < 70% hp
        if attack is None:
            multi_thresh = 70 if 'gods_comfort' in hero.skills else 100
            attack, target = vestal_heal_helper(hero, party, enemies_not_dead_already, single_heal_thresh=50,
                                                multi_heal_thresh=multi_thresh)

        # can kill or stun high threat enemies that haven't moved yet (>=4)
        if attack is None and len(high_threat_not_moved) > 0:
            attack, potential_targets \
                = vestal_attack_helper(hero, high_threat_not_moved, stun_chance, kill_stunned_enemy=False)

        # can kill or stun very high threat enemies (>=7)
        if attack is None and len(very_high_threat_enemies) > 0:
            attack, potential_targets \
                = vestal_attack_helper(hero, very_high_threat_enemies, stun_chance, kill_stunned_enemy=False,
                                       cant_kill_enemy=True)

        # swap if rank 2, can't stun, and (not back line hero in rank 3 or no rank 2 heal skill)
        if attack is None and hero.rank == 2:
            if 'dazzling_light' not in hero.skills or 'gods_comfort' not in hero.skills \
                    or (not any((1 in enemy.rank or 2 in enemy.rank or 3 in enemy.rank)
                                and stun_chance - enemy.stunResist >= 50 and not enemy.stunned
                                for enemy in enemies_not_dead_already)
                        and party[2].heroClass not in BackLineClasses
                        and not (party[2].heroClass == 'crusader'
                                 and any(2 in enemy.rank or 3 in enemy.rank
                                         or 4 in enemy.rank for enemy in enemies_not_dead_already))):
                attack = 'swap'

        # can kill or stun high threat enemies (>=4)
        if attack is None and len(high_threat_enemies) > 0:
            attack, potential_targets \
                = vestal_attack_helper(hero, high_threat_enemies, stun_chance, kill_stunned_enemy=True)

        # one ally < 60% hp or multiple allies < 80% hp
        if attack is None:
            multi_thresh = 80 if 'gods_comfort' in hero.skills else 100
            attack, target = vestal_heal_helper(hero, party, enemies_not_dead_already, single_heal_thresh=60,
                                                multi_heal_thresh=multi_thresh)

        # one ally < 70% hp or multiple allies < 90% hp
        if attack is None:
            multi_thresh = 90 if 'gods_comfort' in hero.skills else 100
            attack, target = vestal_heal_helper(hero, party, enemies_not_dead_already, single_heal_thresh=70,
                                                multi_heal_thresh=multi_thresh)
        # archers on rank 3 or 4
        archers = [enemy for enemy in enemies_not_dead_already if enemy.name == 'Bone Arbalist']
        if attack is None and len(archers) > 0:
            attack, potential_targets \
                = vestal_attack_helper(hero, archers, stun_chance,
                                       kill_stunned_enemy=False, cant_kill_enemy=False)
        # more than one weak enemy left
        if attack is None and len(enemies_not_dead_already) > 1:
            attack, potential_targets \
                = vestal_attack_helper(hero, enemies_not_dead_already, stun_chance,
                                       kill_stunned_enemy=False, cant_kill_enemy=False)

        # one ally < 100% hp or multiple allies < 100% hp
        if attack is None:
            attack, target = vestal_heal_helper(hero, party, enemies_not_dead_already, single_heal_thresh=100,
                                                multi_heal_thresh=100)
        # can stun enemy
        if attack is None:
            if 'dazzling_light' in hero.skills \
                    and any(stun_chance - enemy.stunResist >= 50 and not enemy.stunned
                            and enemy.rank in AttackSkills['dazzling_light'][1] for enemy in enemies_not_dead_already):
                attack = 'dazzling_light'
                potential_targets = enemies_not_dead_already

        # default to heal skill if doesn't have judgement
        if attack is None and ('judgement' not in hero.skills or hero.rank == 2):
            if 'gods_comfort' in hero.skills:
                attack = 'gods_comfort'
            elif 'divine_grace' in hero.skills and hero.rank != 2:
                attack = 'divine_grace'
                party.sort(key=lambda k: k.stress, reverse=True)
                target = party[0]  # highest stress ally
            else:
                attack = 'swap'

    if attack == 'swap':
        swap_hero(hero, swap_distance=-1, party_order=UpdatedPartyOrder, debug=Debug)
    elif attack == 'dazzling_light':
        find_target_and_stun(hero, potential_targets, attack, stun_chance, UpdatedPartyOrder)
    elif attack == 'gods_comfort' or attack == 'divine_grace':
        heal_target(hero, target, attack, Debug)
    else:
        # Find target and attack enemy
        if attack is not None:
            list_of_attacks.insert(0, attack)
        find_target_and_attack(raid_info, enemy_formation, hero, party, list_of_attacks, UpdatedPartyOrder)


def plague_doctor_attack_helper(hero, list_of_enemies):
    attack, stun_chance = None, None
    blinding_stun_chance, disorienting_stun_chance, noxious_poison_dmg, plague_poison_dmg = None, None, None, None

    if 'blinding_gas' in hero.skills:
        blinding_stun_level = hero.skills['blinding_gas']
        blinding_stun_chance = AttackSkills['blinding_gas'][2][blinding_stun_level]
    if 'disorienting_blast' in hero.skills:
        disorienting_stun_level = hero.skills['disorienting_blast']
        disorienting_stun_chance = AttackSkills['disorienting_blast'][2][disorienting_stun_level]
    if 'noxious_blast' in hero.skills:
        noxious_skill_level = hero.skills['noxious_blast']
        noxious_poison_dmg = AttackSkills['noxious_blast'][2][noxious_skill_level]
    if 'plague_grenade' in hero.skills:
        plague_skill_level = hero.skills['plague_grenade']
        plague_poison_dmg = AttackSkills['plague_grenade'][2][plague_skill_level]

    # prioritize targets in the back ranks first
    for enemy in reversed(list_of_enemies):
        # can kill enemy in rank 3 or 4
        if (3 in enemy.rank or 4 in enemy.rank) and 'plague_grenade' in hero.skills \
                and (enemy.effectiveHp <= plague_poison_dmg + 1
                     or (enemy.stunned and enemy.effectiveHp <= plague_poison_dmg * 2 + 1)):
            attack = 'plague_grenade'
            break
        # can stun enemy in rank 3 or 4
        if (3 in enemy.rank or 4 in enemy.rank) and not enemy.stunned:
            if 'disorienting_blast' in hero.skills and disorienting_stun_chance - enemy.stunResist >= 50:
                attack = 'disorienting_blast'
                stun_chance = disorienting_stun_chance
                break
            if 'blinding_gas' in hero.skills and blinding_stun_chance - enemy.stunResist >= 50 \
                    and hero.blinding_gas_count < 3:
                attack = 'blinding_gas'
                stun_chance = blinding_stun_chance
                break
        # can kill enemy in rank 1 or 2
        if 1 in enemy.rank or 2 in enemy.rank:
            if 'noxious_blast' in hero.skills \
                    and (enemy.effectiveHp <= noxious_poison_dmg + 1
                         or (enemy.stunned and enemy.effectiveHp <= noxious_poison_dmg * 2 + 1)):
                attack = 'noxious_blast'
                list_of_enemies = [enemy]
                break
            if 'incision' in hero.skills and not enemy.isTank and enemy.percentHpRemain <= 40 and not enemy.stunned:
                attack = 'incision'
                list_of_enemies = [enemy]
                break
        # can stun enemy in rank 2
        if 2 in enemy.rank and not enemy.stunned:
            if 'disorienting_blast' in hero.skills and disorienting_stun_chance - enemy.stunResist >= 50:
                attack = 'disorienting_blast'
                stun_chance = disorienting_stun_chance
                break
    return attack, stun_chance, list_of_enemies


def plague_doctor_action(party_sorted_by_rank, hero, raid_info, enemy_formation):
    """[ Ideal skill load-out: noxious_blast,
            any 3 - plague_grenade, battlefield_medicine, blinding_gas, disorienting_blast ]"""
    global attack_completed, UpdatedPartyOrder
    current_round = raid_info['battle']['round']
    stall_count = raid_info['battle']['round_stall_count']
    stall_accelerated = raid_info['battle']['previous_stall_accelerated']
    stall = False if stall_count >= 2 or stall_accelerated else True
    party = party_sorted_by_rank
    list_of_attacks = ['plague_grenade', 'noxious_blast', 'incision']
    attack, stun_chance, target = None, None, None

    enemies_not_dead_already = [enemy for enemy in enemy_formation if not enemy.alreadyGoingToDie]
    high_threat_enemies = [enemy for enemy in enemies_not_dead_already if enemy.threat >= 4]
    very_high_threat_enemies = [enemy for enemy in high_threat_enemies if enemy.threat >= 7
                                or (enemy.name == 'Bone Arbalist' and (3 in enemy.rank or 4 in enemy.rank))]
    very_high_threat_not_moved = [enemy for enemy in very_high_threat_enemies if not enemy.alreadyMoved]
    high_threat_not_moved = [enemy for enemy in high_threat_enemies if not enemy.alreadyMoved]
    potential_targets = enemy_formation
    enemy = enemies_not_dead_already[0] if len(enemies_not_dead_already) > 0 else None

    blinding_stun_chance, disorienting_stun_chance, plague_poison_dmg = None, None, None
    if 'blinding_gas' in hero.skills:
        blinding_stun_level = hero.skills['blinding_gas']
        blinding_stun_chance = AttackSkills['blinding_gas'][2][blinding_stun_level]
    if 'disorienting_blast' in hero.skills:
        disorienting_stun_level = hero.skills['disorienting_blast']
        disorienting_stun_chance = AttackSkills['disorienting_blast'][2][disorienting_stun_level]
    if 'plague_grenade' in hero.skills:
        plague_skill_level = hero.skills['plague_grenade']
        plague_poison_dmg = AttackSkills['plague_grenade'][2][plague_skill_level]

    # use battlefield medicine to heal target in danger of dying or with large blight/bleed
    if 'battlefield_medicine' in hero.skills and (hero.rank == 3 or hero.rank == 4):
        target = next((ally for ally in party if ally.currentHp == 0 and ally.effectiveHp < 0), None)
        if target is None:
            target = next((ally for ally in party if ally.percentHp <= 30 and ally.damageOnNextTurn > 0), None)
        if target is None:
            target = next((ally for ally in party if ally.damageOverTime >= 20), None)
        if target is not None:
            attack = 'battlefield_medicine'
    # stall if only one weak enemy left and need to heal or stress heal
    if (len(enemies_not_dead_already) == 0
        or (len(enemies_not_dead_already) == 1
            and (stall or (enemy.canBeKilledIn1Hit
                           and any(ally is not hero and not ally.already_moved and not ally.stunned
                                   and (((ally.rank == 1 or ally.rank == 2) and (ally.heroClass in FrontLineClasses))
                                        or (ally.heroClass not in BackLineClasses and ally.rank != 4))
                                   for ally in party))) and current_round < 8)) \
            and ((any(ally.percentHp < 80 for ally in party) and any(ally.healer for ally in party))
                 or (any(ally.stress > 0 for ally in party) and any(ally.stressHealer for ally in party))):
        if enemy is not None and not enemy.stunned and 'disorienting_blast' in hero.skills \
                and hero.rank in AttackSkills['disorienting_blast'][0] \
                and disorienting_stun_chance - enemy.stunResist >= 50 \
                and any(rank in AttackSkills['disorienting_blast'][1] for rank in enemy.rank):
            attack = 'disorienting_blast'
            target = enemy
        elif enemy is not None and not enemy.stunned and 'blinding_gas' in hero.skills \
                and hero.rank in AttackSkills['blinding_gas'][0] \
                and blinding_stun_chance - enemy.stunResist >= 50 \
                and any(rank in AttackSkills['blinding_gas'][1] for rank in enemy.rank) and hero.blinding_gas_count < 3:
            attack = 'blinding_gas'
            target = enemy
        elif enemy is None or enemy.threat < 4 or (enemy.stunned and enemy.canBeKilledIn1Hit):
            attack, target = plague_doctor_stall_helper(hero, party)
    if target is None and hero.rank == 1:
        if 'incision' in hero.skills:
            if party[1].heroClass not in BackLineClasses:
                attack = 'swap'
            elif party[1].heroClass in BackLineClasses:
                attack = 'incision'
    elif target is None and hero.rank == 2:
        enemy_in_rank2 = True if (len(enemy_formation) == 1 and 2 in enemy_formation[0].rank) \
                                 or len(enemy_formation) > 1 else False
        if 'disorienting_blast' in hero.skills:
            stun_targets = [enemy for enemy in enemies_not_dead_already
                            if (2 in enemy.rank or 3 in enemy.rank or 4 in enemy.rank)
                            and (disorienting_stun_chance - enemy.stunResist >= 50 and not enemy.stunned)]
            if len(stun_targets) > 0:
                attack = 'disorienting_blast'
                potential_targets = stun_targets
                stun_chance = disorienting_stun_chance
        elif party[2].heroClass == 'highwayman' or party[2].heroClass == 'shield_breaker' \
                or (party[2].heroClass == 'crusader' and enemy_in_rank2):
            attack = 'noxious_blast'
        else:
            attack = 'swap' if party[2].heroClass not in BackLineClasses else None
    elif target is None and (hero.rank == 3 or hero.rank == 4):
        rank3_enemy = next((enemy for enemy in enemy_formation if 3 in enemy.rank), None)
        rank4_enemy = next((enemy for enemy in enemy_formation if 4 in enemy.rank and 3 not in enemy.rank), None)

        # two enemies on ranks 3 & 4 and at least 1 very high threat or skeleton archer
        if rank3_enemy is not None and rank4_enemy is not None:
            back_rank_targets = [rank3_enemy, rank4_enemy]
            priority_target = next((enemy for enemy in back_rank_targets
                                    if enemy.threat >= 7
                                    and not enemy.alreadyGoingToDie and not enemy.alreadyMoved), None)
            if priority_target is None:
                priority_target = next((enemy for enemy in back_rank_targets
                                        if enemy.threat >= 7 and not enemy.alreadyGoingToDie), None)
            if priority_target is None:
                priority_target = next((enemy for enemy in back_rank_targets
                                        if enemy.name == 'Bone Arbalist'
                                        and not enemy.alreadyGoingToDie and not enemy.alreadyMoved), None)
            if priority_target is None:
                priority_target = next((enemy for enemy in back_rank_targets
                                        if enemy.name == 'Bone Arbalist' and not enemy.alreadyGoingToDie), None)
            if priority_target is not None and not rank3_enemy.alreadyGoingToDie and not rank4_enemy.alreadyGoingToDie:
                # can stun the priority target with blinding gas and possibly another
                if 'blinding_gas' in hero.skills and not rank3_enemy.stunned and not rank4_enemy.stunned \
                        and hero.blinding_gas_count < 3 and (blinding_stun_chance - priority_target.stunResist >= 35) \
                        and any(blinding_stun_chance - enemy.stunResist >= 50 for enemy in back_rank_targets):
                    attack = 'blinding_gas'
                    stun_chance = blinding_stun_chance
                    target = priority_target

        # can kill or stun a very high threat enemy that hasn't moved (>= 7)
        if attack is None and len(very_high_threat_not_moved) > 0:
            attack, stun_chance, potential_targets = plague_doctor_attack_helper(hero, very_high_threat_not_moved)

        # can kill or stun a very high threat enemy (>= 7)
        if attack is None and len(very_high_threat_enemies) > 0:
            attack, stun_chance, potential_targets = plague_doctor_attack_helper(hero, very_high_threat_enemies)

        # can pull or stun a skeleton archer on rank 3 or 4
        if attack is None:
            skeleton_archer = next((enemy for enemy in enemies_not_dead_already if enemy.name == 'Bone Arbalist'
                                    and (3 in enemy.rank or 4 in enemy.rank) and not enemy.alreadyMoved), None)
            if skeleton_archer is None:
                skeleton_archer = next((enemy for enemy in enemies_not_dead_already if enemy.name == 'Bone Arbalist'
                                        and (3 in enemy.rank or 4 in enemy.rank)), None)
            if skeleton_archer is not None:
                if 'disorienting_blast' in hero.skills:
                    attack = 'disorienting_blast'
                    stun_chance = disorienting_stun_chance
                    target = skeleton_archer
                elif 'blinding_gas' in hero.skills and blinding_stun_chance - skeleton_archer.stunResist > 50 \
                        and not skeleton_archer.stunned and hero.blinding_gas_count < 3:
                    attack = 'blinding_gas'
                    stun_chance = blinding_stun_chance

        # two enemies on ranks 3 & 4
        if attack is None and rank3_enemy is not None and rank4_enemy is not None \
                and not rank3_enemy.alreadyGoingToDie and not rank4_enemy.alreadyGoingToDie:
            # can stun two enemies with blinding gas
            if 'blinding_gas' in hero.skills and not rank3_enemy.stunned and not rank4_enemy.stunned \
                        and hero.blinding_gas_count < 3 and (blinding_stun_chance - rank3_enemy.stunResist >= 50
                                                             or blinding_stun_chance - rank4_enemy.stunResist >= 50):
                attack = 'blinding_gas'
                stun_chance = blinding_stun_chance
                potential_targets = [rank3_enemy, rank4_enemy]
            # can kill one of them
            elif 'plague_grenade' in hero.skills and (rank3_enemy.effectiveHp <= plague_poison_dmg + 1
                                                      or rank4_enemy.effectiveHp <= plague_poison_dmg + 1):
                attack = 'plague_grenade'

        # can kill or stun a high threat enemy that hasn't moved (>= 4)
        if attack is None and len(high_threat_not_moved) > 0:
            attack, stun_chance, potential_targets = plague_doctor_attack_helper(hero, high_threat_not_moved)

        # can kill or stun a high threat enemy (>= 4)
        if attack is None and len(high_threat_enemies) > 0:
            attack, stun_chance, potential_targets = plague_doctor_attack_helper(hero, high_threat_enemies)

        # can kill or stun enemy
        if attack is None and len(enemies_not_dead_already) > 0:
            attack, stun_chance, potential_targets = plague_doctor_attack_helper(hero, enemies_not_dead_already)

        # swap if beneficial
        if attack is None and hero.rank == 3 and party[3].heroClass != 'vestal':
            attack = 'swap'

        # cure bleed/blight
        if attack is None and 'battlefield_medicine' in hero.skills and (hero.rank == 3 or hero.rank == 4) \
                and len(high_threat_enemies) == 0 and any(ally.percentHp < 90 for ally in party):
            heal_targets = list(hero for hero in party if hero.bleedAmount > 0 or hero.blightAmount > 0)
            if len(heal_targets) > 0:
                heal_targets.sort(key=lambda k: k.damageOverTime, reverse=True)
                target = heal_targets[0]
                attack = 'battlefield_medicine'

    if attack == 'swap':
        target = -1 if target is None else target
        swap_hero(hero, swap_distance=target, party_order=UpdatedPartyOrder, debug=Debug)
    elif attack == 'blinding_gas' or attack == 'disorienting_blast':
        find_target_and_stun(hero, potential_targets, attack, stun_chance, UpdatedPartyOrder, target)
    elif attack == 'battlefield_medicine' or attack == 'emboldening_vapours':
        heal_target(hero, target, attack, Debug)
    else:
        # Find target and attack enemy
        if attack is not None:
            list_of_attacks.insert(0, attack)
        find_target_and_attack(raid_info, potential_targets, hero, party, list_of_attacks, UpdatedPartyOrder)

    # heal, buff, or swap if can't hit enemies with any attacks
    if not attack_completed and attack != 'swap' and attack != 'blinding_gas' and attack != 'disorienting_blast' \
            and attack != 'battlefield_medicine' and attack != 'emboldening_vapours':
        attack, target = plague_doctor_stall_helper(hero, party_sorted_by_rank)
        if attack == 'swap':
            swap_hero(hero, swap_distance=target, party_order=UpdatedPartyOrder, debug=Debug)
        elif attack == 'blinding_gas' or attack == 'disorienting_blast':
            find_target_and_stun(hero, potential_targets, attack, stun_chance, UpdatedPartyOrder, target)
        elif attack == 'battlefield_medicine' or attack == 'emboldening_vapours':
            heal_target(hero, target, attack, Debug)


def plague_doctor_stall_helper(hero, party_sorted_by_rank):
    if 'battlefield_medicine' in hero.skills and (hero.rank == 3 or hero.rank == 4):
        attack = 'battlefield_medicine'
        party_sorted_by_rank.sort(key=lambda k: k.damageOverTime, reverse=True)
        if party_sorted_by_rank[0].damageOverTime <= 2:
            party_sorted_by_rank.sort(key=lambda k: k.percentHp)
        return attack, party_sorted_by_rank[0]
    elif 'emboldening_vapours' in hero.skills and hero.emboldening_vapours_count < 2:
        attack = 'emboldening_vapours'
        target = next(hero for hero in party_sorted_by_rank if hero.heroClass == 'vestal')
        return attack, target
    else:
        attack = 'swap'
        swap_distance = -1
        if hero.rank == 4:
            swap_distance = 1
        elif (hero.rank == 1 and party_sorted_by_rank[1].heroClass in BackLineClasses) \
                or (hero.rank == 2 and party_sorted_by_rank[2].heroClass in BackLineClasses):
            swap_distance = 0
        return attack, swap_distance


def highwayman_action(party_sorted_by_rank, hero, raid_info, enemy_formation):
    """[ Ideal skill load-out: wicked slice, pistol shot, duelists advance, point blank shot ]"""
    global UpdatedPartyOrder
    party = party_sorted_by_rank
    current_round = raid_info['battle']['round']
    list_of_attacks = ['wicked_slice', 'opened_vein', 'pistol_shot']
    stall_count = raid_info['battle']['round_stall_count']
    stall_accelerated = raid_info['battle']['previous_stall_accelerated']
    stall = False if stall_count >= 2 or stall_accelerated else True
    attack = None
    swap_distance = 1
    enemies_not_dead_already = [enemy for enemy in enemy_formation if not enemy.alreadyGoingToDie]
    very_high_threat_enemies = [enemy for enemy in enemies_not_dead_already if enemy.threat >= 7]
    enemy = enemies_not_dead_already[0] if len(enemies_not_dead_already) > 0 else None

    # stall if only one weak enemy left and need to heal or stress heal
    if (len(enemies_not_dead_already) == 0
        or (len(enemies_not_dead_already) == 1
            and (stall or (enemy.canBeKilledIn1Hit
                           and any(ally is not hero and not ally.already_moved and not ally.stunned
                                   and (((ally.rank == 1 or ally.rank == 2) and (ally.heroClass in FrontLineClasses))
                                        or (ally.heroClass not in BackLineClasses and ally.rank != 4))
                                   for ally in party))) and current_round < 8)) \
            and ((any(ally.percentHp < 80 for ally in party) and any(ally.healer for ally in party))
                 or (any(ally.stress > 0 for ally in party) and any(ally.stressHealer for ally in party))):
        if enemy is None or ((enemy.threat < 4
                             and not (enemy.name == 'Bone Arbalist' and (3 in enemy.rank or 4 in enemy.rank))
                             and not (enemy.name == 'Brigand Fusilier' and (1 not in enemy.rank))
                             and not enemy.isTank) or (enemy.stunned and not enemy.isTank)):
            attack = 'swap'
            swap_distance = -1 if hero.rank == 1 or (hero.rank == 3 and (party[1].heroClass == 'hellion' or
                                                                         party[1].heroClass == 'crusader')) else 1
    if attack is None and hero.rank == 1:
        # point blank shot if front line hero on rank 2 or highway on rank 2 and no enemies in back ranks,
        #   and no high priority enemy on rank 2
        if party[1].heroClass in FrontLineClasses or party[1].heroClass == 'man_at_arms' \
                or party[1].heroClass == 'shieldbreaker' \
                or (party[1].heroClass == 'highwayman'
                    and (party[1].already_moved
                         or not any((3 in enemy.rank or 4 in enemy.rank) and not (1 in enemy.rank or 2 in enemy.rank)
                                    for enemy in very_high_threat_enemies))):
            if 'point_blank_shot' in hero.skills \
                    and ((any(1 in enemy.rank and enemy.threat > 0 for enemy in enemy_formation)
                          and sum(enemy.threat < 4 for enemy in enemy_formation) >= 2
                          and not any(2 in enemy.rank for enemy in very_high_threat_enemies))
                         or any(1 in enemy.rank and enemy.threat >= 4 for enemy in enemy_formation)):
                attack = 'point_blank_shot'
            elif not any((1 in enemy.rank or 2 in enemy.rank) and enemy.threat >= 4 for enemy in enemies_not_dead_already) \
                    or (any(1 in enemy.rank or 2 in enemy.rank for enemy in enemies_not_dead_already)
                        and (sum(enemy.threat < 4 for enemy in enemy_formation) == 1)
                        and not any(enemy.threat >= 4 for enemy in enemies_not_dead_already))\
                    or not any(1 in enemy.rank or 2 in enemy.rank for enemy in enemies_not_dead_already):
                attack = 'swap'
                swap_distance = -1
    elif attack is None and (hero.rank == 2 or hero.rank == 3):
        if 'duelist_advance' in hero.skills and len(enemy_formation) > 1 or 2 in enemy_formation[0].rank:
            # duelist's advance if party out of position
            attack = 'duelist_advance' if party[hero.rank-2].heroClass in BackLineClasses else attack
            if attack is None and len(enemies_not_dead_already) >= 3 \
                    and ((hero.rank == 3 and party[1].heroClass not in FrontLineClasses)
                         or (hero.rank == 2 and party[0].heroClass != 'hellion')
                         or (hero.rank == 2 and party[0].heroClass == 'hellion'
                             and not any(4 in enemy.rank for enemy in enemies_not_dead_already))):
                # duelist's advance if can kill high threat enemy and still 3 enemies left after
                if len(very_high_threat_enemies) > 0:
                    if any(enemy.lowHp and any(rank in AttackSkills['duelist_advance'][1] for rank in enemy.rank)
                           for enemy in very_high_threat_enemies) and len(enemies_not_dead_already) == 4:
                        attack = 'duelist_advance'
                    # duelist's advance if can't kill high threat enemy with a different attack,
                    #   and no high threat target on rank 4
                    elif not any(enemy.canBeKilledIn1Hit
                                 and any(rank in AttackSkills['duelist_advance'][1] for rank in enemy.rank)
                                 for enemy in very_high_threat_enemies) \
                            and not any(4 in enemy.rank or (3 in enemy.rank and len(enemy.rank) == 1)
                                        for enemy in very_high_threat_enemies):
                        attack = 'duelist_advance'
                # duelist's advance if no high threat enemies and can kill one with it,
                #   or can't kill any with a different ability either, and still 3 enemies left after
                elif len(very_high_threat_enemies) == 0 \
                        and (not any(enemy.canBeKilledIn1Hit for enemy in enemies_not_dead_already)
                             or any(enemy.lowHp
                                    and any(rank in AttackSkills['duelist_advance'][1] for rank in enemy.rank)
                                    for enemy in enemies_not_dead_already))\
                        and len(enemies_not_dead_already) == 4:
                    attack = 'duelist_advance'
        elif party[hero.rank-2].heroClass in BackLineClasses \
                or (hero.rank == 3 and party[0].heroClass in BackLineClasses):
            attack = 'swap'
            swap_distance = 2 if hero.rank == 3 and party[0].heroClass in BackLineClasses else 1

    elif attack is None and hero.rank == 4:
        if len(enemy_formation) > 1 or 2 in enemy_formation[0].rank:
            # duelist's advance if not front line ally in rank 3
            attack = 'duelist_advance' \
                if not party[2].heroClass in FrontLineClasses or party[2].heroClass == 'highwayman' or \
                party[2].heroClass == 'shieldbreaker' else attack
        elif len(enemy_formation) == 1:
            attack = 'swap'

    if attack == 'swap':
        swap_hero(hero, swap_distance, UpdatedPartyOrder, debug=Debug)
    else:
        # Find target and attack enemy
        if attack is not None:
            list_of_attacks.insert(0, attack)
        find_target_and_attack(raid_info, enemy_formation, hero, party, list_of_attacks, UpdatedPartyOrder)


def man_at_arms_attack_helper(hero, party, list_of_enemies, enemies_not_dead_already, stun_chance,
                              kill_stunned_enemy, cant_kill_enemy_ok=False):
    attack = None
    if 'retribution' in hero.skills and hero.rank in AttackSkills['retribution'][0] \
            and any(enemy.effectiveHp <= 3 and (not enemy.stunned or kill_stunned_enemy)
                    and any(rank in AttackSkills['retribution'][1] for rank in enemy.rank)
                    for enemy in list_of_enemies) and len(enemies_not_dead_already) >= 3:
        attack = 'retribution'
    elif 'crush' in hero.skills and hero.rank in AttackSkills['crush'][0] \
            and any(enemy.lowHp
                    and ((not enemy.stunned or (enemy.stunned and kill_stunned_enemy))
                         and any(rank in AttackSkills['crush'][1] for rank in enemy.rank))
                    for enemy in list_of_enemies):
        attack = 'crush'
    elif 'rampart' in hero.skills and hero.rank in AttackSkills['rampart'][0] \
            and not (hero.rank == 2 and party[0].heroClass == 'hellion' and 'iron_swan' in party[0].skills
                     and any(4 in enemy.rank and enemy.threat >= 7 for enemy in enemies_not_dead_already)) \
            and any(any(rank in AttackSkills['rampart'][1] for rank in enemy.rank)
                    and stun_chance - enemy.stunResist >= 50 and not enemy.stunned for enemy in list_of_enemies):
        attack = 'rampart'
    elif 'crush' in hero.skills and hero.rank in AttackSkills['crush'][0] and cant_kill_enemy_ok \
            and any(enemy.rank in AttackSkills['crush'][1] for enemy in list_of_enemies):
        attack = 'crush'
    elif 'rampart' in hero.skills and hero.rank in AttackSkills['rampart'][0] and cant_kill_enemy_ok \
            and not (hero.rank == 2 and party[0].heroClass == 'hellion' and 'iron_swan' in party[0].skills
                     and any(4 in enemy.rank and enemy.threat >= 7 for enemy in enemies_not_dead_already)) \
            and any(enemy.rank in AttackSkills['rampart'][1] for enemy in list_of_enemies):
        attack = 'rampart'
    return attack, list_of_enemies


def man_at_arms_stall_helper(hero, party, swap_distance):
    if (hero.rank == 2 or hero.rank == 3) and party[hero.rank - 2].heroClass in BackLineClasses:
        attack = 'swap'
    elif (hero.rank == 2 or hero.rank == 3) and party[hero.rank].heroClass in FrontLineClasses:
        swap_distance = -1
        attack = 'swap'
    elif hero.rank == 2 and (party[0].heroClass == 'hellion' or party[0].heroClass == 'highwayman'):
        attack = 'swap'
    elif 'bolster' in hero.skills and hero.bolster_count == 0:
        attack = 'bolster'
    elif 'defender' in hero.skills:
        attack = 'defender'
    elif 'command' in hero.skills:
        attack = 'command'
    else:
        if hero.rank == 1:
            swap_distance = -1
        attack = 'swap'
    return attack, swap_distance


def man_at_arms_action(party_sorted_by_rank, hero, raid_info, enemy_formation):
    """[ Ideal skill load-out: rampart, retribution, crush, any - defender, command, bolster ]"""
    global attack_completed, UpdatedPartyOrder
    party = party_sorted_by_rank
    current_round = raid_info['battle']['round']
    list_of_attacks = ['crush', 'rampart', 'retribution']
    stall_count = raid_info['battle']['round_stall_count']
    stall_accelerated = raid_info['battle']['previous_stall_accelerated']
    stall = False if stall_count >= 2 or stall_accelerated else True
    attack, stun_chance, target = None, None, None
    swap_distance = 1

    enemies_not_dead_already = [enemy for enemy in enemy_formation if not enemy.alreadyGoingToDie]
    enemies_not_moved = [enemy for enemy in enemies_not_dead_already if not enemy.alreadyMoved]
    high_threat_enemies = [enemy for enemy in enemies_not_dead_already if enemy.threat >= 4]
    very_high_threat_enemies = [enemy for enemy in high_threat_enemies if enemy.threat >= 7]
    very_high_threat_not_moved = [enemy for enemy in very_high_threat_enemies if not enemy.alreadyMoved]
    high_threat_not_moved = [enemy for enemy in high_threat_enemies if not enemy.alreadyMoved]
    potential_targets = enemy_formation
    enemy = enemies_not_dead_already[0] if len(enemies_not_dead_already) > 0 else None

    if 'rampart' in hero.skills:
        stun_level = hero.skills['rampart']
        stun_chance = AttackSkills['rampart'][2][stun_level]

    # defend ally who is on deaths door
    # future - defend ally to protect from stress damage ???
    if attack is None and len(enemies_not_dead_already) > 0 \
            and 'defender' in hero.skills and any(ally.currentHp == 0 for ally in party) \
            and (len(enemies_not_dead_already) > 1 or not enemy.stunned):
        attack = 'defender'
    # stall if only one weak enemy left and need to heal or stress heal
    if attack is None \
            and (len(enemies_not_dead_already) == 0
                 or (len(enemies_not_dead_already) == 1 and enemy.threat < 4
                     and (stall
                          or (enemy.canBeKilledIn1Hit
                              and any(ally is not hero and not ally.already_moved and not ally.stunned
                                      and (((ally.rank == 1 or ally.rank == 2) and (ally.heroClass in FrontLineClasses))
                                           or (ally.heroClass not in BackLineClasses and ally.rank != 4))
                                      for ally in party))) and current_round < 8)) \
            and ((any(ally.percentHp < 80 for ally in party) and any(ally.healer for ally in party))
                 or (any(ally.stress > 0 for ally in party) and any(ally.stressHealer for ally in party))):
        if 'rampart' in hero.skills and len(enemies_not_dead_already) == 1 \
                and hero.rank in AttackSkills['rampart'][0] \
                and any(rank in AttackSkills['rampart'][1] for rank in enemy.rank) \
                and not enemy.stunned and stun_chance - enemy.stunResist >= 50 \
                and (not enemy.canBeKilledIn1Hit or enemy.threat >= 4):
            attack = 'rampart'
        elif enemy.name == 'Bone Arbalist' and (3 in enemy.rank or 4 in enemy.rank):
            attack = 'crush'  # clear corpses
            potential_targets = enemy_formation
        elif (enemy.stunned or enemy.threat < 4) or len(enemies_not_dead_already) == 0 \
                and any(not ally.already_moved and ally is not hero for ally in party):
            # swap heroes or use buffs
            attack, swap_distance = man_at_arms_stall_helper(hero, party, swap_distance)

    # kill an enemy or stun very high threat enemy
    if attack is None:
        attack, potential_targets = man_at_arms_attack_helper(hero, party, very_high_threat_not_moved,
                                                              enemies_not_dead_already, stun_chance,
                                                              kill_stunned_enemy=False)
    if attack is None:
        attack, potential_targets = man_at_arms_attack_helper(hero, party, very_high_threat_enemies,
                                                              enemies_not_dead_already, stun_chance,
                                                              kill_stunned_enemy=True, cant_kill_enemy_ok=True)
    # kill an enemy or stun high threat enemy
    if attack is None:
        attack, potential_targets = man_at_arms_attack_helper(hero, party, high_threat_not_moved,
                                                              enemies_not_dead_already,
                                                              stun_chance, kill_stunned_enemy=False)
    # swap if need to fix position
    if attack is None and (hero.rank == 2 or hero.rank == 3) and party[hero.rank-2].heroClass in BackLineClasses:
        if 'rampart' in hero.skills and hero.rank in AttackSkills['rampart'][0] \
                and any(any(rank in AttackSkills['rampart'][1] for rank in enemy.rank) and enemy.threat > 0
                        for enemy in enemy_formation):
            attack = 'rampart'
            potential_targets = enemies_not_dead_already
        else:
            attack = 'swap'
    attack = 'swap' if attack is None and hero.rank == 4 and party[2].rank not in FrontLineClasses else attack

    # attack high threat enemy
    if attack is None:
        attack, potential_targets = man_at_arms_attack_helper(hero, party, high_threat_enemies,
                                                              enemies_not_dead_already, stun_chance,
                                                              kill_stunned_enemy=True, cant_kill_enemy_ok=True)
    # kill an enemy or stun enemy
    if attack is None:
        attack, potential_targets = man_at_arms_attack_helper(hero, party, enemies_not_moved, enemies_not_dead_already,
                                                              stun_chance, kill_stunned_enemy=False)
    if attack is None:
        attack, potential_targets = man_at_arms_attack_helper(hero, party, enemies_not_dead_already,
                                                              enemies_not_dead_already, stun_chance,
                                                              kill_stunned_enemy=False)
    # use bolster if can't kill or stun anything (maybe want to run guard here instead)
    attack = 'bolster' if attack is None and 'bolster' in hero.skills and hero.bolster_count == 0 else attack

    if attack is None:
        attack, potential_targets = man_at_arms_attack_helper(hero, party, enemies_not_dead_already,
                                                              enemies_not_dead_already, stun_chance,
                                                              kill_stunned_enemy=True, cant_kill_enemy_ok=True)

    if attack == 'swap':
        swap_hero(hero, swap_distance, UpdatedPartyOrder, debug=Debug)
    elif attack == 'rampart':
        find_target_and_stun(hero, potential_targets, attack, stun_chance, UpdatedPartyOrder, target)
    elif attack == 'defender':
        party.sort(key=lambda k: k.currentHp)
        heal_target(hero, target=party[0], attack=attack, debug=Debug)
    elif attack == 'bolster':
        heal_target(hero, target=party[0], attack=attack, debug=Debug)
    elif attack == 'command':
        target = next((ally for ally in party if (ally.rank == 1 or ally.rank == 2)
                       and ally.heroClass != 'man_at_arms'), party[0])
        heal_target(hero, target, attack=attack, debug=Debug)
    else:
        # Find target and attack enemy
        if attack is not None:
            list_of_attacks.insert(0, attack)
        find_target_and_attack(raid_info, potential_targets, hero, party, list_of_attacks, UpdatedPartyOrder)

    # heal, buff, or swap if can't hit enemies with any attacks
    if not attack_completed:
        attack, swap_distance = man_at_arms_stall_helper(hero, party_sorted_by_rank, swap_distance)
        if attack == 'swap':
            swap_hero(hero, swap_distance, UpdatedPartyOrder, debug=Debug)
        elif attack == 'rampart':
            find_target_and_stun(hero, potential_targets, attack, stun_chance, UpdatedPartyOrder, target)
        elif attack == 'defender':
            party.sort(key=lambda k: k.currentHp)
            heal_target(hero, target=party[0], attack=attack, debug=Debug)
        elif attack == 'bolster':
            heal_target(hero, target=party[0], attack=attack, debug=Debug)
        elif attack == 'command':
            target = next((ally for ally in party if (ally.rank == 1 or ally.rank == 2)
                           and ally.heroClass != 'man_at_arms'), party[0])
            heal_target(hero, target, attack=attack, debug=Debug)


def houndmaster_attack_helper(hero, list_of_enemies, enemies_not_dead_already, stun_chance,
                              kill_stunned_enemy, cant_kill_enemy_ok=False):
    attack = None
    if 'hounds_harry' in hero.skills and any(enemy.effectiveHp <= 2 and (not enemy.stunned or kill_stunned_enemy)
                                             for enemy in list_of_enemies) \
            and sum(enemy.effectiveHp > 3 for enemy in enemies_not_dead_already) >= 1:
        attack = 'hounds_harry'
    elif 'hounds_rush' in hero.skills and hero.rank in AttackSkills['hounds_rush'][0] \
            and any(enemy.lowHp
                    and ((not enemy.stunned or (enemy.stunned and kill_stunned_enemy))
                         and any(rank in AttackSkills['hounds_rush'][1] for rank in enemy.rank))
                    for enemy in list_of_enemies):
        attack = 'hounds_rush'
    elif 'blackjack' in hero.skills and hero.rank in AttackSkills['blackjack'][0] \
            and any(any(rank in AttackSkills['blackjack'][1] for rank in enemy.rank)
                    and stun_chance - enemy.stunResist >= 50 and not enemy.stunned for enemy in list_of_enemies):
        attack = 'blackjack'
    elif 'hounds_rush' in hero.skills and hero.rank in AttackSkills['hounds_rush'][0] and cant_kill_enemy_ok \
            and any(any(rank in AttackSkills['hounds_rush'][1] for rank in enemy.rank) for enemy in list_of_enemies):
        attack = 'hounds_rush'
    return attack, list_of_enemies


def houndmaster_action(party_sorted_by_rank, hero, raid_info, enemy_formation):
    """[ Ideal skill load-out: hounds rush, any 3 - cry havoc, lick wounds, hounds harry, blackjack, guard dog ]"""
    # Note: cry_havoc = howl
    global UpdatedPartyOrder
    party = party_sorted_by_rank
    current_round = raid_info['battle']['round']
    list_of_attacks = ['hounds_rush', 'hounds_harry']
    stall_count = raid_info['battle']['round_stall_count']
    stall_accelerated = raid_info['battle']['previous_stall_accelerated']
    stall = False if stall_count >= 2 or stall_accelerated else True
    attack, stun_chance, target = None, None, None
    swap_distance = -1

    enemies_not_dead_already = [enemy for enemy in enemy_formation if not enemy.alreadyGoingToDie]
    enemies_not_moved = [enemy for enemy in enemies_not_dead_already if not enemy.alreadyMoved]
    high_threat_enemies = [enemy for enemy in enemies_not_dead_already if enemy.threat >= 4]
    very_high_threat_enemies = [enemy for enemy in high_threat_enemies if enemy.threat >= 7]
    very_high_threat_not_moved = [enemy for enemy in very_high_threat_enemies if not enemy.alreadyMoved]
    high_threat_not_moved = [enemy for enemy in high_threat_enemies if not enemy.alreadyMoved]
    potential_targets = enemy_formation
    enemy = enemies_not_dead_already[0] if len(enemies_not_dead_already) > 0 else None

    if 'blackjack' in hero.skills:
        stun_level = hero.skills['blackjack']
        stun_chance = AttackSkills['blackjack'][2][stun_level]

    # heal if on deaths door or going to be on deaths door
    if (hero.effectiveHp == 0 or hero.currentHp == 0) \
            and 'lick_wounds' in hero.skills and hero.rank in AttackSkills['lick_wounds'][0]:
        attack = 'lick_wounds'
    # defend ally who is on deaths door
    # future - defend ally to protect from stress damage ???
    if attack is None and len(enemies_not_dead_already) > 0 \
            and 'guard_dog' in hero.skills and any(ally.currentHp == 0 for ally in party) \
            and (len(enemies_not_dead_already) > 1 or not enemy.stunned):
        attack = 'guard_dog'
    # stall if only one weak enemy left and need to heal or stress heal
    if attack is None \
            and (len(enemies_not_dead_already) == 0
                 or (len(enemies_not_dead_already) == 1
                     and (stall
                          or (enemy.canBeKilledIn1Hit
                              and any(ally is not hero and not ally.already_moved and not ally.stunned
                                      and (((ally.rank == 1 or ally.rank == 2) and (ally.heroClass in FrontLineClasses))
                                           or (ally.heroClass not in BackLineClasses and ally.rank != 4))
                                      for ally in party))) and current_round < 8)) \
            and ((any(ally.percentHp < 80 for ally in party) and any(ally.healer for ally in party))
                 or (any(ally.stress > 0 for ally in party) and any(ally.stressHealer for ally in party))):
        if 'blackjack' in hero.skills and len(enemies_not_dead_already) == 1 \
                and hero.rank in AttackSkills['blackjack'][0] \
                and any(rank in AttackSkills['blackjack'][1] for rank in enemy.rank) \
                and not enemy.stunned and stun_chance - enemy.stunResist >= 50 \
                and (not enemy.canBeKilledIn1Hit or enemy.threat >= 4):
            attack = 'blackjack'
        elif len(enemies_not_dead_already) == 0 or (enemy.stunned or enemy.threat < 4):
            if 'howl' in hero.skills and hero.rank in AttackSkills['howl'][0] \
                    and any(ally.stress > 40 for ally in party):
                attack = 'howl'
            elif 'lick_wounds' and hero.percentHp < 30 and hero.currentHp != hero.maxHp \
                    and hero.rank in AttackSkills['lick_wounds'][0]:
                attack = 'lick_wounds'
            elif 'howl' in hero.skills and hero.rank in AttackSkills['howl'][0] \
                    and any(ally.stress > 0 for ally in party):
                attack = 'howl'
            elif 'lick_wounds' and hero.percentHp < 100 and hero.currentHp != hero.maxHp \
                    and hero.rank in AttackSkills['lick_wounds'][0]:
                attack = 'lick_wounds'
            elif 'howl' in hero.skills and hero.rank in AttackSkills['howl'][0]:
                attack = 'howl'
            elif 'lick_wounds' and hero.rank in AttackSkills['lick_wounds'][0]:
                attack = 'lick_wounds'
            else:
                attack = 'swap'
                swap_distance = 1 if hero.rank == 2 and party[2].heroClass == 'vestal' \
                    or party[2].heroClass == 'jester' or party[2].heroClass == 'houndmaster' else -1

    # kill an enemy or stun very high threat enemy
    if attack is None:
        attack, potential_targets = houndmaster_attack_helper(hero, very_high_threat_not_moved,
                                                              enemies_not_dead_already, stun_chance,
                                                              kill_stunned_enemy=False)
    if attack is None:
        attack, potential_targets = houndmaster_attack_helper(hero, very_high_threat_enemies, enemies_not_dead_already,
                                                              stun_chance, kill_stunned_enemy=True,
                                                              cant_kill_enemy_ok=True)
    # kill an enemy or stun high threat enemy
    if attack is None:
        attack, potential_targets = houndmaster_attack_helper(hero, high_threat_not_moved, enemies_not_dead_already,
                                                              stun_chance, kill_stunned_enemy=False)
    # swap if need to fix position
    attack = 'swap' if attack is None and hero.rank == 1 else attack
    attack = 'swap' if attack is None and hero.rank == 2 and (party[2].heroClass == 'hellion'
                                                              or party[2].heroClass == 'flagellant'
                                                              or party[2].heroClass == 'leper') else attack
    if attack is None and ((hero.rank == 2 and party[0].heroClass == 'vestal')
                           or (hero.rank == 3 and party[1].heroClass in BackLineClasses
                               and party[1].heroClass != 'houndmaster')):
        attack = 'swap'
        swap_distance = 1

    # attack high threat enemy
    if attack is None:
        attack, potential_targets = houndmaster_attack_helper(hero, high_threat_enemies, enemies_not_dead_already,
                                                              stun_chance, kill_stunned_enemy=True,
                                                              cant_kill_enemy_ok=True)
    # stress heal if main threats are dealt with
    if attack is None and 'howl' in hero.skills and hero.rank in AttackSkills['howl'][0] \
            and len(enemies_not_dead_already) < 3 and any(ally.stress > 0 for ally in party) \
            and not any(enemy.threat > 2 or (enemy.threat > 3 and not enemy.stunned)
                        for enemy in enemies_not_dead_already):
        attack = 'howl'

    # kill an enemy or stun enemy
    if attack is None:
        attack, potential_targets = houndmaster_attack_helper(hero, enemies_not_moved, enemies_not_dead_already,
                                                              stun_chance, kill_stunned_enemy=False)
    if attack is None:
        attack, potential_targets = houndmaster_attack_helper(hero, enemies_not_dead_already, enemies_not_dead_already,
                                                              stun_chance, kill_stunned_enemy=True,
                                                              cant_kill_enemy_ok=True)

    if attack == 'swap':
        swap_hero(hero, swap_distance, UpdatedPartyOrder, debug=Debug)
    elif attack == 'blackjack':
        find_target_and_stun(hero, potential_targets, attack, stun_chance, UpdatedPartyOrder, target)
    elif attack == 'howl' or attack == 'lick_wounds':
        heal_target(hero, target=hero, attack=attack, debug=Debug)
    elif attack == 'guard_dog':
        party.sort(key=lambda k: k.currentHp)
        heal_target(hero, target=party[0], attack=attack, debug=Debug)
    else:
        # Find target and attack enemy
        if attack is not None:
            list_of_attacks.insert(0, attack)
        find_target_and_attack(raid_info, potential_targets, hero, party, list_of_attacks, UpdatedPartyOrder)


def shieldbreaker_attack_helper(hero, party, list_of_enemies, kill_stunned_enemy, cant_kill_enemy_ok=False):
    attack = None
    if 'adders_kiss' in hero.skills and (party[1].heroClass not in BackLineClasses or party[1].heroClass == 'highwayman') \
            and hero.rank == 1 and any(not enemy.isTank
                                       and ((not enemy.stunned or (enemy.stunned and kill_stunned_enemy))
                                            and any(rank in AttackSkills['adders_kiss'][1] for rank in enemy.rank))
                                       for enemy in list_of_enemies):
        attack = 'adders_kiss'
    elif 'pierce' in hero.skills and hero.rank in AttackSkills['pierce'][0] \
            and any(enemy.canBeKilledIn1Hit and ((not enemy.stunned or (enemy.stunned and kill_stunned_enemy))
                    and any(rank in AttackSkills['pierce'][1] for rank in enemy.rank)) for enemy in list_of_enemies):
        attack = 'pierce'
    elif 'adders_kiss' in hero.skills and hero.rank == 1 and cant_kill_enemy_ok \
            and (party[1].heroClass not in BackLineClasses or party[1].heroClass == 'highwayman') \
            and any(any(rank in AttackSkills['adders_kiss'][1] for rank in enemy.rank) for enemy in list_of_enemies):
        attack = 'adders_kiss'
    elif 'pierce' in hero.skills and hero.rank in AttackSkills['pierce'][0] and cant_kill_enemy_ok \
            and any(any(rank in AttackSkills['pierce'][1] for rank in enemy.rank) for enemy in list_of_enemies):
        attack = 'pierce'
    return attack, list_of_enemies


def shieldbreaker_action(party_sorted_by_rank, hero, raid_info, enemy_formation):
    """[ Ideal skill load-out: pierce, adders_kiss, any 2 - puncture, impale, expose, serpent_sway ]"""
    # note: puncture == break_guard
    global UpdatedPartyOrder
    party = party_sorted_by_rank
    current_round = raid_info['battle']['round']
    list_of_attacks = ['pierce', 'break_guard']
    stall_count = raid_info['battle']['round_stall_count']
    stall_accelerated = raid_info['battle']['previous_stall_accelerated']
    stall = False if stall_count >= 2 or stall_accelerated else True
    attack = None
    swap_distance = 1

    enemies_not_dead_already = [enemy for enemy in enemy_formation if not enemy.alreadyGoingToDie]
    enemies_not_moved = [enemy for enemy in enemies_not_dead_already if not enemy.alreadyMoved]
    high_threat_enemies = [enemy for enemy in enemies_not_dead_already if enemy.threat >= 4]
    very_high_threat_enemies = [enemy for enemy in high_threat_enemies if enemy.threat >= 7]
    very_high_threat_not_moved = [enemy for enemy in very_high_threat_enemies if not enemy.alreadyMoved]
    high_threat_not_moved = [enemy for enemy in high_threat_enemies if not enemy.alreadyMoved]
    potential_targets = enemy_formation
    enemy = enemies_not_dead_already[0] if len(enemies_not_dead_already) > 0 else None

    # stall if only one weak enemy left and need to heal or stress heal
    if (len(enemies_not_dead_already) == 0
        or (len(enemies_not_dead_already) == 1
            and (stall or (enemy.canBeKilledIn1Hit
                           and any(ally is not hero and not ally.already_moved and not ally.stunned
                                   and (((ally.rank == 1 or ally.rank == 2) and (ally.heroClass in FrontLineClasses))
                                        or (ally.heroClass not in BackLineClasses and ally.rank != 4))
                                   for ally in party))) and current_round < 8)) \
            and ((any(ally.percentHp < 80 for ally in party) and any(ally.healer for ally in party))
                 or (any(ally.stress > 0 for ally in party) and any(ally.stressHealer for ally in party))):
        if len(enemies_not_dead_already) == 0 \
                or (enemies_not_dead_already[0].threat < 4
                    or (enemies_not_dead_already[0].stunned and enemies_not_dead_already[0].canBeKilledIn1Hit)):
            attack = 'swap'
            swap_distance = -1 if hero.rank == 1 or (hero.rank == 3 and (party[1].heroClass == 'hellion' or
                                                                         party[1].heroClass == 'crusader')) else 1
    # kill a very high threat enemy
    if attack is None:
        attack, potential_targets = shieldbreaker_attack_helper(hero, party, very_high_threat_not_moved,
                                                                kill_stunned_enemy=False)
    if attack is None:
        attack, potential_targets = shieldbreaker_attack_helper(hero, party, very_high_threat_enemies,
                                                                kill_stunned_enemy=True, cant_kill_enemy_ok=True)
    # kill a high threat enemy
    if attack is None:
        attack, potential_targets = shieldbreaker_attack_helper(hero, party, high_threat_not_moved,
                                                                kill_stunned_enemy=False)
    # attack high threat enemy
    if attack is None:
        attack, potential_targets = shieldbreaker_attack_helper(hero, party, high_threat_enemies,
                                                                kill_stunned_enemy=True, cant_kill_enemy_ok=True)
    # kill an enemy, threat > 1 not moved
    if attack is None:
        enemies_threat_level_1 = [enemy for enemy in enemies_not_moved if enemy.threat > 1]
        attack, potential_targets = shieldbreaker_attack_helper(hero, party, enemies_threat_level_1,
                                                                kill_stunned_enemy=False)
    # pull a skeleton archer or kill corpse
    if attack is None:
        archers = [enemy for enemy in enemies_not_dead_already if enemy.name == 'Bone Arbalist'
                   and (3 in enemy.rank or 4 in enemy.rank)]
        rank3_archer = next((enemy for enemy in archers if 3 in enemy.rank), None)
        rank4_archer = next((enemy for enemy in archers if 4 in enemy.rank), None)

        if rank4_archer is not None and rank4_archer.canBeKilledIn1Hit \
                and not (rank4_archer.alreadyMoved or rank4_archer.stunned):
            attack = 'pierce'
            potential_targets = [rank4_archer]
        elif rank3_archer is not None and rank3_archer.canBeKilledIn1Hit \
                and not (rank3_archer.alreadyMoved or rank3_archer.stunned):
            attack = 'pierce'
            potential_targets = [rank3_archer]
        elif rank3_archer is not None and not (rank3_archer.alreadyMoved or rank3_archer.stunned) \
                and not any((e.name == 'Corpse' or e.name == 'Large_Corpse') and e.canBeKilledIn1Hit
                            and (1 in e.rank or 2 in e.rank) or (e.name == 'Bone Arbalist' and 2 in e.rank)
                            for e in enemy_formation):
            attack = 'break_guard'
            potential_targets = [rank3_archer]
        elif rank4_archer is not None and not (rank4_archer.alreadyMoved or rank4_archer.stunned) \
                and not any((e.name == 'Corpse' or e.name == 'Large_Corpse') and e.canBeKilledIn1Hit
                            and (1 in e.rank or 2 in e.rank) or (e.name == 'Bone Arbalist' and 2 in e.rank)
                            for e in enemy_formation):
            attack = 'break_guard'
            potential_targets = [rank4_archer]
        elif len(archers) > 0 and any(archer.canBeKilledIn1Hit for archer in archers):
            attack = 'pierce'
            potential_targets = archers

    # kill an enemy
    if attack is None:
        attack, potential_targets = shieldbreaker_attack_helper(hero, party, enemies_not_moved,
                                                                kill_stunned_enemy=False)
    if attack is None:
        attack, potential_targets = shieldbreaker_attack_helper(hero, party, enemies_not_dead_already,
                                                                kill_stunned_enemy=True, cant_kill_enemy_ok=True)

    # Find target and attack enemy
    if attack == 'swap':
        swap_hero(hero, swap_distance, UpdatedPartyOrder, debug=Debug)
    elif attack == 'serpents_sway':
        heal_target(hero, party[0], attack, debug=Debug)
    elif attack is not None:
        list_of_attacks.insert(0, attack)
        find_target_and_attack(raid_info, potential_targets, hero, party, list_of_attacks, UpdatedPartyOrder)
    else:
        find_target_and_attack(raid_info, enemy_formation, hero, party, list_of_attacks, UpdatedPartyOrder)


def hellion_action(party_sorted_by_rank, hero, raid_info, enemy_formation):
    """[ Ideal skill load-out: wicked hack, iron swan, yawp, if it bleeds ]"""
    global UpdatedPartyOrder
    party = party_sorted_by_rank
    current_round = raid_info['battle']['round']
    list_of_attacks = ['iron_swan', 'wicked_hack', 'if_it_bleeds', 'barbaric_yawp']
    stall_count = raid_info['battle']['round_stall_count']
    stall_accelerated = raid_info['battle']['previous_stall_accelerated']
    stall = False if stall_count >= 2 or stall_accelerated else True
    attack, stun_chance = None, None
    swap_distance = 1
    enemies_not_dead_already = [enemy for enemy in enemy_formation if not enemy.alreadyGoingToDie]
    enemy = enemies_not_dead_already[0] if len(enemies_not_dead_already) > 0 else None

    if 'barbaric_yawp' in hero.skills:
        stun_level = hero.skills['barbaric_yawp']
        stun_chance = AttackSkills['barbaric_yawp'][2][stun_level]

    # stall if only one weak enemy left and need to heal or stress heal
    if (len(enemies_not_dead_already) == 0
        or (len(enemies_not_dead_already) == 1
            and (stall or (enemy.canBeKilledIn1Hit
                           and any(ally is not hero and not ally.already_moved and not ally.stunned
                                   and (((ally.rank == 1 or ally.rank == 2) and (ally.heroClass in FrontLineClasses))
                                        or (ally.heroClass not in BackLineClasses and ally.rank != 4))
                                   for ally in party))) and current_round < 8)) \
            and ((any(ally.percentHp < 80 for ally in party) and any(ally.healer for ally in party))
                 or (any(ally.stress > 0 for ally in party) and any(ally.stressHealer for ally in party))):
        if len(enemies_not_dead_already) == 1:
            enemy = enemies_not_dead_already[0]
            if 'barbaric_yawp' in hero.skills and hero.barbaric_yawp_count < 3 and (hero.rank == 1 or hero.rank == 2) \
                    and (1 in enemy.rank or 2 in enemy.rank) and not enemy.stunned \
                    and stun_chance - enemy.stunResist >= 50:
                attack = 'barbaric_yawp'
            elif hero.rank != 1 and (enemy.threat < 4 or (enemy.stunned and enemy.canBeKilledIn1Hit)):
                attack = 'swap'
    # fix if party is out of position
    if attack is None and ((hero.rank == 2 and party[0].heroClass in BackLineClasses)
                           or (hero.rank == 3 and party[1].heroClass not in FrontLineClasses)
                           or (hero.rank == 4 and party[2].heroClass not in FrontLineClasses)):
        attack = 'swap'
    # stun two enemies with yawp if specific conditions are met
    if attack is None and 'barbaric_yawp' in hero.skills and hero.barbaric_yawp_count < 3 \
            and (hero.rank == 1 or hero.rank == 2):
        rank1_enemy = next((enemy for enemy in enemies_not_dead_already if 1 in enemy.rank
                            and not enemy.alreadyMoved), None)
        rank2_enemy = next((enemy for enemy in enemies_not_dead_already if 2 in enemy.rank
                            and 1 not in enemy.rank and not enemy.alreadyMoved), None)
        if rank1_enemy is not None and rank2_enemy is not None:
            high_threat_enemies_in_back = [enemy for enemy in enemies_not_dead_already if enemy.threat >= 4
                                           and 1 not in enemy.rank and 2 not in enemy.rank]
            if len(high_threat_enemies_in_back) == 0 and len(enemies_not_dead_already) < 4 \
                    and not rank1_enemy.stunned and stun_chance - rank1_enemy.stunResist >= 50 \
                    and not rank2_enemy.stunned and stun_chance - rank2_enemy.stunResist >= 50:
                attack = 'barbaric_yawp'

    # Find target and attack enemy
    if attack == 'swap':
        swap_hero(hero, swap_distance, UpdatedPartyOrder, debug=Debug)
    else:
        if attack is not None:
            list_of_attacks.insert(0, attack)
        find_target_and_attack(raid_info, enemy_formation, hero, party, list_of_attacks, UpdatedPartyOrder)


def crusader_action(party_sorted_by_rank, hero, raid_info, enemy_formation):
    """[ Ideal skill load-out: smite, stunning blow, holy lance, inspiring cry ]"""
    global UpdatedPartyOrder
    party = party_sorted_by_rank
    list_of_attacks = ['smite', 'holy_lance']
    stall_count = raid_info['battle']['round_stall_count']
    stall_accelerated = raid_info['battle']['previous_stall_accelerated']
    stall = False if stall_count >= 2 or stall_accelerated else True
    attack, stun_chance, target = None, None, None
    swap_distance = 1

    if 'stunning_blow' in hero.skills:
        stun_level = hero.skills['stunning_blow']
        stun_chance = AttackSkills['stunning_blow'][2][stun_level]

    enemies_not_dead_already = [enemy for enemy in enemy_formation if not enemy.alreadyGoingToDie]
    enemy = enemies_not_dead_already[0] if len(enemies_not_dead_already) > 0 else None

    # stall if only one weak enemy left and need to heal or stress heal
    if (len(enemies_not_dead_already) == 0
        or (len(enemies_not_dead_already) == 1
            and (enemies_not_dead_already[0].threat < 4 or enemies_not_dead_already[0].stunned) and stall)) \
            and ((any(ally.percentHp < 80 for ally in party) and any(ally.healer for ally in party))
                 or (any(ally.stress > 0 for ally in party) and any(ally.stressHealer for ally in party))):
        if len(enemies_not_dead_already) == 1 \
                and not (enemy.name == 'Bone Arbalist' and (3 in enemy.rank or 4 in enemy.rank)):
            enemy = enemies_not_dead_already[0]
            can_stun = stun_chance - enemy.stunResist >= 55
            if 'inspiring_cry' in hero.skills \
                    and (any(ally.effectiveHp == 0 for ally in party)
                         or (enemy.threat <= 2 or enemy.stunned or (enemy.threat < 4 and enemy.canBeKilledIn1Hit)
                             and any(ally.stress > 0 for ally in party))):
                attack = 'inspiring_cry'
            elif (1 == hero.rank or 2 == hero.rank) and (2 in enemy.rank or 1 in enemy.rank) \
                    and not enemy.stunned and can_stun and not enemy.canBeKilledIn1Hit:
                attack = 'stunning_blow'
                target = enemy
            else:
                attack = 'swap' if hero.rank != 1 or (hero.rank == 1 and party[1].heroClass not in BackLineClasses) \
                    else None
                swap_distance = -1 if hero.rank == 1 and party[1].heroClass not in BackLineClasses else 1
    # stress heal if main threat is dealt with, or heal if ally is on deaths door or can stop from reaching deaths door
    if attack is None and stall and 'inspiring_cry' in hero.skills \
            and (any(ally.effectiveHp == 0 for ally in party)
                 or (len(enemies_not_dead_already) < 3 and any(ally.stress > 0 for ally in party)
                     and not any(enemy.threat > 2 or (enemy.threat > 3 and not enemy.stunned)
                                 for enemy in enemies_not_dead_already))):
        attack = 'inspiring_cry'
    # stun enemy if can't kill
    if attack is None and (hero.rank == 1 or hero.rank == 2) and 'stunning_blow' in hero.skills:
        if any(stun_chance - enemy.stunResist >= 55 and not enemy.stunned
               and not enemy.canBeKilledIn1Hit and (1 in enemy.rank or 2 in enemy.rank)
               for enemy in enemies_not_dead_already):
            attack = 'stunning_blow'
    elif attack is None or (hero.rank == 3 or hero.rank == 4):
        # holy lance if rank 3 or 4, and not front line on next rank, and enemy on rank 2
        if any(2 in enemy.rank or 3 in enemy.rank or 4 in enemy.rank for enemy in enemies_not_dead_already) \
                and 'holy_lance' in hero.skills and party[hero.rank-2].heroClass not in FrontLineClasses:
            attack = 'holy_lance'
        elif hero.rank == 3 and party[1] in BackLineClasses \
                or (not any(ally.stress > 0 for ally in party)
                    and party[hero.rank-2].heroClass not in FrontLineClasses):
            attack = 'swap'
        elif 'inspiring_cry' in hero.skills:
            attack = 'inspiring_cry'
        else:
            attack = 'swap'

    if attack == 'swap':
        swap_hero(hero, swap_distance, UpdatedPartyOrder, debug=Debug)
    elif attack == 'stunning_blow':
        find_target_and_stun(hero, enemies_not_dead_already, attack, stun_chance, UpdatedPartyOrder, target)
    elif attack == 'inspiring_cry':
        target = next((ally for ally in party if ally.currentHp == 0), None)
        if target is None:
            target = next((ally for ally in party if ally.effectiveHp == 0), None)
        if target is None:
            party.sort(key=lambda k: k.stress, reverse=True)
            target = party[0]
        heal_target(hero, target, attack, debug=Debug)
    else:
        # Find target and attack enemy
        if attack is not None:
            list_of_attacks.insert(0, attack)
        find_target_and_attack(raid_info, enemy_formation, hero, party, list_of_attacks, UpdatedPartyOrder)


def find_target_and_attack(raid_info, enemy_formation, hero, party, list_of_attacks, party_order):
    global attack_completed
    attack_completed = False
    current_round = raid_info['battle']['round']
    stall_count = raid_info['battle']['round_stall_count']
    stall_accelerated = raid_info['battle']['previous_stall_accelerated']
    stall = False if stall_count >= 2 or stall_accelerated else True
    enemies_not_dead_already = [enemy for enemy in enemy_formation if not enemy.alreadyGoingToDie]
    enemy = enemies_not_dead_already[0] if len(enemies_not_dead_already) > 0 else None

    # filter out skills if hero is not in the correct rank or does not have equipped
    viable_attacks = [attack for attack in list_of_attacks
                      if attack in hero.skills and hero.rank in AttackSkills[attack][0]]

    # stall by attacking corpse if 1 enemy left
    if (len(enemies_not_dead_already) == 0
        or (len(enemies_not_dead_already) == 1
            and (stall or (enemy.canBeKilledIn1Hit
                           and any(ally is not hero and not ally.already_moved and not ally.stunned
                                   and (((ally.rank == 1 or ally.rank == 2) and (ally.heroClass in FrontLineClasses))
                                        or (ally.heroClass not in BackLineClasses and ally.rank != 4))
                                   for ally in party))) and current_round < 8)) \
            and ((any(ally.percentHp < 80 for ally in party) and any(ally.healer for ally in party))
                 or (any(ally.stress > 0 for ally in party) and any(ally.stressHealer for ally in party))):
        if len(enemies_not_dead_already) == 1:
            if ((enemy.threat < 4 and not (enemy.name == 'Bone Arbalist' and (3 in enemy.rank or 4 in enemy.rank))
                 and not enemy.isTank) or (enemy.stunned and not enemy.isTank)):
                targets = [enemy for enemy in enemy_formation if enemy.name == 'Large Corpse' or enemy.name == 'Corpse']
                choose_best_attack(hero, targets, viable_attacks, party_order)
    # if enemy is a very high threat (>=7, stress attacker) and not going to die already
    if not attack_completed:
        targets = [enemy for enemy in enemy_formation if enemy.threat >= 7 and not enemy.alreadyGoingToDie]
        if len(targets) > 0:
            sort_targets(targets)
            choose_best_attack(hero, targets, viable_attacks, party_order)
    # if enemy is a high threat (>=4, high threat) and not going to die already
    if not attack_completed:
        targets = [enemy for enemy in enemy_formation if enemy.threat >= 4 and not enemy.alreadyGoingToDie]
        if len(targets) > 0:
            sort_targets(targets)
            choose_best_attack(hero, targets, viable_attacks, party_order)
    # if enemy isn't stunned, can be killed in one hit, isn't going to die from blight or bleed
    if not attack_completed:
        targets = [enemy for enemy in enemy_formation if not enemy.stunned and not enemy.alreadyGoingToDie
                   and enemy.canBeKilledIn1Hit and enemy.threat > 1]
        if len(targets) > 0:
            sort_targets(targets)
            choose_best_attack(hero, targets, viable_attacks, party_order)
    # if corpse in rank 1 or 2 and enemy in rank 3 is skeleton archer
    if not attack_completed:
        targets = []
        if any(enemy.name == 'Bone Arbalist' and not enemy.alreadyGoingToDie for enemy in enemy_formation):
            if len(enemy_formation) > 2 and 'Bone Arbalist' == enemy_formation[2].name:
                if 'Corpse' == enemy_formation[0].name or 'Large Corpse' == enemy_formation[0].name:
                    targets.append(enemy_formation[0])
                if 'Corpse' == enemy_formation[1].name or 'Large Corpse' == enemy_formation[1].name:
                    targets.append(enemy_formation[1])
            elif 'Large Corpse' == enemy_formation[0].name and 'Bone Arbalist' == enemy_formation[1].name:
                targets.append(enemy_formation[0])
        if len(targets) > 0:
            sort_targets(targets)
            choose_best_attack(hero, targets, viable_attacks, party_order)
    # if enemy is a threat > 1 and not going to die already
    if not attack_completed:
        targets = [enemy for enemy in enemy_formation if enemy.threat > 1 and not enemy.alreadyGoingToDie]
        if len(targets) > 0:
            sort_targets(targets)
            choose_best_attack(hero, targets, viable_attacks, party_order)
    # if enemy isn't stunned, and isn't going to die from blight or bleed
    if not attack_completed:
        targets = [enemy for enemy in enemy_formation if not enemy.stunned and not enemy.alreadyGoingToDie
                   and enemy.threat > 0]
        if len(targets) > 0:
            sort_targets(targets)
            choose_best_attack(hero, targets, viable_attacks, party_order)
    # if isn't going to die from blight or bleed
    if not attack_completed:
        targets = [enemy for enemy in enemy_formation if enemy.threat > 0 and not enemy.alreadyGoingToDie]
        if len(targets) > 0:
            sort_targets(targets)
            choose_best_attack(hero, targets, viable_attacks, party_order)
    # if they're all going to die anyway it doesn't matter
    if not attack_completed:
        choose_best_attack(hero, enemy_formation, viable_attacks, party_order)


def sort_targets(targets):
    if len(targets) > 1:
        # sort enemies first by threat > 1, then by not already_moved/stunned, then threat level, then hp
        targets.sort(key=lambda k: k.effectiveHp)
        targets.sort(key=lambda k: k.threat, reverse=True)
        targets.sort(key=lambda k: (k.threat <= 1, k.alreadyMoved or k.stunned))


def sort_stun_targets(targets):
    if len(targets) > 1:
        # sort enemies first by threat > 1, then by already_moved, then threat level, then rank
        targets.sort(key=lambda k: k.rank, reverse=True)
        targets.sort(key=lambda k: k.threat, reverse=True)
        targets.sort(key=lambda k: (k.threat <= 1, k.alreadyMoved))


def choose_best_attack(hero, targets, list_of_attacks, party_order):
    global Debug, attack_completed
    for attack in list_of_attacks:
        for enemy in targets:
            target = enemy if any(enemy.rank[i] in AttackSkills[attack][1]
                                  for i, ranks in enumerate(enemy.rank)) else None
            if target is not None:
                attack_target(hero, target, attack, Debug)
                attack_completed = True
                break
        if attack_completed:
            if len(AttackSkills[attack]) >= 4:
                print('updating party order!')
                party_order.remove(int(hero.roster_index))
                new_rank = hero.rank + (AttackSkills[attack][3] * -1)
                new_rank = 4 if new_rank > 4 else 1 if new_rank < 1 else new_rank
                party_order.insert(new_rank - 1, int(hero.roster_index))
            break
    # global attack completed will be false if not successful (e.x. see bottom of plague_doctor_action)


def find_target_and_stun(hero, enemies_not_dead_already, attack, stun_chance, party_order, target=None):
    global attack_completed
    attack_completed = False
    list_of_attacks = [attack]

    if target is None:
        potential_targets = [enemy for enemy in enemies_not_dead_already
                             if stun_chance - enemy.stunResist >= 50 and not enemy.stunned
                             and any(rank in AttackSkills[attack][1] for rank in enemy.rank)]
        if hero.heroClass == 'man_at_arms' and len(potential_targets) == 0:
            potential_targets = enemies_not_dead_already

        # if enemy is a very high threat and not going to die already
        if not attack_completed:
            targets = []
            for each_enemy in potential_targets:
                if each_enemy.threat >= 6:
                    targets.append(each_enemy)
            if len(targets) > 0:
                sort_stun_targets(targets)
                choose_best_attack(hero, targets, list_of_attacks, party_order)
        # if enemy is a high threat and not going to die already
        if not attack_completed:
            targets = []
            for each_enemy in potential_targets:
                if each_enemy.threat >= 4:
                    targets.append(each_enemy)
            if len(targets) > 0:
                sort_stun_targets(targets)
                choose_best_attack(hero, targets, list_of_attacks, party_order)
        # if enemy is not going to die already
        if not attack_completed:
            if len(potential_targets) > 0:
                sort_stun_targets(potential_targets)
                choose_best_attack(hero, potential_targets, list_of_attacks, party_order)
    else:
        choose_best_attack(hero, [target], list_of_attacks, party_order)


def select_hero(target_hero_rank, debug):
    global SelectedHeroRank
    c = Controller(debug)
    if SelectedHeroRank != target_hero_rank:
        print(f'Selected hero rank: {SelectedHeroRank}!')
        print(f'New selected hero rank: {target_hero_rank}!')
        c.write(c.down)
        if target_hero_rank < SelectedHeroRank:
            c.write(c.right_bumper, SelectedHeroRank - target_hero_rank)
        else:
            c.write(c.left_bumper, target_hero_rank - SelectedHeroRank)
        SelectedHeroRank = target_hero_rank


def use_campfire_abilities(camping_skills_to_use):
    global Debug, SelectedHeroRank
    c = Controller(Debug)
    print(f'Use Campfire Abilities, selected_hero_rank: {SelectedHeroRank}')
    # r/l bumper to switch heroes
    # starts with left-most hero or last selected hero ???
    # left_stick + a to choose ability and then target, no wrap around
    # need to time.sleep() for ability to be used before selecting next one
    # y to rest (or a if out of points)
    for ability in camping_skills_to_use:
        print(f"using ability {ability['skill']['skill_name']}, hero_rank {ability['skill']['hero_rank']}, "
              f"target_rank {ability['target']}")
        # select hero
        offset = ability['skill']['hero_rank'] - SelectedHeroRank
        if offset > 0:
            c.write(c.left_bumper, offset)
            SelectedHeroRank = ability['skill']['hero_rank']
        elif offset < 0:
            offset *= -1
            c.write(c.right_bumper, offset)
            SelectedHeroRank = ability['skill']['hero_rank']
        # select ability
        c.write(c.left_stick_left, 3)
        time.sleep(.1)
        offset = ability['skill']['skill_slot']
        c.write(c.left_stick_right, offset)
        # select target if applicable
        if ability['target'] > 0:
            c.write(c.a)
            c.write(c.left_stick_right, 4)
            c.write(c.left_stick_left, ability['target'] - 1)
        # use ability
        c.write(c.d_pad_left, 2)  # necessary to make sure button press goes through
        c.write(c.a)
        time.sleep(2)  # give enough time for animation to complete
        c.write(c.b, 3)  # press button to accept dialogue prompt


class Enemy:
    def __init__(self, enemy_info, index, rank, difficulty, already_moved=False):
        self.index = int(index)
        self.battleId = enemy_info['data']['battle_guid']
        self.name = enemy_info['data']['actor']['name']
        self.level = difficulty - 1
        self.threat = Monsters[self.name]['threat']
        self.currentHp = enemy_info['data']['actor']['current_hp']
        self.maxHp = Monsters[self.name]['hp'][self.level]
        self.rank = rank
        self.high_prot = True if self.name == 'Sea Maggot' else False
        self.stunned = True if enemy_info['data']['actor']['stunned'] > 0 else False
        buff_group = enemy_info['data']['actor']['buff_group']
        self.blightAmount = sum((buff['amount'] for buff in buff_group.values() if buff['stat_type'] == 4), 0)
        self.blightDuration = max(buff['duration'] for buff in buff_group.values() if buff['stat_type'] == 4) \
            if any(buff['stat_type'] == 4 for buff in buff_group.values()) else 0
        self.bleedAmount = sum((buff['amount'] for buff in buff_group.values() if buff['stat_type'] == 5), 0)
        self.bleedDuration = max(buff['duration'] for buff in buff_group.values() if buff['stat_type'] == 5) \
            if any(buff['stat_type'] == 5 for buff in buff_group.values()) else 0
        self.damageOnNextTurn = self.bleedAmount + self.blightAmount
        self.damageOnNextTwoTurns = (2*self.bleedAmount if self.bleedDuration > 1 else self.bleedAmount) \
            + (2*self.blightAmount if self.blightDuration > 1 else self.blightAmount)
        self.effectiveHp = self.currentHp - self.damageOnNextTurn if not self.stunned \
            else self.currentHp - self.damageOnNextTwoTurns
        self.percentHpRemain = (self.effectiveHp / self.maxHp) * 100
        self.isTank = True if (self.level == 0 and self.effectiveHp > 14) \
            or (self.level == 1 and self.effectiveHp > 19) or (self.level == 2 and self.effectiveHp > 25) else False
        self.canBeKilledIn1Hit = True \
            if (((self.effectiveHp <= 8 and not self.high_prot)
                 or (self.effectiveHp <= 2 and self.high_prot)) and self.level == 0) \
            or (((self.effectiveHp <= 11 and not self.high_prot)
                 or (self.effectiveHp <= 3 and self.high_prot)) and self.level == 1) \
            or (((self.effectiveHp <= 16 and not self.high_prot)
                 or (self.effectiveHp <= 4 and self.high_prot)) and self.level == 2) else False
        self.lowHp = True \
            if (((self.effectiveHp <= 6 and not self.high_prot)
                 or (self.effectiveHp <= 1 and self.high_prot)) and self.level == 0) \
            or (((self.effectiveHp <= 8 and not self.high_prot)
                 or (self.effectiveHp <= 2 and self.high_prot)) and self.level == 1) \
            or (((self.effectiveHp <= 12 and not self.high_prot)
                 or (self.effectiveHp <= 3 and self.high_prot)) and self.level == 2) else False
        self.alreadyMoved = already_moved
        self.alreadyGoingToDie = self.effectiveHp <= 0 or self.threat == 0
        self.stunResist = Monsters[self.name]['stun_resist'][self.level]
        for each_buff in buff_group.values():
            if each_buff['stat_sub_type'] == 'stun':
                self.stunResist += (each_buff['amount'] * 100)


def get_enemy_formation(raid_info, turn_order, difficulty):
    enemy_formation = []
    next_rank = 1
    for index, enemy_info in raid_info['battle']['enemies'].items():
        name = enemy_info['data']['actor']['name']
        monster_id = str(enemy_info['data']['battle_guid'])
        if Monsters[name]['size'] == 1:
            rank = [next_rank]
            next_rank += 1
        elif Monsters[name]['size'] == 2:
            rank = [next_rank, next_rank+1]
            next_rank += 2
        elif Monsters[name]['size'] == 3:
            rank = [next_rank, next_rank+1, next_rank+2]
            next_rank += 3
        else:
            rank = [1, 2, 3, 4]
        enemy_turn = \
            next((turn for turn in turn_order if 'monster_id' in turn and turn['monster_id'] == int(monster_id)), None)
        enemy_formation.append(
            Enemy(enemy_info, index, rank, difficulty, True if enemy_turn is None else enemy_turn['already_moved']))
    return enemy_formation
