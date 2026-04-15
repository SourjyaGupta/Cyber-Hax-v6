# Cyber Hax v5 Deploy Instructions

## 1. `itch_build/` usage

`itch_build/` is the HTML5 package intended for itch.io upload.

It is already configured to:
- use relative asset paths
- connect to the Render backend at `wss://cyber-hax-server.onrender.com`
- call room creation at `https://cyber-hax-server.onrender.com/api/rooms/new`
- fail gracefully into manual room-code joining if room creation is unavailable

Files included:
- `index.html`
- `app.js`
- `styles.css`
- `main_music.ogg`
- `favicon.svg`

## 2. How to zip `itch_build/` for itch.io

Important: the files must be at the ZIP root, not inside an extra nested folder.

### PowerShell example

From the repo root:

```powershell
cd D:\Projects\Cyber\Cyber-Hax-v5
Compress-Archive -Path .\itch_build\* -DestinationPath .\Cyber-Hax-v5-itch.zip -Force
```

Upload `Cyber-Hax-v5-itch.zip` to itch.io as an HTML game.

## 3. Files that must be at the ZIP root

These should appear immediately when the ZIP opens:
- `index.html`
- `app.js`
- `styles.css`
- `main_music.ogg`
- `favicon.svg`

Do not zip the parent folder itself if that creates `itch_build/index.html` inside the archive.

## 4. `local_build/` usage for FastAPI testing

`local_build/` is the same client packaged for a local FastAPI setup that serves assets from `/static/...`.

It uses:
- `/static/styles.css`
- `/static/app.js`
- `/static/main_music.ogg`
- `/static/favicon.svg`

### Recommended local test approach

Use `local_build/` as the folder mounted to `/static` and serve `local_build/index.html` at `/`.

If you want to test it with the current app:
1. point `WEB_DIR` in `server_runtime.py` to `local_build`
2. run the server locally
3. open `http://127.0.0.1:8000`

Local build behavior:
- defaults to `ws://127.0.0.1:8000` when there is no better same-origin host
- still supports manual room code entry
- still keeps the same UI, chat, invite flow, reconnect handling, command deck, and modals

## 5. Deploy `landing_site/` on GitHub Pages

`landing_site/` is a separate static marketing site. It does not embed the game by default. It sends traffic to your itch.io page.

### Files
- `landing_site/index.html`
- `landing_site/styles.css`
- `landing_site/script.js`

### GitHub Pages steps

1. Put the contents of `landing_site/` into a repo or branch for the site.
2. Commit and push.
3. In GitHub:
   - open `Settings`
   - open `Pages`
   - choose the branch/folder you want to publish
4. Wait for GitHub Pages to deploy.
5. Replace the placeholder itch URL in `landing_site/script.js`.

## 6. Deploy `landing_site/` on Netlify

### Drag-and-drop option

1. Zip the contents of `landing_site/`
2. Log in to Netlify
3. Create a new site by dragging the folder or ZIP into Netlify
4. Replace the placeholder itch URL in `landing_site/script.js`

### Git-based option

1. Push `landing_site/` to GitHub
2. Create a new Netlify site from that repo
3. Set publish directory to `landing_site`
4. Deploy

## 7. Where to paste Google AdSense later

There are two prepared places:

### In `landing_site/index.html`

Search for:

```html
<!-- Future AdSense slot: between content sections -->
```

That section currently contains a visible placeholder block. You can replace or augment it with AdSense markup later.

### In `<head>`

You can also add the AdSense script tag inside `landing_site/index.html` `<head>` when you are ready.

## 8. How to test multiplayer with multiple room codes

### On the itch build

1. Open the uploaded game in two separate browser windows or two devices.
2. In one window, click `Create Room`.
3. Share the generated link or tell the second player the room code.
4. In the second window, join the same room code.

### Manual room-code fallback

If `Create Room` fails:
1. type a room code manually in the `Room Code` field, for example `ALPHA1`
2. have the second player type the same room code
3. both players press `Join Room`

## 9. Notes about create-room endpoint fallback

The itch build is intentionally resilient:
- it tries `https://cyber-hax-server.onrender.com/api/rooms/new`
- if that endpoint is missing, sleeping, or failing, the UI does not dead-end
- the player gets a warning and can still enter a room code manually

This keeps public playtests alive even if automated room creation is temporarily unavailable.

## 10. Recommended itch embed settings

Recommended:
- width: `1280`
- height: `1000` or `1100`
- fullscreen: enabled
- scrollbars: enabled if needed

These settings give the board, sidebar, terminal, and chat enough room while still behaving responsively.

## 11. Final checklist before publishing

### For itch.io
- verify the ZIP contains `index.html` at the root
- verify the uploaded build opens without missing CSS/JS/audio
- verify one player can create or manually join a room
- verify a second player can connect to the same room

### For the landing site
- replace the placeholder itch URL in `landing_site/script.js`
- replace screenshot placeholders with real captures when available
- replace privacy/contact placeholders before public monetization
