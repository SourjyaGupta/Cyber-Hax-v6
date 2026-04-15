# Cyber Hax v5 Android Wrapper

This folder contains a separate Android Studio project that wraps the live web game in a fullscreen Kotlin `WebView` app. The existing web game and backend are left untouched.

## What This App Does

- loads the public live game URL inside the app
- uses a splash screen on Android 12+
- shows a loading state while the game boots
- shows a retry/offline panel if the game cannot load
- keeps external links out of the in-app `WebView`
- supports immersive fullscreen play
- keeps the screen awake during active play
- targets Play-compliant SDK levels for a fast first mobile release

## Project Structure

```text
android-app/
+-- app/
|   +-- build.gradle.kts
|   +-- proguard-rules.pro
|   \-- src/main/
|       +-- AndroidManifest.xml
|       +-- java/com/cyberhax/game/
|       |   +-- AppConfig.kt
|       |   \-- MainActivity.kt
|       \-- res/
+-- build.gradle.kts
+-- gradle.properties
+-- gradle/wrapper/gradle-wrapper.properties
+-- settings.gradle.kts
\-- README.md
```

## Edit These First

1. Package name
   - The project now uses `com.cyberhax.game`
   - Change `namespace` and `applicationId` in [app/build.gradle.kts](D:/Projects/Cyber/Cyber-Hax-v5/android-app/app/build.gradle.kts) only if you want a different final ID
   - If you change it, update the package lines in [AppConfig.kt](D:/Projects/Cyber/Cyber-Hax-v5/android-app/app/src/main/java/com/cyberhax/game/AppConfig.kt) and [MainActivity.kt](D:/Projects/Cyber/Cyber-Hax-v5/android-app/app/src/main/java/com/cyberhax/game/MainActivity.kt)

2. App name
   - Update `app_name` in [app/src/main/res/values/strings.xml](D:/Projects/Cyber/Cyber-Hax-v5/android-app/app/src/main/res/values/strings.xml)

3. Live game URL
   - Update `GAME_URL` and `INTERNAL_HOSTS` in [app/src/main/java/com/cyberhax/game/AppConfig.kt](D:/Projects/Cyber/Cyber-Hax-v5/android-app/app/src/main/java/com/cyberhax/game/AppConfig.kt)
   - Current default: `https://cyber-hax.netlify.app/play/`

4. Icons and splash artwork
   - Replace the placeholder vector assets in:
     - [app/src/main/res/drawable/ic_launcher_foreground.xml](D:/Projects/Cyber/Cyber-Hax-v5/android-app/app/src/main/res/drawable/ic_launcher_foreground.xml)
     - [app/src/main/res/drawable/ic_launcher_monochrome.xml](D:/Projects/Cyber/Cyber-Hax-v5/android-app/app/src/main/res/drawable/ic_launcher_monochrome.xml)
     - [app/src/main/res/drawable/ic_splash_foreground.xml](D:/Projects/Cyber/Cyber-Hax-v5/android-app/app/src/main/res/drawable/ic_splash_foreground.xml)

5. Versioning
   - Update `versionCode` and `versionName` in [app/build.gradle.kts](D:/Projects/Cyber/Cyber-Hax-v5/android-app/app/build.gradle.kts)

## Open In Android Studio

1. Open Android Studio
2. Choose `Open`
3. Select `D:\Projects\Cyber\Cyber-Hax-v5\android-app`
4. Let Gradle sync

### Important wrapper note

This environment could not generate `gradle-wrapper.jar`, so if Android Studio warns about a missing wrapper bootstrap file:

1. Open the project anyway in Android Studio
2. Let Android Studio use/download the Gradle version from `gradle-wrapper.properties`
3. If needed, use a local Gradle install and run:

```powershell
cd D:\Projects\Cyber\Cyber-Hax-v5\android-app
gradle wrapper
```

After that, the wrapper files will be complete for CLI builds.

## Run On A Phone

1. Enable Developer Options and USB debugging on the phone
2. Connect the phone
3. In Android Studio, select the device from the top toolbar
4. Click `Run`

## Local Testing Facility

The debug build now includes a built-in `Connection Lab` panel so you can point the wrapper at a local host without changing code.

### Fastest local test with your FastAPI server

1. On your PC, run:

```powershell
cd D:\Projects\Cyber\Cyber-Hax-v5
uvicorn server_main:app --host 0.0.0.0 --port 8000 --reload
```

