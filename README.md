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

The `Build and deploy web game` workflow builds the web version for pull requests. After changes are merged into `main`, it also deploys the generated site to GitHub Pages.

For the first deployment, GitHub Pages must allow **GitHub Actions** as its deployment source. The workflow attempts to enable Pages automatically; if repository permissions prevent that, a repository administrator must select **Settings → Pages → Build and deployment → Source → GitHub Actions** once.

### Browser compatibility

Pygbag runs pygame-ce in modern browsers, including mobile browsers. The first visit can take longer because the browser downloads the WebAssembly runtime. Mobile touch controls and layout still need real-device testing and refinement; the current game interface was originally designed for a 16:9 desktop canvas.
