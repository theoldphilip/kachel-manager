#!/bin/sh
# Kachel Manager: copy the Home Assistant integration `kachel` from kachel-verbindung-plugin's repository into the
# add-on (screen_manager/app/ha_integration/kachel), at the commit it names in the mailbox. The repository is read from
# a throwaway clone; nothing there is changed. Then set SOURCE_COMMIT in screen_manager/app/kachel_integration.py.
#
#     tools/kachel_integration_copy.sh <commit>
set -eu
[ $# -eq 1 ] || { echo "usage: $0 <commit>" >&2; exit 2; }
root=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
"$HOME/kachel-zentrale/tools/gitk" clone -q https://github.com/theoldphilip/kachel-verbindung.git "$work/repo"
git -C "$work/repo" archive "$1" custom_components/kachel | tar -x -C "$work"
rm -rf "$root/screen_manager/app/ha_integration/kachel"
cp -r "$work/custom_components/kachel" "$root/screen_manager/app/ha_integration/kachel"
sed -i "s/^SOURCE_COMMIT = .*/SOURCE_COMMIT = '$1'/" "$root/screen_manager/app/kachel_integration.py"
echo "kachel $(python3 -c "import json;print(json.load(open('$root/screen_manager/app/ha_integration/kachel/manifest.json'))['version'])") @$1 copied"
