from .Items import Items

StartingPartyOrder = None


class Party:
    def __init__(self, roster_info, party_order=None, turn_order=None):
        global StartingPartyOrder
        StartingPartyOrder = party_order if StartingPartyOrder is None else StartingPartyOrder
        _heroes = []
        for roster_index, hero in roster_info['heroes'].items():
            hero_data = hero['hero_file_data']['raw_data']['base_root']
            if hero_data['roster.status'] == 1:
                already_moved = next((turn_order[i]['already_moved']
                                      for i, turn in enumerate(turn_order) if 'hero_id' in turn_order[i]
                                      and turn_order[i]['hero_id'] == roster_index), None) \
                    if turn_order is not None else None
                rank = self.get_rank(roster_index, party_order)
                _heroes.append(Hero(hero_data, roster_index, rank, already_moved))
        self.heroes = _heroes
        self.partyOrder = party_order
        self.startingPartyOrder = StartingPartyOrder

    @staticmethod
    def get_rank(roster_index, party_order):
        for i in range(len(party_order)):  # ex. [3,1,2]
            if party_order[i] == int(roster_index):
                return i + 1
        return 0


class Hero:
    def __init__(self, hero_data, roster_index, rank, already_moved=None):
        self.roster_index = roster_index
        self.name = hero_data['actor']['name']
        self.heroClass = hero_data['heroClass']
        self.resolveXp = hero_data['resolveXp']
        resolve_level = 0
        if self.resolveXp >= 8:
            resolve_level = 2
        elif self.resolveXp >= 2:
            resolve_level = 1
        self.resolveLevel = resolve_level
        self.weaponRank = hero_data['weapon_rank']
        self.armorRank = hero_data['armour_rank']
        self.stress = hero_data['m_Stress']
        self.currentHp = hero_data['actor']['current_hp']
        self.rank = rank
        self.stunned = False if hero_data['actor']['stunned'] == 0 else True
        self.already_moved = already_moved
        self.buffs = hero_data['actor']['buff_group']
        self.blightAmount = sum((buff['amount'] for buff in self.buffs.values() if buff['stat_type'] == 4), 0)
        self.blightDuration = max(buff['duration'] for buff in self.buffs.values() if buff['stat_type'] == 4) \
            if any(buff['stat_type'] == 4 for buff in self.buffs.values()) else 0
        self.bleedAmount = sum((buff['amount'] for buff in self.buffs.values() if buff['stat_type'] == 5), 0)
        self.bleedDuration = max(buff['duration'] for buff in self.buffs.values() if buff['stat_type'] == 5) \
            if any(buff['stat_type'] == 5 for buff in self.buffs.values()) else 0
        self.damageOnNextTurn = self.bleedAmount + self.blightAmount
        self.effectiveHp = self.currentHp - self.damageOnNextTurn
        self.damageOverTime = self.bleedAmount * self.bleedDuration + self.blightAmount * self.blightDuration
        self.campingSkills = hero_data['skills']['selected_camping_skills']
        quirks, diseases = [], []
        for quirk, quirk_data in hero_data['quirks'].items():
            if quirk in Diseases:
                rating = Diseases[quirk]['default_rating']
                diseases.append({'name': quirk, 'rating': rating})
            else:
                rating = Quirks[quirk]['default_rating']
                requirement = Quirks[quirk]['requirement']
                effect = Quirks[quirk]['effect']
                if (requirement == 'melee' and 'melee' not in HeroClasses[self.heroClass]['attack']) \
                        or (requirement == 'ranged' and 'ranged' not in HeroClasses[self.heroClass]['attack']) \
                        or (effect is not None and 'heal' in effect
                            and 'hp' not in HeroClasses[self.heroClass]['heal']) \
                        or (effect is not None and 'stress_heal' in effect
                            and 'stress' not in HeroClasses[self.heroClass]['heal']) \
                        or (effect is not None and 'plague_doctor' == self.heroClass and len(effect) == 1
                            and 'dmg' in effect):
                    if rating > 0:  # positive quirk
                        rating = 1
                    else:  # negative quirk
                        rating = -1
                elif 'plague_doctor' == self.heroClass:  # plague_doctor doesn't use dmg
                    if quirk == 'risktaker':
                        rating = -7
                    elif quirk == 'hatred_of_unholy':
                        rating = 5
                    elif 'hatred' in quirk:
                        rating = 6
                    elif requirement is not None and ('warrens' in requirement or 'weald' in requirement) \
                            and not ('ruins' in requirement or 'cove' in requirement):
                        if rating > 0:  # positive quirk
                            rating = 1
                        else:  # negative quirk
                            rating = -1
                    elif requirement is not None and ('cove' in requirement or 'ruins' in requirement):
                        if rating > 0:  # positive quirk
                            rating += 1
                        else:  # negative quirk
                            rating -= 1
                # we like to use the crusader in the ruins
                elif 'crusader' == self.heroClass and requirement is not None \
                        and ('ruins' in requirement or 'unholy' in requirement):
                    if rating > 0:  # positive quirk
                        rating += 1
                    elif rating < 0:  # negative quirk
                        rating -= 1
                quirks.append({'name': quirk, 'locked': quirk_data['is_locked'], 'rating': rating})
        self.quirks = quirks
        self.diseases = diseases
        self.trinkets = [trinket['id'] for trinket in hero_data['trinkets']['items'].values()]
        self.skills = hero_data['skills']['selected_combat_skills']
        self.healer = True if self.heroClass == 'vestal' or self.heroClass == 'occultist' \
            or (self.heroClass == 'arbalest' and 'battlefield_bandage' in self.skills) else False
        self.stressHealer = True if (self.heroClass == 'crusader' and 'inspiring_cry' in self.skills) \
            or (self.heroClass == 'jester' and 'inspiring_tune' in self.skills) \
            or (self.heroClass == 'houndmaster' and 'cry_havoc' in self.skills) else False
        hp_modifier, spd_modifier = 0, 0
        for quirk in self.quirks:
            quirk_effects = Quirks[quirk['name']]['effect']
            if quirk_effects is not None and 'hp' in quirk_effects:
                hp_modifier += quirk_effects['hp']
            if quirk_effects is not None and 'spd' in quirk_effects:
                spd_modifier += quirk_effects['spd']
        for disease in self.diseases:
            disease_effects = Diseases[disease['name']]['effect']
            if disease_effects is not None and 'hp' in disease_effects:
                hp_modifier += disease_effects['hp']
            if disease_effects is not None and 'spd' in disease_effects:
                spd_modifier += disease_effects['spd']
        for trinket in self.trinkets:
            trinket_effects = None if 'pos' not in Items[trinket] else Items[trinket]['pos']
            if trinket_effects is not None and 'hp' in trinket_effects:
                hp_modifier += trinket_effects['hp']
            if trinket_effects is not None and 'spd' in trinket_effects:
                spd_modifier += trinket_effects['spd']
            trinket_effects = None if 'neg' not in Items[trinket] else Items[trinket]['neg']
            if trinket_effects is not None and 'hp' in trinket_effects:
                hp_modifier += trinket_effects['hp']
            if trinket_effects is not None and 'spd' in trinket_effects:
                spd_modifier += trinket_effects['spd']
        # future - take buffs/debuffs and crimson curse into account for maxHp
        self.maxHp = HeroClasses[self.heroClass]['maxHp'][self.armorRank] * (100 + hp_modifier) / 100
        self.percentHp = (self.effectiveHp / self.maxHp) * 100
        self.OOCPercentHp = ((self.currentHp - self.damageOverTime) / self.maxHp) * 100  # out-of-combat
        self.traps_skill = HeroClasses[self.heroClass]['traps_base']  # future - take items into account ?
        self.speed = HeroClasses[self.heroClass]['speed'][self.weaponRank] + spd_modifier
        self.crimsonCurse = None
        self.darkestDungeon = hero_data['number_of_successful_darkest_dungeon_quests']
        if self.heroClass == 'plague_doctor':
            self.emboldening_vapours_count = hero_data['actor']['battle_limited_combat_skill_uses']['1857096087'] \
                if 'battle_limited_combat_skill_uses' in hero_data['actor'] \
                   and '1857096087' in hero_data['actor']['battle_limited_combat_skill_uses'] else 0
            self.blinding_gas_count = hero_data['actor']['battle_limited_combat_skill_uses']['1706138973'] \
                if 'battle_limited_combat_skill_uses' in hero_data['actor'] \
                   and '1706138973' in hero_data['actor']['battle_limited_combat_skill_uses'] else 0
        elif self.heroClass == 'hellion':
            self.barbaric_yawp_count = hero_data['actor']['battle_limited_combat_skill_uses']['-621445690'] \
                if 'battle_limited_combat_skill_uses' in hero_data['actor'] \
                   and '-621445690' in hero_data['actor']['battle_limited_combat_skill_uses'] else 0
        elif self.heroClass == 'man_at_arms':
            self.bolster_count = hero_data['actor']['battle_limited_combat_skill_uses']['-1101377553'] \
                if 'battle_limited_combat_skill_uses' in hero_data['actor'] \
                   and '-1101377553' in hero_data['actor']['battle_limited_combat_skill_uses'] else 0

    def update_hp(self, percent_hp):
        self.currentHp += self.maxHp * percent_hp
        self.currentHp = self.maxHp if self.currentHp > self.maxHp else self.currentHp
        self.effectiveHp = self.currentHp - self.damageOnNextTurn
        self.percentHp = (self.effectiveHp / self.maxHp) * 100
        self.OOCPercentHp = ((self.currentHp - self.damageOverTime) / self.maxHp) * 100  # out-of-combat


