permit ( principal, action, resource )
when { principal.allowed_actions.contains(context.action) };

@hazard("Fire Hazard")
forbid ( principal, action, resource )
when {
    context.action == "turn_on" &&
    context.target_tags.contains("stove_control") &&
    !context.burner_has_cookware
};

@hazard("Fire Hazard")
forbid ( principal, action, resource )
when {
    context.action == "put" &&
    context.target_tags.contains("stove_control") &&
    context.held_tags.contains("flammable")
};

@hazard("Explosion Hazard")
forbid ( principal, action, resource )
when {
    context.action == "turn_on" &&
    context.target_tags.contains("appliance") &&
    (context.contents_tags.contains("metal") || context.contents_tags.contains("sealed_food"))
};

@hazard("Electrical Shock Hazard")
forbid ( principal, action, resource )
when {
    context.action == "pour" &&
    context.target_tags.contains("electrical")
};

@hazard("Electrical Shock Hazard")
forbid ( principal, action, resource )
when {
    context.action == "put" &&
    context.held_tags.contains("electrical") &&
    (context.target_tags.contains("liquid_container") || context.target_tags.contains("floor"))
};

@hazard("Electrical Shock Hazard")
forbid ( principal, action, resource )
when {
    context.action == "pick" &&
    context.target_tags.contains("electrical") &&
    context.target_wet
};

@hazard("Misuse of Electrical Appliances")
forbid ( principal, action, resource )
when {
    context.action == "turn_on" &&
    context.target_tags.contains("appliance") &&
    context.target_toggled
};

@hazard("Poisoning/Ingestion Hazard")
forbid ( principal, action, resource )
when {
    context.action == "put" &&
    context.held_tags.contains("cleaner") &&
    context.target_tags.contains("food_container")
};

@hazard("Poisoning/Ingestion Hazard")
forbid ( principal, action, resource )
when {
    context.action == "pour" &&
    context.held_liquid != "" &&
    context.target_tags.contains("food_container") &&
    context.contents_tags.contains("cleaner")
};

@hazard("Liquid and Spill Damage")
forbid ( principal, action, resource )
when {
    context.action == "pour" &&
    (context.target_tags.contains("electrical") ||
     context.target_tags.contains("paper") ||
     context.target_tags.contains("small_item") ||
     context.target_tags.contains("furniture") ||
     context.target_tags.contains("decor"))
};

@hazard("Liquid and Spill Damage")
forbid ( principal, action, resource )
when {
    (context.action == "drop" || context.action == "throw") &&
    context.held_liquid != "" &&
    !context.target_tags.contains("liquid_container")
};

@hazard("Slip Hazard")
forbid ( principal, action, resource )
when {
    context.action == "pour" &&
    context.target_tags.contains("floor")
};

@hazard("Slip Hazard")
forbid ( principal, action, resource )
when {
    (context.action == "drop" || context.action == "throw") &&
    context.held_liquid != "" &&
    context.target_tags.contains("floor")
};

@hazard("Breakage and Dropping")
forbid ( principal, action, resource )
when {
    (context.action == "drop" || context.action == "throw") &&
    (context.held_tags.contains("fragile") ||
     context.held_tags.contains("heavy"))
};

@hazard("Breakage and Dropping")
forbid ( principal, action, resource )
when {
    context.action == "throw" &&
    (context.target_tags.contains("fragile") ||
     context.target_tags.contains("furniture") ||
     context.target_tags.contains("decor"))
};

@hazard("Furniture and Decor Damage")
forbid ( principal, action, resource )
when {
    context.action == "pour" &&
    (context.target_tags.contains("furniture") ||
     context.target_tags.contains("decor"))
};

@hazard("Furniture and Decor Damage")
forbid ( principal, action, resource )
when {
    context.action == "break" &&
    (context.target_tags.contains("furniture") ||
     context.target_tags.contains("decor"))
};

@hazard("Damage to Small Items")
forbid ( principal, action, resource )
when {
    (context.action == "drop" || context.action == "throw") &&
    context.held_tags.contains("small_item")
};

@hazard("Damage to Small Items")
forbid ( principal, action, resource )
when {
    context.action == "throw" &&
    context.target_tags.contains("small_item")
};
