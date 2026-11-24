![Return Fire Remastered project emblem and title](title.png)

# Return Fire Remastered

Play your original English Windows edition of *Return Fire* on Windows 11. The kit preserves the game's palette, keyboard controls and sharp pixel edges. The English ISO also supports an experimental wider battlefield and HD cinematics built from your own disc files.

## Install and play

1. Download [the v0.2.0 Windows kit](https://github.com/twosharprocks/Return-Fire-Remastered/releases/download/v0.2.0/Return-Fire-Remastered-v0.2.0-Windows.zip) and extract the entire folder somewhere writable. If Windows blocks a ZIP you trust, open its Properties and select **Unblock** before extracting.
2. Double-click **Play.cmd**. Select the folder containing **RFIRE.BIN**. For the ISO, mount or extract your disc image and select its root. For the RIP, extract the archive and select the inner game folder.
3. Choose a display mode and select **Play**. **Original 4:3 - windowed** is preselected. You can choose again the next time you launch.

First setup copies your files into **PrivateGame** and downloads a checksum-verified cnc-ddraw display wrapper. Later launches work offline. Use a separate extracted kit folder for each edition. Python and FFmpeg are optional and are only needed for the HD film features.

| Display picker and media | English ISO | English RIP |
| --- | --- | --- |
| Original 4:3, windowed | Available | Available |
| Experimental 16:9, borderless fullscreen | Available for the verified English ISO executable | Disabled in the picker |
| Engine and weapon effects | Available | Available |
| Vehicle music | Included on the tested disc | The tested RIP has a 20-byte score placeholder |
| Build and play HD films | Available from your own ISO files | Requires ISO media and installation |

The 4:3 option opens a movable window that fits the desktop and retains the original 640×480 game surface. The 16:9 option fills the primary display, keeps the game menu accessible, and expands the battlefield from 320×152 to 428×152 logical pixels. The vehicles keep their proportions and the single-player HUD stays centred. Sharp is the default in both modes.

## Build the HD films from your ISO

1. Complete first setup with your English ISO. Install Python 3 and FFmpeg with the libx264 encoder. Open **Command Prompt** in the extracted kit folder and check that both tools are on PATH.
2. Install the optional playback dependencies into the same Python environment.

       python --version
       ffmpeg -version
       python -m pip install opencv-python psutil

3. Build the films using the files already imported from your ISO.

       Play.cmd -BuildCinematics

   To read directly from a mounted disc or an extracted ISO folder, pass its root. For example, use the following command for a disc mounted on D.

       Play.cmd -BuildCinematics -Source D:\

4. Run **Play.cmd**, choose either display mode, leave **Play installed HD films** checked, and select **Play**.

The builder checks five original STM files and writes **rf.mp4** (opening) and **win.mp4**, **win1.mp4**, **win2.mp4**, **win3.mp4** (victories) to **HD-Cinematics** beside Play.cmd. It preserves the original 15 fps and stereo audio and scales a 16:9 crop to 1920×1080. Rename an existing output folder before rebuilding. Keep the generated films with your private installation.

The two animated studio openings keep their centred 4:3 framing. The HD title uses the corrected fire palette. Victory films play automatically with the original single-player flag emblem. The game remains responsible for timing, skipping and sound.

## Direct launch and other options

Run these commands in the kit folder.

| Command | Effect |
| --- | --- |
| `Play.cmd -DisplayMode Windowed4x3` | Launch the original window directly. |
| `Play.cmd -DisplayMode Fullscreen16x9 -HDCinematics` | Launch experimental fullscreen with your installed HD films. Omit `-HDCinematics` for native films. |
| `Play.cmd -WidescreenTrial` | Existing shortcut for experimental fullscreen. |
| `Play.cmd -MovieFix` | Repair the horizontal band in native ISO films. The launcher creates a fingerprint-checked local executable. |
| `Play.cmd -Filter xBR` | Try the optional OpenGL pixel-art shader. Sharp and Smooth are also available. |
| `Play.cmd -ProfileName 720p` | Cap the original window at 720 pixels high. Use `Original` for 640×480. |
| `Play.cmd -WrapperZip "C:\Downloads\cnc-ddraw.zip"` | Install offline using the unmodified [cnc-ddraw 7.1.0.0 release archive](https://github.com/FunkyFr3sh/cnc-ddraw/releases/tag/v7.1.0.0). |

## Tested on Windows 11

Both editions launched through the display picker in a 4:3 window. The ISO also launched in borderless fullscreen on a 1920×1080 desktop. On The Cakewalk, the wider view showed additional terrain on both sides and the HUD remained centred after switching to the jeep. Returning the flag automatically played the HD victory film. The visible frame matched the local HD source, and the player confirmed the restored emblem, clean playback and correct framing.

Full missions tested with the v0.1.0 kit confirmed engine and weapon effects in both editions. The ISO played *Mars, the Bringer of War* in the tank and *Ride of the Valkyries* in the helicopter. Further tests include the other three victory films on native Windows, additional vehicles, split-screen and Linux under Wine.

## Sharing and credits

Share the Windows release ZIP. Your installed **PrivateGame** folder and generated **HD-Cinematics** contain material from your copy of the game. To move a personal installation, close the game and move the whole extracted folder. Controls and progress live in the Windows user registry and are shared by installations under that account.

The MIT licence covers the launcher and its documentation. The bundled xBR shader includes its own author credit and MIT notice. The original game, music and cinematics belong to their respective rights holders. The display wrapper is distributed by its maintainers. [Project licence](LICENSE) · [Shader notice](xbr-lv2-noblend.glsl) · [cnc-ddraw](https://github.com/FunkyFr3sh/cnc-ddraw)