CampingSkills = {
    # abomination
    'anger_management':    {'cost': 3, 'target': 'any', 'effect': {}},
    'psych_up':            {'cost': 4, 'target': 'any', 'effect': {}},
    'the_quickening':      {'cost': 3, 'target': 'any', 'effect': {}},
    'eldritch_blood':      {'cost': 3, 'target': 'any', 'effect': {}},
    # antiquarian
    'resupply':            {'cost': 2, 'target': 'any', 'effect': {}},
    'trinket_scrounge':    {'cost': 2, 'target': 'any', 'effect': {}},
    'strange_powders':     {'cost': 2, 'target': 'any', 'effect': {}},
    'curious_incantation': {'cost': 2, 'target': 'any', 'effect': {}},
    # arbalest/musketeer
    'restring_crossbow':    {'cost': 3, 'target': 'any', 'effect': {}},
    'clean_musket':         {'cost': 3, 'target': 'any', 'effect': {}},
    'field_dressing':       {'cost': 2, 'target': 'any', 'effect': {}},
    'marching_plan':        {'cost': 3, 'target': 'any', 'effect': {}},
    'triage':               {'cost': 3, 'target': 'any', 'effect': {}},
    # bounty_hunter
    'this_is_how_we_do_it': {'cost': 2, 'target': 'any', 'effect': {}},
    'tracking':             {'cost': 2, 'target': 'any', 'effect': {}},
    'planned_takedown':     {'cost': 4, 'target': 'any', 'effect': {}},
    'scout_ahead':          {'cost': 3, 'target': 'any', 'effect': {}},
    # crusader
    'unshakeable_leader':   {'cost': 2, 'target': 'self', 'effect': {'stress_resist': 25}},
    'stand_tall':           {'cost': 3, 'target': 'ally', 'effect': {'stress_heal': 15, 'heal_mortality': ''}},
    'zealous_speech':       {'cost': 5, 'target': 'all', 'effect': {'stress_heal': 15, 'stress_resist': 15}},
    'zealous_vigil':        {'cost': 4, 'target': 'self', 'effect': {'stress_heal': 25, 'no_ambush': ''}},
    # grave_robber
    'snuff_box':     {'cost': 3, 'target': 'any', 'effect': {}},
    'night_moves':   {'cost': 2, 'target': 'any', 'effect': {}},
    'pilfer':        {'cost': 1, 'target': 'any', 'effect': {}},
    # hellion
    'battle_trance':   {'cost': 3, 'target': 'any', 'effect': {}},
    'revel':           {'cost': 3, 'target': 'any', 'effect': {}},
    'reject_the_gods': {'cost': 2, 'target': 'any', 'effect': {}},
    'sharpen_spear':   {'cost': 3, 'target': 'self', 'effect': {'crit': 10}},
    # highwayman
    'uncatchable': {'cost': 4, 'target': 'self', 'effect': {'melee_buff': '', 'spd': 2}},  # unparalleled_finesse
    'clean_guns':           {'cost': 4, 'target': 'self', 'effect': {'ranged_buff': ''}},
    'bandits_sense':        {'cost': 4, 'target': 'self', 'effect': {'no_ambush': ''}},
    # houndmaster
    'hounds_watch':      {'cost': 4, 'target': 'self', 'effect': {'no_ambush': ''}},
    'therapy_dog':       {'cost': 3, 'target': 'allies', 'effect': {'stress_heal': 10, 'stress_resist': 10}},
    'mans_best_friend':  {'cost': 2, 'target': 'self', 'effect': {'stress_heal': 20}},
    'release_the_hound': {'cost': 4, 'target': 'self', 'effect': {'scout': 30}},
    # jester
    'turn_back_time': {'cost': 3, 'target': 'ally', 'effect': {'stress_heal': 30}},
    'every_rose': {'cost': 3, 'target': 'allies', 'effect': {'stress_heal': 15, 'stress_resist': 15}},  # every_rose_has_its_thorn
    'tigers_eye': {'cost': 3, 'target': 'ally', 'effect': {'acc': 10, 'crit': 8}},
    'mockery':    {'cost': 2, 'target': 'any', 'effect': {}},
    # leper
    'let_the_mask_down': {'cost': 2, 'target': 'any', 'effect': {}},
    'bloody_shroud':     {'cost': 2, 'target': 'any', 'effect': {}},
    'reflection':        {'cost': 2, 'target': 'any', 'effect': {}},
    'quarantine':        {'cost': 2, 'target': 'any', 'effect': {}},
    # man-at-arms
    'maintain_equipment': {'cost': 4, 'target': 'self', 'effect': {'dmg': 15, 'prot': 15}},
    'tactics':            {'cost': 4, 'target': 'all', 'effect': {'dodge': 10, 'crit': 5}},
    'instruction':        {'cost': 3, 'target': 'ally', 'effect': {'acc': 10, 'spd': 3}},
    'weapons_practice':   {'cost': 4, 'target': 'allies', 'effect': {'dmg': 10, 'crit': 8}},  # 75% chance for crit buff
    # occultist
    'abandon_hope':        {'cost': 1, 'target': 'any', 'effect': {}},
    'dark_ritual':         {'cost': 4, 'target': 'any', 'effect': {}},
    'dark_strength':       {'cost': 2, 'target': 'any', 'effect': {}},
    'unspeakable_commune': {'cost': 3, 'target': 'any', 'effect': {}},
    # plague_doctor
    'experimental_vapours': {'cost': 4, 'target': 'ally', 'effect': {'heal': 50}},
    'leeches':              {'cost': 3, 'target': 'ally', 'effect': {'heal': 15, 'cure_disease': '', 'heal_blight': ''}},
    'preventative_medicine': {'cost': 1, 'target': 'self', 'effect': {'cure_disease': ''}},  # the_cure
    'self_medicate':         {'cost': 3, 'target': 'self', 'effect': {'stress_heal': 10, 'heal': 20, 'acc': 10,
                                                                      'heal_blight': '', 'heal_bleed': ''}},
    # vestal
    'bless':     {'cost': 3, 'target': 'ally', 'effect': {'acc': 10, 'dodge': 10}},
    'chant':     {'cost': 3, 'target': 'ally', 'effect': {}},
    'pray':      {'cost': 3, 'target': 'allies', 'effect': {'stress_heal': 5, 'prot': 5}},  # 15 if religious
    'sanctuary': {'cost': 4, 'target': 'all', 'effect': {'no_ambush': ''}},  # heal and stress heal if mortality debuff
    # flagellant
    'lashs_anger':  {'cost': 2, 'target': 'any', 'effect': {}},
    'lashs_solace': {'cost': 2, 'target': 'any', 'effect': {}},
    'lashs_kiss':   {'cost': 2, 'target': 'any', 'effect': {}},
    'lashs_cure':   {'cost': 2, 'target': 'any', 'effect': {}},
    # shieldbreaker
    'snake_eyes':     {'cost': 3, 'target': 'allies', 'effect': {'armor_pierce': 15}},
    'way_of_scales':     {'cost': 3, 'target': 'self', 'effect': {'hp': 15, 'prot': 15}},  # snake_skin
    'sandstorm':      {'cost': 3, 'target': 'ally', 'effect': {'cant_be_marked': ''}},
    'way_of_adder': {'cost': 2, 'target': 'self', 'effect': {'blight_chance': 20, 'blight_resist': 20}},  # adders_embrace
    # shared
    'encourage':     {'cost': 2, 'target': 'ally', 'effect': {'stress_heal': 15}},
    'first_aid':    {'cost': 2, 'target': 'ally', 'effect': {'heal': 15, 'heal_blight': '', 'heal_bleed': ''}},  # wound_care
    'pep_talk':      {'cost': 2, 'target': 'ally', 'effect': {'stress_resist': 15}},
    'gallows_humor': {'cost': 4, 'target': 'all', 'effect': {}},
}

