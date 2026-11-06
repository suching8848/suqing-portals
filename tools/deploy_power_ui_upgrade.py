"""Deploy the authorized power-status, resize and test-giver removal update."""
import argparse
import deploy_picker_hotfix as deployment

deployment.STATE = deployment.ROOT / 'publishing/power-ui-upgrade-state.json'
deployment.VERSION = '0.1.3-lua-test.2'
deployment.FROM = '0.1.3-lua-test.1'
deployment.LABEL = 'PowerUI'
deployment.SCOPE = 'Visible power/source state, responsive resizable management, complete mod test-giver removal; no save schema change'
deployment.ALLOWED = {'42/mod.info', '42/media/lua/shared/SuQingPortals/Core.lua',
    '42/media/lua/server/SuQingPortals/World.lua', '42/media/lua/client/SuQingPortals/UI.lua',
    '42/media/lua/client/SuQingPortals/Client.lua', '42/media/lua/client/SuQingPortals/Build.lua',
    '42/media/sandbox-options.txt',
    '42/media/lua/shared/Translate/CN/IG_UI.json', '42/media/lua/shared/Translate/EN/IG_UI.json',
    '42/media/lua/shared/Translate/CN/Sandbox.json', '42/media/lua/shared/Translate/EN/Sandbox.json',
    '42/media/lua/shared/Translate/CN/Mod.json', '42/media/lua/shared/Translate/EN/Mod.json'}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('snapshot', 'deploy'))
    args = parser.parse_args()
    deployment.snapshot() if args.action == 'snapshot' else deployment.deploy()
