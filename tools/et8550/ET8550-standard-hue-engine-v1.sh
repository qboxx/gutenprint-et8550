#!/usr/bin/env bash
set -euo pipefail

SRC="$HOME/gutenprint-et8550/src/xml/escp2/inks/claria_et.xml"
DST="/opt/gutenprint-et8550/share/gutenprint/5.3/xml/escp2/inks/claria_et.xml"
BACKUP="${SRC}.before-standard-hue-engine-v1"

ACTION="${1:-status}"

show_status() {
  python3 - "$SRC" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

marker = '<InkName translate="text" name="CMYKk"'
start = text.find(marker)
end = text.find("</InkName>", start)

if start < 0 or end < 0:
    raise SystemExit("FEJL: CMYKk-blokken blev ikke fundet.")

block = text[start:end]

print("===== CMYKk STATUS =====")
print("PB color 64:", 'subchannel color="64"' in block)
print("GY color 16:", 'subchannel color="16"' in block)
print("Cyan HueCurveParam:", 'name="CyanHueCurve"' in block)
print("Magenta HueCurveParam:", 'name="MagentaHueCurve"' in block)
print("Yellow HueCurveParam:", 'name="YellowHueCurve"' in block)
print("Fast Cyan HueCurve ref:", 'ref="cmykrCyan"' in block)
print("Fast Magenta HueCurve ref:", 'ref="cmykrMagenta"' in block)
print("Fast Yellow HueCurve ref:", 'ref="cmykrYellow"' in block)
PY
}

case "$ACTION" in
  status)
    if [[ ! -f "$SRC" ]]; then
      echo "FEJL: Kan ikke finde $SRC" >&2
      exit 1
    fi
    show_status
    ;;

  apply)
    if [[ ! -f "$SRC" ]]; then
      echo "FEJL: Kan ikke finde $SRC" >&2
      exit 1
    fi

    if [[ ! -f "$BACKUP" ]]; then
      cp -av "$SRC" "$BACKUP"
    else
      echo "Backup findes allerede: $BACKUP"
    fi

    python3 - "$SRC" <<'PY'
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

marker = '<InkName translate="text" name="CMYKk"'
start = text.find(marker)
if start < 0:
    raise SystemExit("FEJL: CMYKk-blokken blev ikke fundet.")

end = text.find("</InkName>", start)
if end < 0:
    raise SystemExit("FEJL: Slutningen på CMYKk-blokken blev ikke fundet.")
end += len("</InkName>")

block = text[start:end]

required = [
    'subchannel color="64"',
    'subchannel color="16"',
    '<HueCurveParam name="CyanHueCurve"/>',
    '<HueCurveParam name="MagentaHueCurve"/>',
    '<HueCurveParam name="YellowHueCurve"/>',
]

for token in required:
    if token not in block:
        raise SystemExit(
            "FEJL: Den aktive CMYKk-blok matcher ikke den validerede PB/GY-baseline. "
            f"Mangler: {token}"
        )

refs = [
    '    <HueCurve ref="cmykrCyan"/>\n',
    '    <HueCurve ref="cmykrMagenta"/>\n',
    '    <HueCurve ref="cmykrYellow"/>\n',
]

removed = 0
for ref in refs:
    if ref in block:
        block = block.replace(ref, "", 1)
        removed += 1

if removed == 0:
    print("De tre faste HueCurve-referencer er allerede fjernet.")
elif removed != 3:
    raise SystemExit(
        f"FEJL: Kun {removed} af 3 HueCurve-referencer blev fundet. "
        "Ingen fil er skrevet."
    )

updated = text[:start] + block + text[end:]

# Bevar de eksisterende kurvedefinitioner i <Curves>; kun bindingen i CMYKk fjernes.
# Raw-inksettet må ikke ændres.
raw_marker = '<InkName translate="text" name="PhysicalCMYKkR"'
raw_start = updated.find(raw_marker)
raw_end = updated.find("</InkName>", raw_start)
if raw_start < 0 or raw_end < 0:
    raise SystemExit("FEJL: PhysicalCMYKkR-blokken mangler.")

raw = updated[raw_start:raw_end]
for token in (
    'subchannel color="0"',
    'subchannel color="2"',
    'subchannel color="1"',
    'subchannel color="4"',
    'subchannel color="16"',
    'subchannel color="64"',
):
    if token not in raw:
        raise SystemExit(f"FEJL: Raw sekskanalsblokken mangler {token}")

new_block_start = updated.find(marker)
new_block_end = updated.find("</InkName>", new_block_start)
new_block = updated[new_block_start:new_block_end]

if '<HueCurve ref=' in new_block:
    raise SystemExit("FEJL: En fast HueCurve-reference er stadig i CMYKk-blokken.")

for token in required:
    if token not in new_block:
        raise SystemExit(f"FEJL: Validering efter ændring mangler {token}")

ET.fromstring(updated)
path.write_text(updated, encoding="utf-8")
print("OK: Kun de tre faste CMY HueCurve-referencer er fjernet fra CMYKk.")
PY

    sudo install -m 0644 "$SRC" "$DST"
    echo
    show_status
    echo
    echo "Installeret i: $DST"
    ;;

  restore)
    if [[ ! -f "$BACKUP" ]]; then
      echo "FEJL: Backup findes ikke: $BACKUP" >&2
      exit 1
    fi
    cp -av "$BACKUP" "$SRC"
    sudo install -m 0644 "$SRC" "$DST"
    echo
    echo "Den tidligere CMYKk-huemotor er gendannet."
    show_status
    ;;

  *)
    echo "Brug:"
    echo "  bash \"$0\" status"
    echo "  bash \"$0\" apply"
    echo "  bash \"$0\" restore"
    exit 2
    ;;
esac