2. Install/run the Android **debug** build.
3. In the app, open `Connection Lab`.
4. Use one of these URLs:
   - Android emulator: `http://10.0.2.2:8000/`
   - Real phone on same Wi-Fi: `http://YOUR_PC_LAN_IP:8000/`
5. Tap `Save And Reload`.

### Optional advanced local static-site test

If you want to test the Netlify-style static build instead:

```powershell
cd D:\Projects\Cyber\Cyber-Hax-v5
python build_netlify_site.py
python -m http.server 8080 --directory site_dist
```

Then use:
- Emulator: `http://10.0.2.2:8080/play/?server=ws://10.0.2.2:8000`
- Real phone: `http://YOUR_PC_LAN_IP:8080/play/?server=ws://YOUR_PC_LAN_IP:8000`

### Important note

- Local HTTP testing is enabled only for the **debug** build.
- Release builds stay stricter and do not expose the Connection Lab UI.

## Build A Debug APK

### Android Studio

1. `Build`
2. `Build Bundle(s) / APK(s)`
3. `Build APK(s)`

### Command line

After the Gradle wrapper is fully available:

```powershell
cd D:\Projects\Cyber\Cyber-Hax-v5\android-app
.\gradlew.bat assembleDebug
```

## Build A Release AAB For Play Store

### Android Studio

1. `Build`
2. `Generate Signed Bundle / APK`
3. Choose `Android App Bundle`
4. Create or select your keystore
5. Pick the `release` build variant
6. Finish the wizard

### Command line

After signing is configured and the wrapper is complete:

```powershell
cd D:\Projects\Cyber\Cyber-Hax-v5\android-app
.\gradlew.bat bundleRelease
```

Output location:

```text
android-app\app\build\outputs\bundle\release\
```

## Signing Setup

Do not commit real signing secrets. For release builds:

1. Create a keystore in Android Studio during the signed bundle flow
2. Keep the keystore and passwords backed up safely
3. If you want CLI signing later, add a local-only `keystore.properties` file and read it from `app/build.gradle.kts`

## Why The WebView Settings Were Chosen

- JavaScript is required because the game is an interactive web app
- DOM storage is enabled because modern browser games rely on it
- mixed content is blocked for safer HTTPS-only loading
- file/content access stays off because the game does not need arbitrary local files
- non-game links open externally so the app stays focused on gameplay
- safe browsing is enabled when the Android WebView supports it

## Manual Checklist Before Play Store Upload

1. Confirm `com.cyberhax.game` is the final package name you want
2. Replace or refine the current icons and splash art if you want a final branded version
3. Confirm the live URL is the final public game URL
4. Confirm the site works well in Android Chrome before wrapping it
5. Generate a signed `AAB`
6. Prepare Play Console assets:
   - app icon
   - feature graphic
   - screenshots
   - short description
   - full description
   - privacy policy URL
7. Add a privacy policy page on your public site if you use analytics, accounts, or ads later

## Possible Play Store Review Risks

- If the wrapped site looks too much like a thin website shell with no mobile care, review quality can suffer
- If the live site is unstable, blank, or slow on mobile networks, the app can be judged poorly
- If the privacy policy is missing once you add analytics, ads, or sign-in, publishing gets harder
- If the app frequently opens broken external pages, review quality drops

## How To Reduce Rejection Risk

- keep the mobile experience clean and reliable
- test on at least one real Android phone
- make sure the game loads without console errors on mobile Chrome
- provide a real privacy policy before adding tracking or monetization
- keep store listing screenshots accurate to the actual app

## Future Upgrade Path: Trusted Web Activity

If the live web game becomes a stronger mobile PWA later, you can move from `WebView` to a Trusted Web Activity. For that path, the site should add:

- a full `manifest.json`
- service worker support
- installable PWA behavior
- Digital Asset Links verification for the production domain

For now, `WebView` is the fastest playable route and needs the least change to your existing game.

## Added Play Store Art Templates

Source templates are included in [playstore-assets](D:/Projects/Cyber/Cyber-Hax-v5/android-app/playstore-assets):

- [cyber-hax-store-icon.svg](D:/Projects/Cyber/Cyber-Hax-v5/android-app/playstore-assets/cyber-hax-store-icon.svg)
- [cyber-hax-feature-graphic.svg](D:/Projects/Cyber/Cyber-Hax-v5/android-app/playstore-assets/cyber-hax-feature-graphic.svg)

Export these to PNG for the Play Console listing.
