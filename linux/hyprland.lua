-- StashOfExile2 window rules for Lua-based Hyprland configs (player-tested) - see linux/README.md.
o.window({ class = "^Stashofexile2$" }, { float = true, center = true, size = { 1400, 1000 } })
o.window({ class = "^Toplevel$", xwayland = true }, { float = true })
-- Keys: nothing to add - the app adds its own pass-through binds (hl.bind, description "SoE2 <key>") while it runs.