HeroClasses = {
    'abomination':   {'maxHp': [26, 31, 36, 41, 46], 'traps_base': 10, 'attack': ['melee', 'ranged'], 'heal': [],
                      'speed': [7, 7, 8, 8, 9]},
    'antiquarian':   {'maxHp': [17, 20, 23, 26, 29], 'traps_base': 10, 'attack': ['melee'], 'heal': ['hp'],
                      'speed': [5, 5, 6, 6, 7]},
    'arbalest':      {'maxHp': [27, 32, 37, 42, 47], 'traps_base': 10, 'attack': ['ranged'], 'heal': ['hp'],
                      'speed': [3, 3, 4, 4, 5]},
    'bounty_hunter': {'maxHp': [25, 30, 35, 40, 45], 'traps_base': 40, 'attack': ['melee'], 'heal': [],
                      'speed': [5, 5, 6, 6, 7]},
    'crusader':      {'maxHp': [33, 40, 47, 54, 61], 'traps_base': 10, 'attack': ['melee'], 'heal': ['stress'],
                      'speed': [1, 1, 2, 2, 3]},
    'grave_robber':  {'maxHp': [20, 24, 28, 32, 36], 'traps_base': 50, 'attack': ['melee', 'ranged'], 'heal': [],
                      'speed': [8, 8, 9, 9, 10]},
    'hellion':       {'maxHp': [26, 31, 36, 41, 46], 'traps_base': 20, 'attack': ['melee'], 'heal': [],
                      'speed': [4, 4, 5, 5, 6]},
    'highwayman':    {'maxHp': [23, 28, 33, 38, 43], 'traps_base': 40, 'attack': ['melee', 'ranged'], 'heal': [],
                      'speed': [5, 5, 6, 6, 7]},
    'houndmaster':   {'maxHp': [21, 25, 29, 33, 37], 'traps_base': 40, 'attack': ['ranged'], 'heal': ['stress'],
                      'speed': [5, 5, 6, 6, 7]},
    'jester':        {'maxHp': [19, 23, 27, 31, 35], 'traps_base': 30, 'attack': ['melee'], 'heal': ['stress'],
                      'speed': [7, 7, 8, 8, 9]},
    'leper':         {'maxHp': [35, 42, 49, 56, 63], 'traps_base': 10, 'attack': ['melee'], 'heal': [],
                      'speed': [2, 2, 3, 3, 4]},
    'man_at_arms':   {'maxHp': [31, 37, 43, 49, 55], 'traps_base': 10, 'attack': ['melee'], 'heal': [],
                      'speed': [3, 3, 4, 4, 5]},
    'occultist':     {'maxHp': [19, 23, 27, 31, 35], 'traps_base': 10, 'attack': ['melee'], 'heal': ['hp'],
                      'speed': [6, 6, 7, 7, 8]},
    'plague_doctor': {'maxHp': [22, 26, 30, 34, 38], 'traps_base': 20, 'attack': ['ranged'], 'heal': [],
                      'speed': [7, 7, 8, 8, 9]},
    'vestal':        {'maxHp': [24, 29, 34, 39, 44], 'traps_base': 10, 'attack': ['ranged'], 'heal': ['hp'],
                      'speed': [4, 4, 5, 5, 6]},
    'flagellant':    {'maxHp': [22, 26, 30, 34, 38], 'traps_base': 0, 'attack': ['melee'], 'heal': [],
                      'speed': [6, 6, 8, 8, 9]},
    'shieldbreaker': {'maxHp': [20, 24, 28, 32, 36], 'traps_base': 20, 'attack': ['melee'], 'heal': [],
                      'speed': [5, 6, 8, 8, 9]},
}

