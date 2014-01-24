#! /bin/bash

VOLUME_NAME="Nuxeo Drive"
SCRIPT_LOCATION="`dirname \"$0\"`"
SRC_FOLDER_TEMP="$SCRIPT_LOCATION/dmg_src_folder.tmp"
DMG_TEMP="$SCRIPT_LOCATION/nuxeo-drive.tmp.dmg"
BACKGROUND_FILE="$SCRIPT_LOCATION/dmgbackground.png"
GENERATED_DS_STORE="$SCRIPT_LOCATION/generated_DS_Store"

PACKAGE_PATH="$SCRIPT_LOCATION/../../dist/Nuxeo Drive.app"
SIGNING_IDENTITY="Nuxeo Drive"
DMG_PATH="$SCRIPT_LOCATION/../../dist/Nuxeo Drive.dmg"
DMG_SIZE=$(($(du -sm "$PACKAGE_PATH" | cut -d$'\t' -f1,1)+20))m

# Sign application bundle
codesign -s "$SIGNING_IDENTITY" "$PACKAGE_PATH" -v
# Verify code signature
codesign -vv "$PACKAGE_PATH"
codesign -d -vvv "$PACKAGE_PATH"
spctl --assess --type execute "$PACKAGE_PATH" --verbose

rm -rf "$SRC_FOLDER_TEMP" "$DMG_TEMP"
mkdir "$SRC_FOLDER_TEMP"

cp -a "$PACKAGE_PATH" "$SRC_FOLDER_TEMP"
mkdir "$SRC_FOLDER_TEMP/.background"
cp "$BACKGROUND_FILE" "$SRC_FOLDER_TEMP/.background"
cp "$GENERATED_DS_STORE" "$SRC_FOLDER_TEMP/.DS_Store"
ln -s /Applications "$SRC_FOLDER_TEMP"

hdiutil create -srcfolder "$SRC_FOLDER_TEMP" -volname "${VOLUME_NAME}" -fs HFS+ -fsargs "-c c=64,a=16,e=16" -format UDRW -size "${DMG_SIZE}" "${DMG_TEMP}"

rm -f "$DMG_PATH"
hdiutil convert "${DMG_TEMP}" -format UDZO -imagekey zlib-level=9 -o "${DMG_PATH}"

rm -rf "$SRC_FOLDER_TEMP" "$DMG_TEMP"
