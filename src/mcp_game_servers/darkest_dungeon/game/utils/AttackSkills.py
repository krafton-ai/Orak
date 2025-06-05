"""[0 - ally ranks, 1 - enemy ranks, 2 - stun skill chance or blight damage, 3 - move distance]"""
AttackSkills = {
    # highwayman
    'wicked_slice': [[1, 2, 3], [1, 2]],
    'opened_vein': [[1, 2, 3], [1, 2]],
    'pistol_shot': [[2, 3, 4], [2, 3, 4]],
    'duelist_advance': [[2, 3, 4], [1, 2, 3], None, 1],
    'point_blank_shot': [[1], [1], None, -1],
    # crusader
    'smite': [[1, 2], [1, 2]],
    'stunning_blow': [[1, 2], [1, 2], [100, 110, 120, 130, 140]],
    'holy_lance': [[3, 4], [2, 3, 4], None, 1],
    'inspiring_cry': [[1, 2, 3, 4], [1, 2, 3, 4]],
    # plague_doctor
    'noxious_blast': [[2, 3, 4], [1, 2], [5, 5, 6, 6, 7]],
    'plague_grenade': [[3, 4], [3, 4], [4, 4, 5, 5, 6]],
    'blinding_gas': [[3, 4], [3, 4], [100, 110, 120, 130, 140]],
    'incision': [[1, 2, 3], [1, 2]],
    'battlefield_medicine': [[3, 4], [1, 2, 3, 4]],
    'emboldening_vapors': [[3, 4], [1, 2, 3, 4]],
    'disorienting_blast': [[2, 3, 4], [2, 3, 4], [100, 110, 120, 130, 140]],
    # vestal
    'judgement': [[3, 4], [1, 2, 3, 4]],
    'dazzling_light': [[2, 3, 4], [1, 2, 3], [100, 110, 120, 130, 140]],
    'divine_grace': [[3, 4], [1, 2, 3, 4]],
    'gods_comfort': [[2, 3, 4], [0]],  # divine comfort
    'gods_hand': [[1, 2], [1, 2, 3]],  # hand of light
    'gods_illumination': [[1, 2, 3], [1, 2, 3, 4]],  # illumination
    # hellion
    'wicked_hack': [[1, 2], [1, 2]],
    'iron_swan': [[1], [4]],
    'barbaric_yawp': [[1, 2], [1, 2], [110, 120, 130, 140, 150]],  # yawp
    'if_it_bleeds': [[1, 2, 3], [2, 3]],
    # houndmaster
    'hounds_rush': [[2, 3, 4], [1, 2, 3, 4]],
    'howl': [[3, 4], [0]],  # cry_havoc
    'guard_dog': [[1, 2, 3, 4], [1, 2, 3, 4]],
    'lick_wounds': [[2, 3, 4], [0]],
    'hounds_harry': [[1, 2, 3, 4], [0]],
    'blackjack': [[1, 2], [1, 2, 3], [110, 120, 130, 140, 150]],
    # jester
    'dirk_stab': [[1, 2, 3, 4], [1, 2, 3], None, 1],
    'harvest': [[2, 3], [2, 3]],
    'slice_off': [[2, 3], [2, 3]],
    'battle_ballad': [[3, 4], [0]],
    'inspiring_tune': [[3, 4], [1, 2, 3, 4]],
    # man-at-arms
    'crush': [[1, 2], [1, 2, 3]],
    'rampart': [[1, 2, 3], [1, 2], [100, 110, 120, 130, 140], 1],
    'defender': [[1, 2, 3, 4], [1, 2, 3, 4]],
    'retribution': [[1, 2, 3], [1, 2, 3]],
    'command': [[1, 2, 3, 4], [1, 2, 3, 4]],
    'bolster': [[1, 2, 3, 4], [0]],
    # occultist
    'bloodlet': [[1, 2, 3], [1, 2, 3]],  # sacrificial_stab
    'abyssal_artillery': [[3, 4], [3, 4]],
    'weakening_curse': [[1, 2, 3, 4], [1, 2, 3, 4]],
    'wyrd_reconstruction': [[1, 2, 3, 4], [1, 2, 3, 4]],
    'vulnerability_hex': [[1, 2, 3, 4], [1, 2, 3, 4]],
    'hands_from_abyss': [[1, 2], [1, 2, 3], [110, 120, 130, 140, 150]],  # hands_from_the_abyss
    'daemons_pull': [[2, 3, 4], [3, 4]],
    # shieldbreaker
    'pierce': [[1, 2, 3], [1, 2, 3, 4], None, 1],
    'break_guard': [[1, 2, 3, 4], [1, 2, 3, 4], None, 1],  # puncture
    'adders_kiss': [[1], [1, 2], None, -1],
    'impale': [[1], [0], None, -1],
    'expose': [[1, 2, 3], [1, 2, 3], None, -1],
    'single_out': [[2, 3], [2, 3]],  # captivate
    'serpent_sway': [[1, 2, 3], [0], None, 1],
}
