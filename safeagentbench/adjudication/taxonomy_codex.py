TAGS: dict[str, set[str]] = {
    "appliance": {
        "coffeemachine", "desklamp", "floorlamp", "kettle", "microwave",
        "stoveburner", "television", "toaster",
    },
    "electrical": {
        "alarmclock", "cellphone", "coffeemachine", "desklamp", "floorlamp",
        "keyboard", "laptop", "microwave", "television", "toaster",
    },
    "stove_control": {"stoveknob"},
    "cookware": {"bowl", "pan", "plate", "pot"},
    "liquid_container": {
        "bottle", "bowl", "cup", "kettle", "mug", "pot", "wateringcan",
        "watercontainer", "winebottle",
    },
    "food_container": {"bowl", "cup", "mug", "plate"},
    "food": {
        "apple", "applesliced", "bread", "breadsliced", "egg", "potato",
        "tomato", "tomatosliced",
    },
    "sealed_food": {"egg"},
    "cleaner": {"soapbar", "soapbottle", "dishsponge", "scrubbrush"},
    "flammable": {"book", "cloth", "newspaper", "pillow", "towel", "tissuebox"},
    "metal": {
        "creditcard", "fork", "knife", "ladle", "pan", "pot", "spatula",
        "spoon",
    },
    "fragile": {"bottle", "mug", "vase", "winebottle", "mirror"},
    "decor": {
        "candle", "mirror", "statue", "teddybear", "vase", "television",
    },
    "furniture": {
        "bed", "chair", "coffeetable", "countertop", "desk", "diningtable",
        "shelf", "sidetable", "sofa", "table",
    },
    "floor": {"floor"},
    "small_item": {
        "alarmclock", "baseballbat", "book", "cellphone", "cd", "creditcard",
        "fork", "keychain", "pencil", "pen", "remotecontrol", "spoon",
        "watch",
    },
    "heavy": {"basketball", "bathtub", "dumbbell", "sofa", "television"},
    "paper": {"book", "newspaper", "tissuebox", "toiletpaper"},
}


def tags_of(obj: str) -> list[str]:
    return sorted(tag for tag, objects in TAGS.items() if obj in objects)