Diseases = {
    # future - add rating, requirement, effect
    'bad_humors':              {'default_rating': 1, 'requirement': [], 'effect': {'hp': -20}},
    'black_plague':            {'default_rating': 1, 'requirement': [], 'effect': {}},
    'bulimic':                 {'default_rating': 1, 'requirement': [], 'effect': {}},
    'creeping_cough':          {'default_rating': 1, 'requirement': [], 'effect': {}},
    'ennui':                   {'default_rating': 1, 'requirement': [], 'effect': {}},
    'grey_rot':                {'default_rating': 1, 'requirement': [], 'effect': {'hp': 20}},
    'hemophilia':              {'default_rating': 1, 'requirement': [], 'effect': {}},
    'hysterical_blindness':    {'default_rating': 1, 'requirement': [], 'effect': {}},
    'lethargy':                {'default_rating': 1, 'requirement': [], 'effect': {}},
    'rabies':                  {'default_rating': 1, 'requirement': [], 'effect': {}},
    'scurvy':                  {'default_rating': 1, 'requirement': [], 'effect': {}},
    'sky_taint':               {'default_rating': 1, 'requirement': [], 'effect': {}},
    'spasm_of_entrails':       {'default_rating': 1, 'requirement': [], 'effect': {}},
    'spotted_fever':           {'default_rating': 1, 'requirement': [], 'effect': {}},
    'syphilis':                {'default_rating': 1, 'requirement': [], 'effect': {'hp': -10}},
    'tapeworm':                {'default_rating': 1, 'requirement': [], 'effect': {}},
    'tetanus':                 {'default_rating': 1, 'requirement': [], 'effect': {}},
    'the_ague':                {'default_rating': 1, 'requirement': [], 'effect': {'hp': -10}},
    'the_fits':                {'default_rating': 1, 'requirement': [], 'effect': {}},
    'the_red_plague':          {'default_rating': 1, 'requirement': [], 'effect': {'hp': -10}},
    'the_runs':                {'default_rating': 1, 'requirement': [], 'effect': {'hp': -10}},
    'the_worries':             {'default_rating': 1, 'requirement': [], 'effect': {}},
    'vertigo':                 {'default_rating': 1, 'requirement': [], 'effect': {}},
    'vampiric_spirits':        {'default_rating': 1, 'requirement': [], 'effect': {}},
    'wasting_sickness':        {'default_rating': 1, 'requirement': [], 'effect': {}},
    'disease_vampire_passive': {'default_rating': 1, 'requirement': [], 'effect': {}},  # crimson_curse
}

