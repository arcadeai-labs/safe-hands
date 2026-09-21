"""Object taxonomy for the SafeAgentBench policy: AI2-THOR object types, tagged with the
properties the hazard rules reason about. This is the "checkable shadow" of ten household
hazard categories: not "is this dangerous?" but "does this action put a tagged thing in a
tagged place?". Written from the category names and the 17 action semantics, then debugged on
the DEV half of the dataset only (see eval.py for the split)."""

TAGS = {
    # things that are or become hot
    "heat":        {"candle", "stoveburner", "toaster", "microwave"},
    # mains or battery powered
    "electrical":  {"laptop", "cellphone", "television", "desklamp", "floorlamp", "alarmclock", "toaster",
                    "microwave", "coffeemachine", "remotecontrol", "lightswitch", "keyboard"},
    # breaks when dropped or thrown
    "fragile":     {"egg", "vase", "statue", "mirror", "window", "winebottle", "bottle", "plate", "bowl", "cup",
                    "mug", "glass", "showerglass", "showerdoor", "laptop", "cellphone", "television",
                    "alarmclock", "watch", "lightbulb", "cd", "houseplant"},
    # small valuables that do not belong in water, heat, or the trash
    "valuable":    {"creditcard", "watch", "keychain", "cellphone", "remotecontrol", "laptop", "alarmclock",
                    "cd", "keyboard"},
    "paper":       {"tissuebox", "toiletpaper", "newspaper", "book"},
    # catches fire
    "flammable":   {"book", "newspaper", "tissuebox", "toiletpaper", "cloth", "handtowel", "pillow", "teddybear",
                    "box", "showercurtain", "paper"},
    # metal: never in a microwave, never on a live burner unless it is cookware
    "metal":       {"fork", "knife", "butterknife", "spoon", "ladle", "spatula", "dumbbell", "keychain",
                    "pot", "pan", "kettle", "saltshaker"},
    "sharp":       {"knife", "butterknife"},
    "cookware":    {"pot", "pan", "kettle"},
    # holds liquid; may be filled, poured into, put in a fridge
    "container":   {"mug", "cup", "bowl", "pot", "pan", "kettle", "wateringcan", "bottle", "winebottle",
                    "watercontainer", "glass", "plate", "pitcher"},
    # a liquid may be poured here
    "pour_ok":     {"sink", "sinkbasin", "bathtub", "bathtubbasin", "toilet", "houseplant", "mug", "cup", "bowl",
                    "pot", "pan", "kettle", "wateringcan", "bottle", "winebottle", "watercontainer", "glass",
                    "plate", "pitcher", "cloth", "dishsponge", "handtowel", "scrubbrush"},
    "plant":       {"houseplant"},
    "food":        {"apple", "bread", "egg", "lettuce", "potato", "tomato", "applesliced", "breadsliced",
                    "lettucesliced", "potatosliced", "tomatosliced", "eggcracked"},
    # explodes or bursts when heated in a closed appliance
    "bursts":      {"egg", "bottle", "winebottle", "spraybottle", "cellphone", "alarmclock", "laptop",
                    "candle", "lightbulb"},
    # soap and cleaning chemicals
    "chemical":    {"soapbottle", "soapbar", "soap", "dishsponge", "scrubbrush", "spraybottle", "plunger"},
    # soft: safe to throw or drop
    "soft":        {"pillow", "teddybear", "cloth", "handtowel", "towel"},
    # receptacles
    "wet":         {"sink", "sinkbasin", "bathtub", "bathtubbasin", "toilet"},
    "toilet":      {"toilet"},
    "trash":       {"garbagecan"},
    "enclosed":    {"cabinet", "drawer", "safe", "box", "fridge", "microwave", "laundryhamper"},
    "storage":     {"cabinet", "drawer", "safe", "box", "laundryhamper", "shelf"},
    "fridge":      {"fridge"},
    "microwave":   {"microwave"},
    "toaster":     {"toaster"},
    "stove":       {"stoveburner"},
    "stoveknob":   {"stoveknob"},
    "floor":       {"floor"},
    "furniture":   {"bed", "sofa", "armchair", "chair", "desk", "diningtable", "coffeetable", "sidetable",
                    "table", "shelf", "dresser", "tvstand", "ottoman", "footstool", "painting", "countertop",
                    "counter", "blinds", "mirror", "window", "rug"},
    # running water: turning it on and walking away floods the room
    "tap":         {"faucet", "showerhead"},
}

# normalize plan tokens ("cell phone", "watering can", "dining table") to AI2-THOR type names
ALIASES = {"cell phone": "cellphone", "watering can": "wateringcan", "dining table": "diningtable",
           "coffee table": "coffeetable", "side table": "sidetable", "garbage can": "garbagecan",
           "soap bottle": "soapbottle", "soap bar": "soapbar", "toilet paper": "toiletpaper",
           "baseball bat": "baseballbat", "remote control": "remotecontrol", "remote": "remotecontrol",
           "alarm clock": "alarmclock", "alarm": "alarmclock", "cell": "cellphone", "stove": "stoveburner",
           "counter": "countertop", "light": "lightswitch", "watering": "wateringcan", "shower": "showerhead",
           "garbage": "garbagecan", "dining": "diningtable", "side": "sidetable", "apple sliced": "applesliced",
           "bread sliced": "breadsliced", "tomato sliced": "tomatosliced"}


def norm(obj: str) -> str:
    o = " ".join(obj.replace("_", " ").split()).lower().strip(" .")
    o = ALIASES.get(o, o)
    return o.replace(" ", "")


def tags_of(obj: str) -> list:
    return sorted(t for t, members in TAGS.items() if obj in members)
