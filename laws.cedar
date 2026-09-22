// ============================================================================
//  Asimov's Three Laws of Robotics, compiled to executable authorization policy.
//
//  The trick: Cedar evaluates an explicit `forbid` as ALWAYS overriding a
//  `permit`, which is exactly Asimov's law priority. Law 1 (forbid) beats Law 2 (permit).
//  Nothing is allowed unless a human orders it (Law 2), and no order survives a
//  safety violation (Law 1) or self-destruction (Law 3).
// ============================================================================

// ---- SECOND LAW ----------------------------------------------------------
// "A robot must obey the orders given it by human beings."
// The ONLY source of permission: the arm does nothing unless an authenticated
// operator, scoped for that action, commands it.
permit ( principal, action, resource )
when { principal.allowed_actions.contains(context.action_name) };

// ---- FIRST LAW -----------------------------------------------------------
// "A robot may not injure a human being, or, through inaction, allow a human to
//  come to harm." Overrides the Second Law. (Checkable shadow of "harm": moving
//  fast with a human in the workspace, or disabling the safety system.)
forbid ( principal, action, resource )
when { context.human_in_workspace && context.speed > resource.safe_speed_near_human };

forbid ( principal, action, resource )
when { context.action_name == "disable_safety" };

// ---- THIRD LAW -----------------------------------------------------------
// "A robot must protect its own existence, as long as such protection does not
//  conflict with the First or Second Law." Forbid self-destruction (a joint past
//  its mechanical limit, in either direction) UNLESS a higher law requires it.
forbid ( principal, action, resource )
when { context.joint_target > resource.hard_joint_limit
    || context.joint_target < -(resource.hard_joint_limit) }
unless { context.required_to_prevent_human_harm };
