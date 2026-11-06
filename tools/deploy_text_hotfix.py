"""Reuse the verified code-only deployment procedure with an exact text allowlist."""
import argparse
import deploy_picker_hotfix as deployment

deployment.STATE = deployment.ROOT / 'publishing/text-hotfix-state.json'
deployment.VERSION = '0.1.2-lua-test.3'
deployment.FROM = '0.1.2-lua-test.2'
deployment.LABEL = 'Text'
deployment.SCOPE = 'CN/EN translation formatting and configurable departure cost 0.5 to 4; no save schema change'
deployment.ALLOWED = {'42/mod.info', '42/media/lua/shared/SuQingPortals/Core.lua',
    '42/media/lua/server/SuQingPortals/World.lua', '42/media/lua/client/SuQingPortals/UI.lua',
    '42/media/sandbox-options.txt',
    '42/media/lua/shared/Translate/CN/IG_UI.json', '42/media/lua/shared/Translate/EN/IG_UI.json',
    '42/media/lua/shared/Translate/CN/Sandbox.json', '42/media/lua/shared/Translate/EN/Sandbox.json',
    '42/media/lua/shared/Translate/CN/Mod.json', '42/media/lua/shared/Translate/EN/Mod.json'}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('snapshot', 'deploy'))
    args = parser.parse_args()
    deployment.snapshot() if args.action == 'snapshot' else deployment.deploy()