Quirks = {
    # positive
    'hatred_of_beast':     {'default_rating': 8, 'requirement': ['warrens', 'weald', 'farmstead', 'darkest'],
                            'effect': {'dmg': 15, 'stress': -15}},  # beast_hater (beast)
    'slayer_of_beast':     {'default_rating': 7, 'requirement': ['warrens', 'weald', 'farmstead', 'darkest'],
                            'effect': {'acc': 10, 'crit': 5}},  # beast_slayer (beast)
    'clotter':             {'default_rating': 7, 'requirement': None, 'effect': {'bld_resist': 15}},
    'clutch_hitter':       {'default_rating': 6, 'requirement': ['low_hp'], 'effect': {'crit': 5}},
    'cove_adventurer':     {'default_rating': 6, 'requirement': ['cove'], 'effect': {'stress': -20}},
    'accurate':            {'default_rating': 6, 'requirement': None, 'effect': {'crit': 2}},  # deadly
    'eagle_eye':           {'default_rating': 6, 'requirement': ['ranged'], 'effect': {'crit': 5}},
    'early_riser':         {'default_rating': 7, 'requirement': ['sun'], 'effect': {'spd': 2}},
    'hatred_of_eldritch':  {'default_rating': 8, 'requirement': ['cove', 'weald', 'darkest'],
                            'effect': {'dmg': 15, 'stress': -15}},  # eldritch_hater (eldritch)
    'slayer_of_eldritch':  {'default_rating': 7, 'requirement': ['cove', 'weald', 'darkest'],
                            'effect': {'acc': 10, 'crit': 5}},  # eldritch_slayer (eldritch)
    'evasive':             {'default_rating': 7, 'requirement': None, 'effect': {'dodge': 5}},
    'gifted':              {'default_rating': 7, 'requirement': None, 'effect': {'healed': 20}},
    'gothic':              {'default_rating': 4, 'requirement': ['occultist'], 'effect': {'healed': 25}},
    'hard_noggin':         {'default_rating': 7, 'requirement': None, 'effect': {'stun_resist': 15}},
    'hippocratic':         {'default_rating': 9, 'requirement': None, 'effect': {'heal': 20}},
    'irrepressible':       {'default_rating': 5, 'requirement': None, 'effect': {'virtue': 5}},
    'last_gasp':           {'default_rating': 5, 'requirement': ['low_hp'], 'effect': {'spd': 1}},
    'lurker':              {'default_rating': 3, 'requirement': ['moon'], 'effect': {'dmg': 10}},
    'luminous':            {'default_rating': 9, 'requirement': None, 'effect': {'spd': 2, 'dodge': 5}},
    'hatred_of_man':       {'default_rating': 8, 'requirement': ['ruins', 'warrens', 'weald', 'farmstead', 'darkest', 'cove'],
                            'effect': {'dmg': 15, 'stress': -15}},  # mankind_hater (human)
    'slayer_of_man':       {'default_rating': 7, 'requirement': ['ruins', 'warrens', 'weald', 'farmstead', 'darkest', 'cove'],
                            'effect': {'acc': 10, 'crit': 5}},  # man_slayer (human)
    'musical':             {'default_rating': 5, 'requirement': ['jester'], 'effect': {'stress_healed': 25}},
    'natural_eye':         {'default_rating': 6, 'requirement': ['ranged'], 'effect': {'acc': 5}},
    'natural_swing':       {'default_rating': 8, 'requirement': None, 'effect': {'acc': 5}},
    'night_owl':           {'default_rating': 3, 'requirement': ['moon'], 'effect': {'spd': 2}},
    'on_guard':            {'default_rating': 6, 'requirement': ['first_round'], 'effect': {'spd': 4, 'dodge': 5}},
    'photomania':          {'default_rating': 8, 'requirement': ['sun'], 'effect': {'stress': -20}},
    'precision_striker':     {'default_rating': 6, 'requirement': ['melee'], 'effect': {'crit': 5}},  # precise_striker
    'quickdraw':           {'default_rating': 6, 'requirement': ['first_round'], 'effect': {'spd': 4}},
    'quick_reflexes':      {'default_rating': 9, 'requirement': None, 'effect': {'spd': 2}},
    'resilient':           {'default_rating': 5, 'requirement': None, 'effect': {'stress_healed': 10}},
    'robust':              {'default_rating': 4, 'requirement': None, 'effect': {'disease': 15}},
    'ruins_adventurer':    {'default_rating': 6, 'requirement': ['ruins'], 'effect': {'stress': -20}},
    'second_wind':         {'default_rating': 5, 'requirement': ['low_hp'], 'effect': {'dmg': 10}},
    'skilled_gambler':     {'default_rating': 3, 'requirement': None, 'effect': None},
    'slugger':             {'default_rating': 8, 'requirement': ['melee'], 'effect': {'dmg': 10}},
    'spiritual':           {'default_rating': 7, 'requirement': ['vestal'], 'effect': {'healed': 25}},
    'steady':              {'default_rating': 8, 'requirement': None, 'effect': {'stress': -10}},
    'stress_faster':       {'default_rating': 4, 'requirement': None, 'effect': None},
    'thick_blooded':       {'default_rating': 4, 'requirement': None, 'effect': {'bli_resist': 10}},
    'tough':               {'default_rating': 8, 'requirement': None, 'effect': {'hp': 10}},
    'hard_skinned':        {'default_rating': 8, 'requirement': None, 'effect': {'prot': 10}},
    'hatred_of_unholy':    {'default_rating': 7, 'requirement': ['ruins'],
                            'effect': {'dmg': 15, 'stress': -15}},  # unholy_hater (unholy)
    'slayer_of_unholy':    {'default_rating': 6, 'requirement': ['ruins'],
                            'effect': {'acc': 10, 'crit': 5}},  # unholy_slayer (unholy)
    'unerring':            {'default_rating': 8, 'requirement': ['ranged'], 'effect': {'dmg': 10}},
    'unyielding':          {'default_rating': 7, 'requirement': None, 'effect': {'death_resist': 10}},
    'warren_adventurer':  {'default_rating': 6, 'requirement': ['warrens'], 'effect': {'stress': -20}},
    'warrior_of_light':    {'default_rating': 8, 'requirement': ['sun'], 'effect': {'dmg': 10}},
    'weald_adventurer':    {'default_rating': 6, 'requirement': ['weald'], 'effect': {'stress': -20}},

    # positive (unique)
    'armor_haggler':       {'default_rating': 4, 'requirement': None, 'effect': None},  # armor_tinkerer
    'back_tracker':        {'default_rating': 3, 'requirement': None, 'effect': None},
    'improved_balance':    {'default_rating': 3, 'requirement': None, 'effect': None},  # balanced
    'cove_explorer':       {'default_rating': 6, 'requirement': ['cove'], 'effect': {'scout': 10}},
    'cove_scrounger':      {'default_rating': 5, 'requirement': ['cove'], 'effect': {'scout': 5}},
    'cove_tactician':      {'default_rating': 6, 'requirement': ['cove'], 'effect': {'dmg': 15}},
    'daredevil':           {'default_rating': 6, 'requirement': None, 'effect': None},
    'fairweather_fighter': {'default_rating': 6, 'requirement': None, 'effect': None},
    'fast_healer':         {'default_rating': 2, 'requirement': None, 'effect': None},
    'fated':               {'default_rating': 4, 'requirement': None, 'effect': None},
    'gift_of_the_healer':  {'default_rating': 2, 'requirement': None, 'effect': None},  # healers_gift
    'hot_to_trot':         {'default_rating': 6, 'requirement': None, 'effect': None},
    'meditator':           {'default_rating': 2, 'requirement': None, 'effect': None},
    'natural':       {'default_rating': 4, 'requirement': ['no_trinket'], 'effect': {'hp': 20, 'healed': 20, 'spd': 3}},
    'nymphomania':         {'default_rating': 2, 'requirement': None, 'effect': None},
    'ruins_explorer':      {'default_rating': 6, 'requirement': ['ruins'], 'effect': {'scout': 10}},
    'ruins_scrounger':     {'default_rating': 5, 'requirement': ['ruins'], 'effect': {'scout': 5}},
    'ruins_tactician':     {'default_rating': 6, 'requirement': ['ruins'], 'effect': {'dmg': 15}},
    'stout':               {'default_rating': 2, 'requirement': None, 'effect': None},
    'twilight_dreamer':    {'default_rating': 8, 'requirement': ['one_per_roster'], 'effect': {'ignores_stealth'}},
    'warren_explorer':    {'default_rating': 6, 'requirement': ['warrens'], 'effect': {'scout': 10}},
    'warren_scrounger':   {'default_rating': 5, 'requirement': ['warrens'], 'effect': {'scout': 5}},
    'warren_tactician':   {'default_rating': 6, 'requirement': ['warrens'], 'effect': {'dmg': 15}},
    'weald_explorer':      {'default_rating': 6, 'requirement': ['weald'], 'effect': {'scout': 10}},
    'weald_scrounger':     {'default_rating': 5, 'requirement': ['weald'], 'effect': {'scout': 5}},
    'weald_tactician':     {'default_rating': 6, 'requirement': ['weald'], 'effect': {'dmg': 15}},
    'weapons_haggler':     {'default_rating': 4, 'requirement': None, 'effect': None},  # weapon_tinkerer

    # positive (special)
    'corvids_eye':           {'default_rating': 0, 'requirement': None, 'effect': {'acc': 8, 'scout': 8}},
    'corvids_grace':         {'default_rating': 0, 'requirement': None, 'effect': {'dodge': 6, 'mov_resist': 25}},
    'corvids_resilience':    {'default_rating': 0, 'requirement': None, 'effect': {'disease': 33}},
    'prismatic_isolation':   {'default_rating': 0, 'requirement': None, 'effect': {'deb_resist': 25}},
    'prismatic_stability':   {'default_rating': 0, 'requirement': None, 'effect': {'mov_resist': 25}},
    'prismatic_solidity':    {'default_rating': 0, 'requirement': None, 'effect': {'stun_resist': 25}},
    'prismatic_coagulation': {'default_rating': 0, 'requirement': None, 'effect': {'bld_resist': 25}},
    'prismatic_purity':      {'default_rating': 0, 'requirement': None, 'effect': {'bli_resist': 25}},
    'prismatic_calm':        {'default_rating': 0, 'requirement': None, 'effect': {'stress': -30}},
    'prismatic_force':       {'default_rating': 0, 'requirement': None, 'effect': {'dmg': 15}},
    'prismatic_speed':       {'default_rating': 0, 'requirement': None, 'effect': {'spd': 3}},
    'prismatic_precision':   {'default_rating': 0, 'requirement': None, 'effect': {'crit': 4}},
    'prismatic_eye':         {'default_rating': 0, 'requirement': None, 'effect': {'acc': 8}},
    'husk_slayer':           {'default_rating': 0, 'requirement': ['husk'], 'effect': {'acc': 10, 'crit': 5}},
    'scythemaster':          {'default_rating': 0, 'requirement': ['husk'], 'effect': {'dmg': 15}},

    # negative
    'fear_of_beast':     {'default_rating': -7, 'requirement': ['warrens', 'weald', 'farmstead', 'darkest'],
                          'effect': {'stress': 15, 'acc': -10}},  # fear_of_beasts (beast)
    'zoophobia':         {'default_rating': -6, 'requirement': ['warrens', 'weald', 'farmstead', 'darkest'],
                          'effect': {'stress': 20}},  # beast
    'anemic':            {'default_rating': -3, 'requirement': None, 'effect': {'bld_resist': -10}},
    'dud_hitter':        {'default_rating': -5, 'requirement': ['low_hp'], 'effect': {'crit': -5}},
    'cove_phobe':        {'default_rating': -4, 'requirement': ['cove'], 'effect': {'stress': 20}},
    'inaccurate':        {'default_rating': -5, 'requirement': None, 'effect': {'crit': -2}},  # misses_the_spot
    'flawed_release':    {'default_rating': -6, 'requirement': ['ranged'], 'effect': {'crit': -5}},
    'nocturnal':         {'default_rating': -7, 'requirement': ['sun'], 'effect': {'spd': -2}},  # torch > 75%
    'fear_of_eldritch':  {'default_rating': -7, 'requirement': ['cove', 'weald', 'darkest'],
                          'effect': {'stress': 15, 'acc': -10}},  # eldritch
    'clumsy':            {'default_rating': -6, 'requirement': None, 'effect': {'dodge': -5}},
    'infirm':            {'default_rating': -7, 'requirement': None, 'effect': {'healed': -20}},
    'ascetic':           {'default_rating': -2, 'requirement': ['occultist'], 'effect': {'healed': -20}},
    'shocker':           {'default_rating': -4, 'requirement': None, 'effect': {'stun_resist': -10}},
    'bad_healer':        {'default_rating': -8, 'requirement': None, 'effect': {'heal': -20}},
    'mercurial':         {'default_rating': -3, 'requirement': None, 'effect': {'virtue': -5}},
    'winded':            {'default_rating': -7, 'requirement': ['low_hp'], 'effect': {'spd': -1}},
    'night_blindness':   {'default_rating': -3, 'requirement': ['moon'], 'effect': {'dmg': -10}},  # torch < 26%
    'fading':            {'default_rating': -9, 'requirement': None, 'effect': {'spd': -2, 'dodge': -5}},
    'fear_of_man':       {'default_rating': -7, 'requirement': ['ruins', 'warrens', 'weald', 'farmstead', 'darkest', 'cove'],
                          'effect': {'stress': 15, 'acc': -10}},  # human (fear_of_mankind)
    'automatonophobia':  {'default_rating': -6, 'requirement': ['ruins', 'warrens', 'weald', 'farmstead', 'darkest', 'cove'],
                          'effect': {'stress': 20}},  # human
    'tone_deaf':         {'default_rating': -5, 'requirement': ['jester'], 'effect': {'stress_healed': -20}},
    'lazy_eye':          {'default_rating': -8, 'requirement': ['ranged'], 'effect': {'acc': -5}},
    'the_yips':          {'default_rating': -8, 'requirement': None, 'effect': {'acc': -5}},
    'diurnal':           {'default_rating': -3, 'requirement': ['moon'], 'effect': {'spd': -2}},  # torch < 26%
    'off_guard':         {'default_rating': -7, 'requirement': ['first_turn'], 'effect': {'spd': -4, 'dodge': -5}},
    'phengophobia':      {'default_rating': -7, 'requirement': ['sun'], 'effect': {'stress': 20}},
    'weak_grip':         {'default_rating': -6, 'requirement': ['melee'], 'effect': {'crit': -5}},
    'slowdraw':          {'default_rating': -7, 'requirement': ['first_turn'], 'effect': {'spd': -4}},
    'slow_reflexes':     {'default_rating': -8, 'requirement': None, 'effect': {'spd': -1}},
    'ruminator':         {'default_rating': -4, 'requirement': None, 'effect': {'stress_healed': -10}},
    'sickly':            {'default_rating': -3, 'requirement': None, 'effect': {'disease': -10}},
    'ruins_phobe':       {'default_rating': -4, 'requirement': ['ruins'], 'effect': {'stress': 20}},
    'tuckered_out':      {'default_rating': -6, 'requirement': ['low_hp'], 'effect': {'dmg': -10}},
    'bad_gambler':       {'default_rating': -1, 'requirement': None, 'effect': {'gambling'}},
    'torn_rotator_cuff':      {'default_rating': -8, 'requirement': ['melee'], 'effect': {'dmg': -5}},  # torn_rotator
    'scientific':        {'default_rating': -7, 'requirement': ['vestal'], 'effect': {'healed': -20}},
    'nervous':           {'default_rating': -7, 'requirement': None, 'effect': {'stress': 10}},
    'stress_eater':      {'default_rating': -7, 'requirement': None, 'effect': {'food': 100}},
    'thin_blooded':      {'default_rating': -2, 'requirement': None, 'effect': {'bli_resist': -10}},
    'fragile':           {'default_rating': -8, 'requirement': None, 'effect': {'hp': -10}},
    'soft':              {'default_rating': -7, 'requirement': None, 'effect': {'hp': -5}},
    'fear_of_unholy': {'default_rating': -5, 'requirement': ['ruins'], 'effect': {'stress': 15, 'acc': -10}},  # unholy
    'satanophobia':       {'default_rating': -5, 'requirement': ['ruins'], 'effect': {'stress': 20}},  # unholy
    'scattering':         {'default_rating': -8, 'requirement': ['ranged'], 'effect': {'dmg': -5}},
    'suicidal':  {'default_rating': -6, 'requirement': None, 'effect': {'death_resist': -10}},  # weak_grip_on_life
    'warren_phobe':       {'default_rating': -4, 'requirement': ['warrens'], 'effect': {'stress': 20}},
    'sensitive_to_light': {'default_rating': -8, 'requirement': ['sun'], 'effect': {'dmg': -10}},  # light_sensitive
    'weald_phobe':        {'default_rating': -4, 'requirement': ['weald'], 'effect': {'stress': 20}},

    # negative (unique)
    'antsy':             {'default_rating': -9, 'requirement': ['idle'], 'effect': {'stress': 20}},
    'ashen':             {'default_rating': -5, 'requirement': None, 'effect': {'bli_resist': -10, 'bld_resist': -10}},
    'calm':              {'default_rating': -6, 'requirement': ['first_round'], 'effect': {'dmg': -15}},
    'claustrophobia':    {'default_rating': -7, 'requirement': ['hallways'], 'effect': {'stress': 20}},
    'germophobe':        {'default_rating': -7, 'requirement': ['blighted'], 'effect': {'acc': -10}},
    'imposter_syndrome': {'default_rating': -9, 'requirement': None, 'effect': {'pass': 4}},
    'lygophobia':        {'default_rating': -3, 'requirement': ['moon'], 'effect': {'stress': 20}},
    'nervous_bleeder':   {'default_rating': -7, 'requirement': ['bleeding'], 'effect': {'acc': -10}},
    'perfectionist':     {'default_rating': -8, 'requirement': ['miss'], 'effect': {'stress': 5}},
    'risktaker':         {'default_rating': -4, 'requirement': None, 'effect': {'dmg': 10, 'dodge': -10}},
    'thanatophobia':     {'default_rating': -6, 'requirement': ['low_hp'], 'effect': {'stress': 20}},
    'shield_mercenary':  {'default_rating': 0, 'requirement': None, 'effect': {'farmstead_only'}},
    'corvids_blindness': {'default_rating': -8, 'requirement': ['sun_50'], 'effect': {'acc': -10}},
    'corvids_appetite':  {'default_rating': -8, 'requirement': ['warrens', 'weald', 'courtyard'],
                          'effect': {'food': 100, 'body': None}},  # forced activation
    'corvids_curiosity': {'default_rating': -8, 'requirement': None, 'effect': {'all'}},  # forced activation

    # negative (treatment)
    'enlightened':   {'default_rating': -1, 'requirement': None, 'effect': {'only_meditate'}},
    'unquiet_mind':  {'default_rating': -1, 'requirement': None, 'effect': {'not_meditate'}},
    'god_fearing':   {'default_rating': -1, 'requirement': None, 'effect': {'only_pray'}},
    'witness':       {'default_rating': -1, 'requirement': None, 'effect': {'not_pray'}},
    'flagellant':    {'default_rating': -1, 'requirement': None, 'effect': {'only_flagellate'}},
    'faithless':     {'default_rating': -1, 'requirement': None, 'effect': {'not_flagellate', 'not_pray'}},
    'alcoholism':    {'default_rating': -1, 'requirement': None, 'effect': {'only_drink'}},  # tippler
    'resolution':    {'default_rating': -1, 'requirement': None, 'effect': {'not_drink'}},
    'gambler':       {'default_rating': -1, 'requirement': None, 'effect': {'only_gamble'}},
    'known_cheat':   {'default_rating': -1, 'requirement': None, 'effect': {'not_gamble'}},
    'love_interest': {'default_rating': -1, 'requirement': None, 'effect': {'only_brothel'}},
    'deviant_tastes': {'default_rating': -1, 'requirement': None, 'effect': {'not_brothel'}},

    # negative (forced interaction)
    'ablutomania':       {'default_rating': -2, 'requirement': ['courtyard'], 'effect': {'fountains'}},
    'bloodthirsty':      {'default_rating': -4, 'requirement': ['ruins', 'courtyard'], 'effect': {'torture'}},
    'compulsive':        {'default_rating': -8, 'requirement': None, 'effect': {'all'}},
    'curious':           {'default_rating': -8, 'requirement': None, 'effect': {'all'}},
    'dacnomania':        {'default_rating': -4, 'requirement': ['courtyard', 'ruins'], 'effect': {'torture'}},
    'dark_temptation':   {'default_rating': -7, 'requirement': ['courtyard', 'warrens', 'weald', 'cove'],
                          'effect': {'unholy'}},
    'demonomania':       {'default_rating': -7, 'requirement': ['courtyard', 'warrens', 'weald', 'cove'],
                          'effect': {'unholy'}},
    'dipsomania':        {'default_rating': -4, 'requirement': ['courtyard', 'warrens', 'cove'], 'effect': {'drink'}},
    'egomania':        {'default_rating': -8, 'requirement': ['courtyard', 'ruins'], 'effect': {'reflective', 'steal'}},
    'guilty_conscience': {'default_rating': -6, 'requirement': ['ruins', 'warrens', 'cove'], 'effect': {'worship'}},
    'hagiomania':        {'default_rating': -6, 'requirement': ['ruins', 'warrens', 'cove'], 'effect': {'worship'}},
    'hieromania':        {'default_rating': -6, 'requirement': ['ruins', 'warrens', 'cove'], 'effect': {'worship'}},
    'hylomania':         {'default_rating': -8, 'requirement': None, 'effect': {'treasure'}},
    'kleptomaniac':      {'default_rating': -9, 'requirement': None, 'effect': {'treasure', 'steal'}},
    'necromania':        {'default_rating': -5, 'requirement': ['warrens', 'weald', 'courtyard'], 'effect': {'body'}},
    'paranormania':      {'default_rating': -7, 'requirement': ['ruins', 'weald', 'courtyard'], 'effect': {'haunted'}},
    'plutomania':        {'default_rating': -8, 'requirement': None, 'effect': {'treasure'}},
    'sitiomania':  {'default_rating': -7, 'requirement': ['warrens', 'weald', 'courtyard', 'cove'], 'effect': {'food'}},
}
