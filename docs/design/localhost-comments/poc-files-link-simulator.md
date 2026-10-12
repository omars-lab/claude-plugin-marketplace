# Files-app link on the iPhone simulator: command log

The long form of the test in section 16 of [design.md](design.md). Run on 2026-10-12 on Omar's
Mac. Placeholders: `<udid>` is the simulator's id, `<group-uuid>` is the Files app group folder.
Paths are written with `~`.

The simulator was never signed into iCloud, and no Apple ID was entered. Nothing was written to
Omar's iCloud Drive. The test picture is invented.

## Setup

1. Pick and boot a simulator.

   ```sh
   xcrun simctl list devices available
   xcrun simctl boot <udid>          # iPhone 17e, iOS 26.5
   open -a Simulator
   ```

2. Check which apps are on it. Files (`com.apple.DocumentsApp`) and Shortcuts are both there.

   ```sh
   xcrun simctl listapps <udid>
   ```

3. Launch Files once. Its "On My iPhone" folder does not exist until Files has run.

   ```sh
   xcrun simctl launch <udid> com.apple.DocumentsApp
   ```

4. Find that folder. It is the app group folder that has a `File Provider Storage` inside.

   ```sh
   find ~/Library/Developer/CoreSimulator/Devices/<udid>/data/Containers/Shared/AppGroup -maxdepth 2 -name "File Provider Storage"
   ```

   It was at
   `~/Library/Developer/CoreSimulator/Devices/<udid>/data/Containers/Shared/AppGroup/<group-uuid>/File Provider Storage/`.
   Below, `<fps>` stands for that folder.

5. Draw an invented test picture (600 × 300, the text "Day 2: museum and park" and
   "TEST SHOT t_8f3a2c (invented)") with a short Python and Pillow script, and copy it in.

   ```sh
   mkdir -p "<fps>/page-comments/sample-repo/shots"
   cp t_8f3a2c.png "<fps>/page-comments/sample-repo/shots/"
   ```

## Test 1, the first link: opened from the Mac

```sh
xcrun simctl openurl <udid> 'shareddocuments://<fps with spaces as %20>/page-comments/sample-repo/shots/t_8f3a2c.png'
```

The path after `shareddocuments://` is the full path from the disk root, so the link has three
slashes in a row (`shareddocuments:///` then the path, with `~` expanded). The space in `File Provider Storage` is written `%20`.

**Result:** Files opened and showed the picture full screen. Omar watched it work.

## Tests 2 to 4: links on a web page, opened in Safari

A test page with three link buttons:

| Button | Link |
|---|---|
| Open the screenshot in Files | `shareddocuments:///<fps>/page-comments/sample-repo/shots/t_8f3a2c.png` |
| Open the shots folder in Files | `shareddocuments:///<fps>/page-comments/sample-repo/shots/` |
| Open through a Shortcut (x-callback) | `shortcuts://x-callback-url/run-shortcut?name=Open%20Comment%20Shot&input=text&text=page-comments%2Fsample-repo%2Fshots%2Ft_8f3a2c.png` |

The page also had a short script: if the address ends in `#file`, `#folder` or `#shortcut`, it
clicks that button after 800 ms. That let a link be followed without a tap.

Served from the Mac, loopback only, and opened in the simulator's Safari. The simulator shares
the Mac's network, so it reaches `127.0.0.1`.

```sh
python3 -m http.server 8765 --bind 127.0.0.1 --directory site
xcrun simctl openurl <udid> 'http://127.0.0.1:8765/'
xcrun simctl io <udid> screenshot 03-safari-page.png
```

**Test 2, the second link: a tap on "Open the screenshot in Files".**
Files opened on Recents, showing `t_8f3a2c`, with a "◀ Safari" back link at the top left. Omar
watched it, then tapped the button himself. It opened the picture directly.

**Test 3: the folder link.**
Opened with `xcrun simctl openurl <udid> 'http://127.0.0.1:8765/#folder'`, so the page's script
followed the link. Safari first asked "Open this page in "Files"?" with Cancel and Open. Omar
tapped the folder button himself, and Files opened the `shots` folder.

**Test 4: the Shortcut link.**
Omar tapped it. Shortcuts opened and said the Shortcut was not found. That is expected: no
Shortcut named "Open Comment Shot" was ever made. The plain `shareddocuments://` links were
enough, so none was made.

## Clean-up

```sh
xcrun simctl shutdown <udid>
```

The test server was stopped. The test picture stays only inside the simulator's own folder.
Nothing was put in iCloud Drive or in Omar's `CloudDesktop/data` folder.

## Screenshots kept

In `media/`, each shrunk to 640 px tall with `sips -Z 640`:

| File | Shows |
|---|---|
| `sim-1-file-link-opens-image.png` | Test 1: Files showing the picture full screen |
| `sim-2-safari-test-page.png` | The test page in Safari, with its three buttons |
| `sim-3-safari-asks-to-open-files.png` | Test 3: Safari asking "Open this page in Files?" |
| `sim-4-files-after-safari-tap.png` | Test 2: Files on Recents after the tap, with the Safari back link |

Screenshots that showed anything outside the simulator were not kept.
