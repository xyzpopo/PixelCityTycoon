# Pixel City Tycoon

Isometric sandbox city-building game built with Python and pygame-ce.

## Windows version

- Run `run_windows.bat` to launch from Python.
- Run `build_windows.bat` to create the standalone Windows EXE.
- The Windows build continues to use the regular synchronous Pygame loop and saves to Documents/PixelCityTycoon/saves.

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

The current game repository is private, so the first automatic deployment was rejected by GitHub before the publish step. The build itself succeeded. To enable Pages deployment, first confirm that the account plan supports Pages for this private repository (or intentionally make the repository public). Then create the repository Actions variable `ENABLE_GITHUB_PAGES=true` under **Settings → Secrets and variables → Actions → Variables**. The workflow will then attempt deployment. If Pages still needs initial setup, select **Settings → Pages → Build and deployment → Source → GitHub Actions**.

Do not make the source repository public just to remove this deployment error unless you explicitly intend to publish the source code.

### Browser compatibility

Pygbag runs pygame-ce in modern browsers, including mobile browsers. The first visit can take longer because the browser downloads the WebAssembly runtime. Mobile touch controls and layout still need real-device testing and refinement; the current game interface was originally designed for a 16:9 desktop canvas.
