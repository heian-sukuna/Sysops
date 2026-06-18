"""
sysops/__main__.py — Entry point for SYSOPS
Run as: python3 -m sysops   (from /home/claude)
     or: sysops              (after install.py)
"""

import sys, os

# Add both the package dir and its parent to sys.path so imports work
# regardless of how the module is invoked.
_PKG  = os.path.dirname(os.path.abspath(__file__))   # .../sysops/
_ROOT = os.path.dirname(_PKG)                         # .../  (project root)
for _p in (_ROOT, _PKG):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.save  import SaveManager
from core.menu  import main_menu, new_game_wizard, options_screen, howto_screen
from core.world import VirtualWorld
from core.repl  import GameREPL
from scenarios.engine import ScenarioEngine
from core.ui    import clear, err, dim


def main():
    save = SaveManager()

    while True:
        choice = main_menu(save)

        if choice == "exit":
            print(dim("\n  Goodbye.\n"))
            sys.exit(0)

        elif choice == "howto":
            howto_screen()
            continue

        elif choice == "new":
            new_game_wizard(save)
            _start_game(save)

        elif choice == "load":
            if not save.load():
                print(err("  Failed to load save. Starting new game."))
                new_game_wizard(save)
            _start_game(save)

        elif choice == "options":
            if not save.exists():
                continue
            save.load()
            options_screen(save)
            # loop back to main menu after options


def _start_game(save: SaveManager):
    """Boot the virtual world and REPL from a loaded/new save."""
    world     = VirtualWorld(save.data)
    sc_engine = ScenarioEngine(world, save)

    repl = GameREPL(world, save, sc_engine)
    try:
        repl.run()
    except SystemExit:
        pass
    finally:
        if save.data:
            save.data["world"] = world.to_dict()
            save.save()


if __name__ == "__main__":
    main()
