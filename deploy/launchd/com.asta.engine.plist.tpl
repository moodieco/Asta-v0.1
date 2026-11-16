<?xml version="1.0" encoding="UTF-8"?>
<!-- Template — deploy/install.sh substitutes @ASTA_ROOT@ and @ASTA_BIN@.
     KeepAlive restarts the engine after a crash; RunAtLoad starts it at login. -->
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.asta.engine</string>
  <key>ProgramArguments</key>
  <array>
    <string>@ASTA_BIN@</string>
    <string>serve</string>
    <string>--host</string>
    <string>127.0.0.1</string>
    <string>--port</string>
    <string>4310</string>
    <string>--no-browser</string>
  </array>
  <key>WorkingDirectory</key>
  <string>@ASTA_ROOT@</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONUNBUFFERED</key>
    <string>1</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>10</integer>
  <key>StandardOutPath</key>
  <string>@ASTA_ROOT@/data/logs/service.out.log</string>
  <key>StandardErrorPath</key>
  <string>@ASTA_ROOT@/data/logs/service.err.log</string>
</dict>
</plist>
