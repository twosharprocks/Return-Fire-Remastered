![Return Fire Remastered project emblem and title](title.png)

# Return Fire Remastered

Play your original Windows edition of *Return Fire* on Windows 11 with its 256-colour battlefield, keyboard controls, sound effects and vehicle themes. This unofficial kit brings the original executable to a modern display. You supply the game.

## First launch

1. Download the repository ZIP from GitHub (**Code → Download ZIP**) and extract it into a writable folder.
2. Prepare one of the English Windows PC editions below.
3. Double-click **Play.cmd** and select the folder containing **RFIRE.BIN**. The first setup imports your files into **PrivateGame** and downloads a checksum-verified copy of cnc-ddraw. Later launches work offline.

| Your edition | Folder to select | Music |
| --- | --- | --- |
| English ISO | Mount the extracted disc image in Explorer and select its drive, or select the root of the extracted image. It should contain Langs and Sound. | The tested disc includes the full score. The tank plays *Mars, the Bringer of War* and the helicopter plays *Ride of the Valkyries*. |
| English RIP | Extract the archive and select the inner returnfire folder. | The tested RIP has a 20-byte score placeholder. Engine and weapon effects use separate files. |

Use a separate kit folder for each edition. Once installed, the launcher reuses its local game data. If Windows blocks a downloaded copy you trust, open the ZIP's Properties, select **Unblock** if available and extract again.

## Picture, sound and films

The default 1080p profile centres the original 4:3 frame on a borderless display. At 1920×1080 the battlefield occupies 1440×1080, preserving vehicle and HUD proportions. The original game still draws at 640×480. Live Windows 11 checks confirmed the repaired palette, engine sounds and gunfire. The English ISO reached the training depot. The tested RIP reached the title screen and its imported files matched the gameplay-tested installation.

Run these examples in a command prompt inside the kit folder.

| Command | Effect |
| --- | --- |
| `Play.cmd -MovieFix` | Repairs the horizontal band across ISO films. Both the opening and mission-completion film passed live playback checks. The launcher checks the executable fingerprint and creates a separate local copy. Launch normally to restore standard playback. |
| `Play.cmd -Filter Sharp` | Uses nearest-neighbour scaling for crisp pixel edges. |
| `Play.cmd -Filter xBR` | Uses an optional OpenGL pixel-art shader. Reference frames have been compared. In-game driver compatibility still needs testing. |
| `Play.cmd -ProfileName 720p` | Selects the smaller HD profile. |
| `Play.cmd -ProfileName Original` | Selects the original-size profile. |
| `Play.cmd -WrapperZip "C:\Downloads\cnc-ddraw.zip"` | Uses a local copy of the pinned wrapper for an offline first setup. |

The default Smooth option requests Direct3D bicubic filtering. Its visible effect on the game's 8-bit frames depends on wrapper support. For offline installation, obtain the unmodified archive from the [cnc-ddraw 7.1.0.0 release](https://github.com/FunkyFr3sh/cnc-ddraw/releases/tag/v7.1.0.0).

## Moving or sharing the kit

Close the game before moving your personal installation. Move the whole extracted folder together. The launcher refreshes the game path at startup and uses a temporary drive mapping while playing. Controls and progress live in the Windows user registry and are shared by installations under that account. To share the kit, send a clean repository ZIP. Your installed folder contains your personal copy of the game.

## Where the remaster goes next

- **More battlefield at 16:9.** Compare the same map and camera position in the original and experimental wider viewport. Check extra terrain at both edges, vehicle shape and HUD alignment. Runtime validation awaits a Windows test VM.
- **HD cinematics.** Private 1920×1080 previews cover the opening and four completion films, including a correction for colour fringing around the opening title. Package a repeatable conversion from player-owned media and verify the transition from a mission win into HD playback.
- **Graphics and platform testing.** Compare xBR with the default renderer in motion, then test installation, sound and input under Wine on Linux.

## Credits and licensing

The project MIT licence covers the launcher and its documentation. The bundled xBR shader carries its own author credit and MIT notice. The original game, music and cinematics belong to their respective rights holders and are supplied by the player. The display wrapper is distributed by its own maintainers. [Project licence](LICENSE) · [Shader notice](xbr-lv2-noblend.glsl) · [cnc-ddraw](https://github.com/FunkyFr3sh/cnc-ddraw)
