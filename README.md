# Pixel City Tycoon

Isometric sandbox city-building game built with Python and pygame-ce.

## Windows version

- Run `run_windows.bat` to launch from Python.
- Run `build_windows.bat` to create the standalone Windows EXE.
- The Windows build continues to use the regular synchronous Pygame loop and saves to Documents/PixelCityTycoon/saves.
- The title menu separates single-player (new game / continue) from multiplayer (create room / join room). Online multiplayer is not connected yet.
- In-game mode keys are fixed: F1 Move, F2 Remove, F3 Road, F4 Build, F5 Restore. ESC or the Menu button autosaves and returns to the title screen.

## Browser version

The browser build uses [Pygbag](https://github.com/pygame-web/pygbag) to package pygame-ce for WebAssembly.

### Build locally

Install the web dependencies:

```bash
python -m pip install -r requirements-web.txt
```

Build the game:

```bash
python -m pygbag --build --ume_block 0 --title "Pixel City Tycoon" --package pixel-city-tycoon .
```

The generated site is placed in `build/web`. The same source code is used for both Windows and browser builds; browser saves are stored in that browser's local storage, separately from Windows save files.

### GitHub Pages

The workflow always builds the browser version and uploads it as a workflow artifact. Publishing is deliberately opt-in because GitHub Pages eligibility depends on repository visibility and the account plan:

- GitHub Free supports Pages for public repositories.
- A private repository needs GitHub Pro, GitHub Team, or an Enterprise plan.
- A published Pages site is public on the internet, even when its source repository is private.

The repository is public and GitHub Pages deploys automatically from successful pushes to the main branch. The published game is available at https://xyzpopo.github.io/PixelCityTycoon/.

### Browser compatibility

Pygbag runs pygame-ce in modern browsers, including mobile browsers. The first visit can take longer because the browser downloads the WebAssembly runtime. The web build downloads and packages Noto Sans KR so Korean text does not depend on fonts installed on the device. Mobile touch controls and layout are being added in stages and still require real-device testing.


## Multiplayer lobby server (first online milestone)

The repository includes a WebSocket lobby service for room creation/joining, 2–4 player presence, ready status and lobby chat. The current game client connects from the Windows EXE. Shared-city simulation and authoritative world-command synchronization are **not implemented yet**.

### Deploy the lobby

1. Create a Render account and choose **New → Blueprint**.
2. Connect this repository and deploy the `render.yaml` blueprint.
3. When Render provides the service hostname, use `wss://YOUR-SERVICE.onrender.com/ws` in the game's Multiplayer screen.
4. Check `https://YOUR-SERVICE.onrender.com/health` to confirm the service is awake.

For local testing, install `requirements-server.txt` and run `uvicorn server:app --host 0.0.0.0 --port 8765`. The default game address is `ws://127.0.0.1:8765/ws`. To test with another PC over the internet, deploy the server and use its secure `wss://` address.

Rooms are currently held in server memory and disappear when the service restarts. Do not treat room codes as account authentication. The first milestone is the lobby transport; the next multiplayer milestone is shared-world snapshots, server-ordered game commands and reconnect recovery.
