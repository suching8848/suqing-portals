"""Deploy only the authorized generator/ISA candidate to the existing isolated profile."""
import argparse
import deploy_picker_hotfix as deployment

deployment.STATE = deployment.ROOT / 'publishing/energy-upgrade-state.json'
deployment.VERSION = '0.1.4-lua-test.1'
deployment.FROM = '0.1.3-lua-test.2'
deployment.LABEL = 'EnergyCompat'
deployment.SCOPE = 'Actual stored-charge fuel/ISA settlement, single-source selection and generator UI; keep schema3, recipe, transfer settings and selected C artwork'
deployment.ALLOW_ADDED_FILES = True
deployment.ALLOWED = {
    '42/mod.info',
    '42/media/lua/shared/SuQingPortals/Core.lua',
    '42/media/lua/server/SuQingPortals/World.lua',
    '42/media/lua/server/SuQingPortals/Power.lua',
    '42/media/lua/server/SuQingPortals/ISAPower.lua',
    '42/media/lua/client/SuQingPortals/UI.lua',
    '42/media/lua/client/SuQingPortals/PowerDisplay.lua',
    '42/media/lua/shared/Translate/CN/IG_UI.json',
    '42/media/lua/shared/Translate/EN/IG_UI.json',
}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('snapshot', 'deploy'))
    args = parser.parse_args()
    deployment.snapshot() if args.action == 'snapshot' else deployment.deploy()
