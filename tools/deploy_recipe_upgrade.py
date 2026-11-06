"""Deploy the approved recipe on top of the text/cost candidate, preserving saves."""
import argparse
import deploy_picker_hotfix as deployment

deployment.STATE = deployment.ROOT / 'publishing/recipe-upgrade-state.json'
deployment.VERSION = '0.1.3-lua-test.1'
deployment.FROM = '0.1.2-lua-test.3'
deployment.LABEL = 'Recipe'
deployment.SCOPE = 'Approved native recipe and explicit versioned test kit; retain configurable cost, Lua format fix and save schema3'
deployment.ALLOWED = {'42/mod.info', '42/media/lua/shared/SuQingPortals/Core.lua',
    '42/media/lua/client/SuQingPortals/Build.lua', '42/media/scripts/SuQingPortals_Building.txt',
    '42/media/lua/shared/Translate/CN/IG_UI.json', '42/media/lua/shared/Translate/EN/IG_UI.json',
    '42/media/lua/shared/Translate/CN/Mod.json', '42/media/lua/shared/Translate/EN/Mod.json',
    '42/media/lua/shared/Translate/CN/Tooltip.json', '42/media/lua/shared/Translate/EN/Tooltip.json'}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('snapshot', 'deploy'))
    args = parser.parse_args()
    deployment.snapshot() if args.action == 'snapshot' else deployment.deploy()
