@echo off
setlocal

set WRAPPER_JAR=%~dp0gradle\wrapper\gradle-wrapper.jar

if exist "%WRAPPER_JAR%" (
  java -classpath "%WRAPPER_JAR%" org.gradle.wrapper.GradleWrapperMain %*
  exit /b %ERRORLEVEL%
)

where gradle >nul 2>nul
if %ERRORLEVEL%==0 (
  echo gradle-wrapper.jar not found. Falling back to local Gradle installation.
  gradle %*
  exit /b %ERRORLEVEL%
)

echo gradle-wrapper.jar not found and no local Gradle installation is available.
echo Open this project in Android Studio to sync it, or install Gradle and run: gradle wrapper
exit /b 1
